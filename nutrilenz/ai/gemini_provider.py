import logging

from ..errors.ai_error import AIError
from .ai_request import AIRequest
from .ai_provider import AIProvider

logger = logging.getLogger("nutrilenz.ai")


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
