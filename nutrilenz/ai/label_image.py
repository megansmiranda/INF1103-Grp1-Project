import base64


class LabelImage:
    """A photo uploaded by the user. Checked before it is ever sent to an AI."""

    ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp")
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, data: bytes, mime_type: str, filename: str = "label"):
        if mime_type not in self.ALLOWED_TYPES:
            raise ValueError("Only JPG, PNG or WEBP photos are supported")
        if not data:
            raise ValueError("The photo is empty")
        if len(data) > self.MAX_BYTES:
            raise ValueError("The photo is too large (max 8 MB)")
        self._data = data
        self._mime_type = mime_type
        self._filename = filename

    @property
    def mime_type(self) -> str:
        return self._mime_type

    @property
    def filename(self) -> str:
        return self._filename

    def as_base64(self) -> str:
        return base64.b64encode(self._data).decode("ascii")
