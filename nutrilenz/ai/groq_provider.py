import http.client
import logging

from ..errors.ai_error import AIError
from .ai_request import AIRequest
from .http_client import HttpClient
from .ai_provider import AIProvider

logger = logging.getLogger("nutrilenz.ai")


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
