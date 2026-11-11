import math


class Amount:
    """Checks for nutrient amounts and targets."""

    @staticmethod
    def is_number(value: object) -> bool:
        """Finite int/float only. bool and numeric text are rejected."""
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (isinstance(value, float) and math.isfinite(value))
