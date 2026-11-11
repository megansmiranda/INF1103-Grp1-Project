import http.client
import json
import logging
import urllib.error
import urllib.request

from ..errors.ai_error import AIError

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
