from .label_image import LabelImage


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
