import json


class JsonReplyParser:
    """Turns the model's raw text into a dict. Raises ValueError if it is not a JSON object."""

    def parse(self, raw_text: str) -> dict:
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError("Empty response")
        text = raw_text.strip()
        # Some models wrap JSON in ```json ... ```
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError("Response is not valid JSON") from error
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        return data
