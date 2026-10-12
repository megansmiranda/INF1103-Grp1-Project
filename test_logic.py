"""
test_logic.py - REQUIRED API-free tests for the Logic Manager

Uses hardcoded AI responses from sample_data.py, so it needs NO internet and NO API key.
Run:  python test_logic.py
A failed check stops with an AssertionError (non-zero exit code).
"""

from copy import deepcopy

import io_manager
import logic_manager
from sample_data import SAMPLE_PROFILES, SAMPLE_PRODUCTS, SAMPLE_AI_RESPONSES


def make(product_key, profile_key, ai_key):
    """Return fresh copies so one test cannot affect another."""
    return (deepcopy(SAMPLE_PRODUCTS[product_key]),
            deepcopy(SAMPLE_PROFILES[profile_key]),
            deepcopy(SAMPLE_AI_RESPONSES[ai_key]))


# ---------------------------------------------------------------------------
# Person A: numeric target checks (below / equal / above / missing / zero)
# ---------------------------------------------------------------------------

def test_sugar_max_boundaries():
    product, profile, _ = make("cereal", "jane", "aligned_no_claim")   # max 10 g
    for value, expected in ((9.0, "MET"), (10.0, "MET"), (14.0, "MISMATCH"), (0.0, "MET")):
        product["nutrition"]["sugar_g"] = value
        assert logic_manager.evaluate_target(product, profile) == expected


def test_protein_min_boundaries():
    product, profile, _ = make("protein_bar", "sam", "aligned_no_claim")  # min 15 g
    for value, expected in ((9.0, "MISMATCH"), (15.0, "MET"), (18.0, "MET"), (0.0, "MISMATCH")):
        product["nutrition"]["protein_g"] = value
        assert logic_manager.evaluate_target(product, profile) == expected


def test_sodium_max_boundaries():
    product, profile, _ = make("noodles", "ari", "aligned_no_claim")    # max 400 mg
    for value, expected in ((300.0, "MET"), (400.0, "MET"), (520.0, "MISMATCH")):
        product["nutrition"]["sodium_mg"] = value
        assert logic_manager.evaluate_target(product, profile) == expected


def test_missing_value_is_not_zero():
    product, profile, _ = make("missing_sugar", "jane", "aligned_no_claim")
    assert logic_manager.evaluate_target(product, profile) == "MISSING"


def test_bad_internal_data_is_rejected():
    product, profile, _ = make("cereal", "jane", "aligned_no_claim")
    profile["target_unit"] = "mg_per_serving"           # wrong unit for sugar
    try:
        logic_manager.evaluate_target(product, profile)
        raise AssertionError("unit mismatch should raise ValueError")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Person B: combined flags (the worked examples from our proposal)
# ---------------------------------------------------------------------------

def test_mismatch_ignores_ai_alignment():
    # Sugar 14 > 10. AI says ALIGNED, but the numbers win.
    product, profile, ai = make("cereal", "jane", "aligned_no_claim")
    product["marketing_claim"] = None
    assert logic_manager.evaluate_product(product, profile, ai) == ["GOAL_MISMATCH"]


def test_mismatch_plus_claim_review():
    product, profile, ai = make("cereal", "jane", "questionable_high")
    assert logic_manager.evaluate_product(product, profile, ai) == ["GOAL_MISMATCH", "CLAIM_REVIEW"]


def test_low_confidence_goes_to_manual_review_not_claim_review():
    product, profile, ai = make("cereal", "jane", "questionable_low")
    assert logic_manager.evaluate_product(product, profile, ai) == ["GOAL_MISMATCH", "MANUAL_REVIEW"]


def test_missing_nutrient_gives_manual_review():
    product, profile, ai = make("missing_sugar", "jane", "questionable_high")
    assert logic_manager.evaluate_product(product, profile, ai) == ["CLAIM_REVIEW", "MANUAL_REVIEW"]


def test_good_match_no_claim():
    product, profile, ai = make("protein_bar", "sam", "aligned_no_claim")
    product["marketing_claim"] = None
    assert logic_manager.evaluate_product(product, profile, ai) == ["GOOD_MATCH"]


def test_good_match_consistent_claim():
    product, profile, ai = make("protein_bar", "sam", "aligned_consistent")
    assert logic_manager.evaluate_product(product, profile, ai) == ["GOOD_MATCH"]


def test_low_confidence_blocks_good_match():
    product, profile, ai = make("protein_bar", "sam", "aligned_no_claim")
    product["marketing_claim"] = None
    ai["confidence"] = "LOW"
    assert logic_manager.evaluate_product(product, profile, ai) == ["MANUAL_REVIEW"]


def test_mixed_alignment_gives_no_flags():
    product, profile, ai = make("protein_bar", "sam", "mixed_consistent")
    assert logic_manager.evaluate_product(product, profile, ai) == []


def test_inputs_not_modified():
    product, profile, ai = make("cereal", "jane", "questionable_high")
    before = deepcopy((product, profile, ai))
    logic_manager.evaluate_product(product, profile, ai)
    assert (product, profile, ai) == before


