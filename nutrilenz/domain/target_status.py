from enum import Enum


class TargetStatus(Enum):
    MET = "MET"
    MISMATCH = "MISMATCH"
    MISSING = "MISSING"          # nutrient not on the label, so it cannot be compared
