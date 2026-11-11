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
