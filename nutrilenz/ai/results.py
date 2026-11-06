import base64

from ..domain.analysis import ProductSuggestion


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


class AIRequest:
    """What gets sent to a provider: system rules, the user data and an optional photo."""

    def __init__(self, system_rules: str, user_content: str, image: LabelImage | None = None):
        self._system_rules = system_rules
        self._user_content = user_content
        self._image = image

    @property
    def system_rules(self) -> str:
        return self._system_rules

    @property
    def user_content(self) -> str:
        return self._user_content

    @property
    def image(self) -> LabelImage | None:
        return self._image

    def with_feedback(self, problem: str) -> "AIRequest":
        """Same request plus a note on why the last reply was rejected (used for the retry)."""
        note = ("\n\nYour previous reply was rejected because: " + problem
                + ". Reply again with ONLY the corrected JSON object.")
        return AIRequest(self._system_rules, self._user_content + note, self._image)


class AIResult:
    """A validated task result plus which provider produced it."""

    def __init__(self, value, provider: str):
        self._value = value
        self._provider = provider

    @property
    def value(self):
        return self._value

    @property
    def provider(self) -> str:
        return self._provider


class LabelReading:
    """Label values read from a photo. Shown to the user to check before analysis."""

    def __init__(self, readable: bool, product_fields: dict, notes: str | None):
        self._readable = readable
        self._product_fields = dict(product_fields)
        self._notes = notes

    @property
    def readable(self) -> bool:
        return self._readable

    @property
    def product_fields(self) -> dict:
        return dict(self._product_fields)

    @property
    def notes(self) -> str | None:
        return self._notes


class RecommendationAdvice:
    """AI reasons for each shortlisted product, general tips and other Singapore products."""

    def __init__(self, reasons: dict[int, str], tips: list[str],
                 suggested_products: list[ProductSuggestion] | None = None):
        self._reasons = dict(reasons)
        self._tips = list(tips)
        self._suggested_products = list(suggested_products or [])

    @property
    def suggested_products(self) -> list[ProductSuggestion]:
        return list(self._suggested_products)

    @property
    def reasons(self) -> dict[int, str]:
        return dict(self._reasons)

    @property
    def tips(self) -> list[str]:
        return list(self._tips)
