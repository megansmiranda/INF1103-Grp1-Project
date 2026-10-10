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


def run_tests():
    tests = [
        test_sugar_max_boundaries, test_protein_min_boundaries, test_sodium_max_boundaries,
        test_missing_value_is_not_zero, test_bad_internal_data_is_rejected,
        test_mismatch_ignores_ai_alignment, test_mismatch_plus_claim_review,
        test_low_confidence_goes_to_manual_review_not_claim_review,
        test_missing_nutrient_gives_manual_review, test_good_match_no_claim,
        test_good_match_consistent_claim, test_low_confidence_blocks_good_match,
        test_mixed_alignment_gives_no_flags, test_inputs_not_modified,
    ]
    for test in tests:
        test()
        io_manager.show_message("PASS  " + test.__name__)
    io_manager.show_message("\nAll {} logic tests passed.".format(len(tests)))


if __name__ == "__main__":
    run_tests()
