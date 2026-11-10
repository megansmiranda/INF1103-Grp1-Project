import http.client
from abc import ABC, abstractmethod

from ..errors.ai_error import AIError
from .ai_request import AIRequest
from .http_client import HttpClient


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
