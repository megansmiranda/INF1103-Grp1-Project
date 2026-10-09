"""
logic_manager.py - LOGIC LAYER (owner: Logic Person A)

Map goals, compare the selected nutrient and check unusual nutrition values.
evaluate_target() returns MET, MISMATCH or MISSING without inspecting AI output.
Invalid internal data raises ValueError with a reason for main.py to pass to I/O.
Unusual-value warnings use team-agreed limits supplied by the caller.

Person B's review rules and evaluate_product() must be added during team
integration before the full application can produce final analysis flags.
No printing, keyboard input, API calls or file access here.
"""

import math

# Goal -> which nutrient to check, and whether the target is a MAX or a MIN
GOAL_RULES = {
    "REDUCE_SUGAR": {"nutrient_key": "sugar_g", "direction": "MAX", "unit": "g_per_serving"},
    "HIGH_PROTEIN": {"nutrient_key": "protein_g", "direction": "MIN", "unit": "g_per_serving"},
    "LOWER_SODIUM": {"nutrient_key": "sodium_mg", "direction": "MAX", "unit": "mg_per_serving"},
}


# ===========================================================================
# PERSON A: numeric target check (does NOT look at AI output at all)
# ===========================================================================

def get_goal_rule(primary_goal):
    """Return a copy of the goal rule. Unsupported goals raise ValueError."""
    if not isinstance(primary_goal, str) or primary_goal not in GOAL_RULES:
        raise ValueError("Unknown goal: " + str(primary_goal))
    return GOAL_RULES[primary_goal].copy()


def _is_number(value):
    """Accept finite int/float values, excluding bool and numeric text."""
    if isinstance(value, bool):
        return False
    # Integers are finite; converting a very large int to float can overflow.
    return isinstance(value, int) or (isinstance(value, float) and math.isfinite(value))


def _require_fields(data, fields, name):
    """Reject malformed dictionaries with a field-specific integration error."""
    if not isinstance(data, dict):
        raise ValueError(name + " must be a dictionary")
    for field in fields:
        if field not in data:
            raise ValueError("Missing required field: " + name + "." + field)


def _get_nutrition(product):
    """Read the nutrition dictionary without changing the product."""
    _require_fields(product, ("nutrition",), "product")
    nutrition = product["nutrition"]
    _require_fields(nutrition, (), "product.nutrition")
    return nutrition


def _get_nutrient_value(nutrition, nutrient_key):
    """A required key may contain None, but must not be absent or invalid."""
    _require_fields(nutrition, (nutrient_key,), "product.nutrition")
    value = nutrition[nutrient_key]
    if value is not None and (not _is_number(value) or value < 0):
        raise ValueError("product.nutrition." + nutrient_key
                         + " must be a finite non-negative number or None")
    return value


def evaluate_target(product, profile):
    """Compare the selected nutrient with the user's target.

    Return MET, MISMATCH or MISSING (a present nutrient key containing None).
    Missing required keys and invalid values raise ValueError, not MISSING.
    Check only the selected nutrient, in its agreed per-serving unit.
    Neither input is modified; meeting the target alone is not GOOD_MATCH.
    """
    _require_fields(profile, ("primary_goal", "target_unit", "target_value"), "profile")
    rule = get_goal_rule(profile["primary_goal"])

    # Defensive checks: these catch broken data passed between managers
    if profile["target_unit"] != rule["unit"]:
        raise ValueError("profile.target_unit must be " + rule["unit"]
                         + " for " + profile["primary_goal"])
    target = profile["target_value"]
    if not _is_number(target) or target <= 0:
        raise ValueError("profile.target_value must be a finite positive number")

    nutrition = _get_nutrition(product)
    value = _get_nutrient_value(nutrition, rule["nutrient_key"])
    if value is None:
        return "MISSING"            # missing is NOT zero - we cannot compare

    # Equal to the target counts as meeting it
    if rule["direction"] == "MAX":
        return "MISMATCH" if value > target else "MET"
    return "MISMATCH" if value < target else "MET"


# ===========================================================================
# PERSON A: unusual-number warnings (for main.py to call before the AI step)
# ===========================================================================

def check_unusual_numbers(product, warning_limits=None):
    """Validate all three nutrients and return a list of warning messages.

    warning_limits is a dictionary of nutrient keys to team-agreed positive
    limits per serving: sugar_g/protein_g in grams, sodium_mg in milligrams.
    A value strictly above its configured limit produces a warning, not a
    rejection or a flag. None values are skipped and zero remains valid.

    With None or {} as limits, only validate the data; no high-value warnings
    are enabled. The PDF does not approve any default numerical thresholds.
    Partial limits check only the configured nutrients for unusual values.
    No serving mass or physical limits are assumed, and no units are converted.

    Malformed data or limits raise ValueError. main.py should pass errors and
    warnings to I/O for correction/confirmation before calling AI. This function
    does not change the product, limits, or numeric target status.
    """
    nutrition = _get_nutrition(product)
    values = {}
    units = {}
    for rule in GOAL_RULES.values():
        key = rule["nutrient_key"]
        values[key] = _get_nutrient_value(nutrition, key)
        units[key] = rule["unit"].replace("_", " ")

    if warning_limits is None:
        warning_limits = {}
    _require_fields(warning_limits, (), "warning_limits")
    for key, limit in warning_limits.items():
        if key not in values:
            raise ValueError("Unknown nutrient in warning_limits: " + str(key))
        if not _is_number(limit) or limit <= 0:
            raise ValueError("warning_limits." + key + " must be a finite positive number")

    warnings = []
    for key, value in values.items():
        if value is not None and key in warning_limits and value > warning_limits[key]:
            nutrient_name = key.rsplit("_", 1)[0].capitalize()
            warnings.append(
                nutrient_name + " (" + str(value) + " " + units[key]
                + ") exceeds the configured warning limit of "
                + str(warning_limits[key]) + " " + units[key] + ". "
                + "This value seems unusually high for one serving. "
                + "Check grams versus milligrams and per-serving versus per-100-g/ml "
                + "values; correct or confirm the label value."
            )
    return warnings