# ---------------------------------------------------------------------------
# Each public logic_manager function tested on its own
# ---------------------------------------------------------------------------

def expect_value_error(function, *args):
    """Helper: assert that calling function(*args) raises ValueError."""
    try:
        function(*args)
    except ValueError:
        return
    raise AssertionError(function.__name__ + " should have raised ValueError")


def test_get_goal_rule():
    assert logic_manager.get_goal_rule("REDUCE_SUGAR")["direction"] == "MAX"
    assert logic_manager.get_goal_rule("HIGH_PROTEIN")["nutrient_key"] == "protein_g"
    assert logic_manager.get_goal_rule("LOWER_SODIUM")["unit"] == "mg_per_serving"
    expect_value_error(logic_manager.get_goal_rule, "LOSE_WEIGHT")      # unknown goal


def test_needs_manual_review():
    ai = deepcopy(SAMPLE_AI_RESPONSES["aligned_no_claim"])             # HIGH, ALIGNED, NO_CLAIM
    assert logic_manager.needs_manual_review("MET", ai) is False
    assert logic_manager.needs_manual_review("MISSING", ai) is True     # value not on label
    ai["confidence"] = "LOW"
    assert logic_manager.needs_manual_review("MET", ai) is True
    ai = deepcopy(SAMPLE_AI_RESPONSES["aligned_no_claim"])
    ai["claim_status"] = "INSUFFICIENT_INFORMATION"
    assert logic_manager.needs_manual_review("MET", ai) is True


def test_needs_claim_review_needs_all_three_conditions():
    product = deepcopy(SAMPLE_PRODUCTS["cereal"])                       # has a claim
    ai = deepcopy(SAMPLE_AI_RESPONSES["questionable_high"])             # QUESTIONABLE + HIGH
    assert logic_manager.needs_claim_review(product, ai) is True
    ai["confidence"] = "MEDIUM"
    assert logic_manager.needs_claim_review(product, ai) is True
    ai["confidence"] = "LOW"                                            # low confidence -> no
    assert logic_manager.needs_claim_review(product, ai) is False
    ai = deepcopy(SAMPLE_AI_RESPONSES["questionable_high"])
    product["marketing_claim"] = "   "                                  # blank claim -> no
    assert logic_manager.needs_claim_review(product, ai) is False


def test_is_good_match_gate():
    ai = deepcopy(SAMPLE_AI_RESPONSES["aligned_consistent"])
    assert logic_manager.is_good_match("MET", False, False, ai) is True
    assert logic_manager.is_good_match("MISMATCH", False, False, ai) is False
    assert logic_manager.is_good_match("MET", True, False, ai) is False   # manual review
    assert logic_manager.is_good_match("MET", False, True, ai) is False   # claim review
    ai["goal_alignment"] = "MIXED"
    assert logic_manager.is_good_match("MET", False, False, ai) is False


def test_check_unusual_numbers():
    product = deepcopy(SAMPLE_PRODUCTS["noodles"])                      # sodium 1450 mg
    assert logic_manager.check_unusual_numbers(product) == []           # no limits -> no warnings
    warnings = logic_manager.check_unusual_numbers(product, {"sodium_mg": 1000})
    assert len(warnings) == 1 and "Sodium" in warnings[0]
    assert logic_manager.check_unusual_numbers(product, {"sodium_mg": 2000}) == []
    missing = deepcopy(SAMPLE_PRODUCTS["missing_sugar"])                # None is skipped
    assert logic_manager.check_unusual_numbers(missing, {"sugar_g": 1}) == []
    expect_value_error(logic_manager.check_unusual_numbers, product, {"fat_g": 10})
    expect_value_error(logic_manager.check_unusual_numbers, product, {"sodium_mg": -5})
    product["nutrition"]["sugar_g"] = -1                                # bad label data
    expect_value_error(logic_manager.check_unusual_numbers, product)


def run_tests():
    tests = [
        test_sugar_max_boundaries, test_protein_min_boundaries, test_sodium_max_boundaries,
        test_missing_value_is_not_zero, test_bad_internal_data_is_rejected,
        test_mismatch_ignores_ai_alignment, test_mismatch_plus_claim_review,
        test_low_confidence_goes_to_manual_review_not_claim_review,
        test_missing_nutrient_gives_manual_review, test_good_match_no_claim,
        test_good_match_consistent_claim, test_low_confidence_blocks_good_match,
        test_mixed_alignment_gives_no_flags, test_inputs_not_modified,
        test_get_goal_rule, test_needs_manual_review,
        test_needs_claim_review_needs_all_three_conditions, test_is_good_match_gate,
        test_check_unusual_numbers,
    ]
    for test in tests:
        test()
        io_manager.show_message("PASS  " + test.__name__)
    io_manager.show_message("\nAll {} logic tests passed.".format(len(tests)))


if __name__ == "__main__":
    run_tests()
