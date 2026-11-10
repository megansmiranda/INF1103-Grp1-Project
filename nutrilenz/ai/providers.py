import http.client
import json
import logging
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from ..errors.ai_error import AIError
from .results import AIRequest

logger = logging.getLogger("nutrilenz.ai")


class HttpClient:
    """Sends one JSON POST request. Every failure becomes an AIError with a code."""

    def __init__(self, timeout_seconds: int = 30):
        self._timeout = timeout_seconds

    def post_json(self, url: str, headers: dict, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        headers = dict(headers)
        headers["Content-Type"] = "application/json"
        headers["User-Agent"] = "NutriLenz/2.0"
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        safe_url = url.split("?")[0]
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                reply = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            logger.warning("HTTP %s from %s: %s", error.code, safe_url, self._error_reason(error))
            if error.code in (401, 403):
                raise AIError("AUTHENTICATION_ERROR") from error
            if error.code in (400, 404):
                raise AIError("CONFIGURATION_ERROR") from error    # e.g. wrong model name
            raise AIError("API_UNAVAILABLE") from error            # 429 rate limit, 5xx
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:
            logger.warning("Connection problem with %s: %r", safe_url, error)
            raise AIError("API_CONNECTION_ERROR") from error
        except ValueError as error:
            logger.warning("Unreadable reply from %s", safe_url)
            raise AIError("INVALID_RESPONSE") from error
        if not isinstance(reply, dict):
            raise AIError("INVALID_RESPONSE", "reply was not a JSON object")
        return reply

    @staticmethod
    def _error_reason(http_error: urllib.error.HTTPError) -> str:
        """Short reason from the error reply, for the log. Keys are in headers, not here."""
        try:
            reply = json.loads(http_error.read().decode("utf-8"))
            reason = str(reply["error"]["message"])
        except Exception:
            reason = str(http_error.reason)
        return reason[:200]


class AIProvider(ABC):
    """Base class for an AI service. generate() is the same for every provider:
    build the body, send it, pull the text out. Subclasses fill in those steps."""

    def __init__(self, api_key: str, model: str, http: HttpClient):
        if not api_key:
            raise ValueError("API key is required")
        self.__api_key = api_key
        self._model = model
        self._http = http

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name shown to the user, e.g. 'gemini'."""

    @property
    @abstractmethod
    def supports_images(self) -> bool:
        """True if this provider can read label photos."""

    @abstractmethod
    def _url(self, request: AIRequest) -> str:
        """Endpoint for this request."""

    @abstractmethod
    def _auth_headers(self, api_key: str) -> dict:
        """Headers carrying the API key (never the URL, so keys stay out of logs)."""

    @abstractmethod
    def _build_body(self, request: AIRequest) -> dict:
        """Provider-specific request body."""

    @abstractmethod
    def _extract_text(self, reply: dict) -> str:
        """Pull the model's text out of the provider's reply. Raises AIError if the shape is wrong."""

    def generate(self, request: AIRequest) -> str:
        if request.image is not None and not self.supports_images:
            raise AIError("NO_IMAGE_PROVIDER")
        reply = self._http.post_json(self._url(request), self._auth_headers(self.__api_key),
                                     self._build_body(request))
        return self._extract_text(reply)


class GeminiProvider(AIProvider):
    """Google Gemini. Main provider; reads text and photos."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def supports_images(self) -> bool:
        return True

    def _url(self, request: AIRequest) -> str:
        return self.URL.format(model=self._model)

    def _auth_headers(self, api_key: str) -> dict:
        return {"x-goog-api-key": api_key}

    def _build_body(self, request: AIRequest) -> dict:
        parts = []
        if request.image is not None:
            parts.append({"inline_data": {"mime_type": request.image.mime_type,
                                          "data": request.image.as_base64()}})
        parts.append({"text": request.user_content})
        return {
            "systemInstruction": {"parts": [{"text": request.system_rules}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0,                        # same input -> same answer
                "responseMimeType": "application/json",
                "maxOutputTokens": 2048,
            },
        }

    def _extract_text(self, reply: dict) -> str:
        try:
            candidate = reply["candidates"][0]
            if candidate.get("finishReason") not in (None, "STOP"):
                logger.warning("Gemini stopped early: %s", candidate.get("finishReason"))
                raise AIError("INVALID_RESPONSE", "stopped early")
            return candidate["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as error:
            raise AIError("INVALID_RESPONSE", "unexpected Gemini reply shape") from error


class GroqProvider(AIProvider):
    """Groq (OpenAI-style API). Backup provider. Reads photos only if a vision model is set."""

    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, http: HttpClient, vision_model: str | None = None):
        super().__init__(api_key, model, http)
        self._vision_model = vision_model or None

    @property
    def name(self) -> str:
        return "groq"

    @property
    def supports_images(self) -> bool:
        return self._vision_model is not None

    def _url(self, request: AIRequest) -> str:
        return self.URL

    def _auth_headers(self, api_key: str) -> dict:
        return {"Authorization": "Bearer " + api_key}

    def _build_body(self, request: AIRequest) -> dict:
        if request.image is None:
            user_content = request.user_content
            model = self._model
        else:
            data_url = "data:" + request.image.mime_type + ";base64," + request.image.as_base64()
            user_content = [{"type": "text", "text": request.user_content},
                            {"type": "image_url", "image_url": {"url": data_url}}]
            model = self._vision_model
        body = {
            "model": model,
            "messages": [{"role": "system", "content": request.system_rules},
                         {"role": "user", "content": user_content}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 2048,
        }
        if model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"            # keeps token usage small
        return body

    def _extract_text(self, reply: dict) -> str:
        try:
            choice = reply["choices"][0]
            if choice.get("finish_reason") not in (None, "stop"):
                logger.warning("Groq stopped early: %s", choice.get("finish_reason"))
                raise AIError("INVALID_RESPONSE", "stopped early")
            return choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise AIError("INVALID_RESPONSE", "unexpected Groq reply shape") from error
