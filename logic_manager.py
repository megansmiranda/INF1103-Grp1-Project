"""
logic_manager.py - LOGIC LAYER  (owner: Logic Person A + Person B)

The "domain brain". It takes the AI-enriched record and applies deterministic
business rules to decide the final FLAGS:

  GOAL_MISMATCH  - product fails the user's numeric target (AI cannot override this)
  CLAIM_REVIEW   - claim given AND AI says QUESTIONABLE AND confidence MEDIUM/HIGH
                   (this is our required multi-condition rule on AI fields)
  MANUAL_REVIEW  - LOW confidence, missing nutrient, or AI says INSUFFICIENT_INFORMATION
  GOOD_MATCH     - target met AND no review needed AND AI says ALIGNED
                   AND claim is CONSISTENT or NO_CLAIM

The AI never decides the outcome; it only supplies fields that these rules read.
No printing, no keyboard input, no API calls, no file access here.
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
    """Return the rule dictionary for a goal. Unknown goal -> ValueError."""
    if primary_goal not in GOAL_RULES:
        raise ValueError("Unknown goal: " + str(primary_goal))
    return GOAL_RULES[primary_goal]


def _is_number(value):
    """True for int/float that are finite. (bool is excluded on purpose.)"""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def evaluate_target(product, profile):
    """Compare the selected nutrient with the user's target.
    Returns "MET", "MISMATCH" or "MISSING" (value not on the label)."""
    rule = get_goal_rule(profile["primary_goal"])

    # Defensive checks: these catch broken data passed between managers
    if profile["target_unit"] != rule["unit"]:
        raise ValueError("target_unit does not match the goal")
    target = profile["target_value"]
    if not _is_number(target) or target <= 0:
        raise ValueError("target_value must be a positive number")

    value = product["nutrition"][rule["nutrient_key"]]
    if value is None:
        return "MISSING"            # missing is NOT zero - we cannot compare
    if not _is_number(value) or value < 0:
        raise ValueError("nutrition value must be a non-negative number or None")

    # Equal to the target counts as meeting it
    if rule["direction"] == "MAX":
        return "MISMATCH" if value > target else "MET"
    return "MISMATCH" if value < target else "MET"


# ===========================================================================
# PERSON B: rules that use the AI fields
# ===========================================================================

def needs_manual_review(target_status, ai_analysis):
    """True when we cannot give a reliable automatic answer."""
    return (target_status == "MISSING"
            or ai_analysis["confidence"] == "LOW"
            or ai_analysis["goal_alignment"] == "INSUFFICIENT_INFORMATION"
            or ai_analysis["claim_status"] == "INSUFFICIENT_INFORMATION")


def needs_claim_review(product, ai_analysis):
    """MULTI-CONDITION RULE - all three must be true:
       1. the user supplied a marketing claim
       2. the AI classed it as QUESTIONABLE
       3. the AI is MEDIUM or HIGH confidence (LOW goes to MANUAL_REVIEW instead)"""
    claim = product["marketing_claim"]
    has_claim = isinstance(claim, str) and bool(claim.strip())
    return (has_claim
            and ai_analysis["claim_status"] == "QUESTIONABLE"
            and ai_analysis["confidence"] in ("MEDIUM", "HIGH"))


def is_good_match(target_status, manual, claim_review, ai_analysis):
    """Positive result only when EVERYTHING agrees."""
    return (target_status == "MET"
            and not manual
            and not claim_review
            and ai_analysis["goal_alignment"] == "ALIGNED"
            and ai_analysis["claim_status"] in ("CONSISTENT", "NO_CLAIM"))


# ===========================================================================
# The ONE function main.py calls
# ===========================================================================

def evaluate_product(product, profile, ai_analysis):
    """Apply all rules and return the list of flags, e.g. ["GOAL_MISMATCH", "CLAIM_REVIEW"].
    Several flags can appear together because they describe different concerns.
    An empty list means: nothing wrong was proven, but no GOOD_MATCH either
    (for example the AI said MIXED)."""
    target_status = evaluate_target(product, profile)
    manual = needs_manual_review(target_status, ai_analysis)
    claim_review = needs_claim_review(product, ai_analysis)

    flags = []
    if target_status == "MISMATCH":
        flags.append("GOAL_MISMATCH")
    if claim_review:
        flags.append("CLAIM_REVIEW")
    if manual:
        flags.append("MANUAL_REVIEW")
    if is_good_match(target_status, manual, claim_review, ai_analysis):
        flags.append("GOOD_MATCH")
    return flags
