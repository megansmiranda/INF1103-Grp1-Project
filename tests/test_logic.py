"""Logic Manager: the Part 1 business rules (now for several goals), scoring and ranking.
Uses hardcoded AI answers, so no API is needed."""
import pytest

from conftest import (CALORIES_MAX_200, PROTEIN_MIN_15, SUGAR_MAX_10, ai_analysis, product,
                      profile)
from nutrilenz.domain.flag import Flag
from nutrilenz.domain.target_status import TargetStatus
from nutrilenz.domain.nutrients import Nutrient
from nutrilenz.domain.recommendation_focus import RecommendationFocus
from nutrilenz.domain.recommendation_options import RecommendationOptions
from nutrilenz.logic.logic_manager import LogicManager
from nutrilenz.logic.evaluation_context import EvaluationContext
from nutrilenz.logic.rule import Rule
from nutrilenz.domain.profile import Profile
from nutrilenz.ai.label_analysis_task import LabelAnalysisTask


def flags_for(logic, prod, prof, **ai_changes):
    return list(logic.evaluate(prod, prof, ai_analysis(**ai_changes)).flags)


class TestPart1Rules:
    def test_goal_mismatch(self, logic):
        assert Flag.GOAL_MISMATCH in flags_for(logic, product(), profile(SUGAR_MAX_10))

    def test_claim_review_needs_all_three_conditions(self, logic):
        prof = profile(SUGAR_MAX_10)
        # claim + QUESTIONABLE + HIGH -> review
        assert Flag.CLAIM_REVIEW in flags_for(logic, product(), prof)
        # no claim -> never (AI must then say NO_CLAIM)
        assert Flag.CLAIM_REVIEW not in flags_for(logic, product(marketing_claim=None), prof,
                                                  claim_status="NO_CLAIM")
        # claim judged consistent -> no review
        assert Flag.CLAIM_REVIEW not in flags_for(logic, product(), prof, claim_status="CONSISTENT")
        # LOW confidence -> manual review instead of claim review
        flags = flags_for(logic, product(), prof, confidence="LOW")
        assert Flag.CLAIM_REVIEW not in flags and Flag.MANUAL_REVIEW in flags

    @pytest.mark.parametrize("changes", [
        {"confidence": "LOW"},
        {"goal_alignment": "INSUFFICIENT_INFORMATION"},
        {"claim_status": "INSUFFICIENT_INFORMATION"},
    ])
    def test_manual_review_for_unsure_ai(self, logic, changes):
        assert Flag.MANUAL_REVIEW in flags_for(logic, product(), profile(SUGAR_MAX_10), **changes)

    def test_manual_review_for_missing_label_value(self, logic):
        missing_sugar = product(nutrition={"sugar_g": None, "protein_g": 5})
        flags = flags_for(logic, missing_sugar, profile(SUGAR_MAX_10))
        assert Flag.MANUAL_REVIEW in flags and Flag.GOAL_MISMATCH not in flags

    def test_good_match_only_when_everything_agrees(self, logic):
        low_sugar = product(nutrition={"sugar_g": 5, "calories_kcal": 150})
        good = dict(goal_alignment="ALIGNED", claim_status="CONSISTENT")
        assert flags_for(logic, low_sugar, profile(SUGAR_MAX_10), **good) == [Flag.GOOD_MATCH]
        # numbers fine but AI says MIXED -> no flags at all (not a good match)
        assert flags_for(logic, low_sugar, profile(SUGAR_MAX_10), goal_alignment="MIXED",
                         claim_status="CONSISTENT") == []

    def test_flags_come_in_fixed_order(self, logic):
        flags = flags_for(logic, product(nutrition={"sugar_g": 30, "calories_kcal": None}),
                          profile(SUGAR_MAX_10, CALORIES_MAX_200))
        assert flags == [Flag.GOAL_MISMATCH, Flag.CLAIM_REVIEW, Flag.MANUAL_REVIEW]


class TestMultipleGoals:
    def test_one_failed_goal_is_a_mismatch(self, logic):
        prod = product(nutrition={"sugar_g": 5, "calories_kcal": 250})
        evaluation = logic.evaluate(prod, profile(SUGAR_MAX_10, CALORIES_MAX_200), ai_analysis())
        statuses = [r.status for r in evaluation.goal_results]
        assert statuses == [TargetStatus.MET, TargetStatus.MISMATCH]
        assert Flag.GOAL_MISMATCH in evaluation.flags

    def test_good_match_needs_every_goal(self, logic):
        prod = product(nutrition={"sugar_g": 5, "calories_kcal": 150, "protein_g": 20})
        prof = profile(SUGAR_MAX_10, CALORIES_MAX_200, PROTEIN_MIN_15)
        flags = flags_for(logic, prod, prof, goal_alignment="ALIGNED", claim_status="NO_CLAIM")
        assert flags == [Flag.GOOD_MATCH]

    def test_single_goal_profile_behaves_like_part1(self, logic):
        # same input as Part 1's sample cereal: sugar 14 vs target 10 with a questionable claim
        assert flags_for(logic, product(), profile(SUGAR_MAX_10)) == [Flag.GOAL_MISMATCH, Flag.CLAIM_REVIEW]


class TestOpenClosedRules:
    def test_new_rule_can_be_added_without_changing_logic_manager(self):
        class AvoidedIngredientRule(Rule):
            @property
            def flag(self):
                return Flag.MANUAL_REVIEW

            def applies(self, context: EvaluationContext, flags_so_far):
                return bool(context.product.ingredients_found(["maltodextrin"]))

        logic = LogicManager(rules=[AvoidedIngredientRule()])
        flags = logic.evaluate(product(), profile(), ai_analysis(goal_alignment="ALIGNED")).flags
        assert flags == (Flag.MANUAL_REVIEW,)


class TestScoringAndWarnings:
    def test_score_range_and_penalties(self, logic):
        prof = profile(SUGAR_MAX_10)
        perfect = product(nutrition={"sugar_g": 5}, ingredient_text="Oats")
        assert logic.score(perfect, prof) == 100.0
        with_avoided = logic.score(perfect, profile(SUGAR_MAX_10, avoid=["oats"]))
        assert with_avoided == 75.0
        assert 0 <= logic.score(product(nutrition={"sugar_g": 999}), prof) <= 100

    def test_missing_value_scores_half(self, logic):
        assert logic.score(product(nutrition={"sugar_g": None}, ingredient_text="Oats"),
                           profile(SUGAR_MAX_10)) == 50.0

    def test_unusual_number_warning(self, logic):
        warnings = logic.check_unusual_numbers(product(nutrition={"sugar_g": 150, "sodium_mg": 200}))
        assert len(warnings) == 1 and "Sugar" in warnings[0]

    def test_warning_limits_are_configurable(self):
        strict = LogicManager(warning_limits={Nutrient.SODIUM: 100})
        assert strict.check_unusual_numbers(product(nutrition={"sodium_mg": 180}))
        with pytest.raises(ValueError):
            LogicManager(warning_limits={Nutrient.SODIUM: 0})


class TestRanking:
    def catalogue(self):
        items = [product(product_name="A", nutrition={"sugar_g": 2, "protein_g": 5}, category="Snack"),
                 product(product_name="B", nutrition={"sugar_g": 8, "protein_g": 25}, category="Snack"),
                 product(product_name="C", nutrition={"sugar_g": 1}, category="Drink",
                         ingredient_text="Water, peanuts"),
                 product(product_name="D", nutrition={"sugar_g": None, "protein_g": 30}, category="Snack")]
        for index, item in enumerate(items, start=1):
            item.assign_id(index)
        return items

    def names(self, ranked):
        return [s.product.name for s in ranked]

    def test_avoided_ingredients_are_left_out(self, logic):
        ranked = logic.rank(self.catalogue(), profile(SUGAR_MAX_10, avoid=["peanuts"]), RecommendationOptions())
        assert "C" not in self.names(ranked)

    def test_focus_orders_by_nutrient(self, logic):
        options = RecommendationOptions([RecommendationFocus.HIGHEST_PROTEIN])
        assert self.names(logic.rank(self.catalogue(), profile(SUGAR_MAX_10), options))[:2] == ["D", "B"]

    def test_focus_skips_products_without_that_value(self, logic):
        options = RecommendationOptions([RecommendationFocus.LOWEST_SUGAR])
        assert "D" not in self.names(logic.rank(self.catalogue(), profile(SUGAR_MAX_10), options))

    def test_several_focuses_are_combined(self, logic):
        # A is best on sugar only, B best on protein only; E is good at both, so E wins
        balanced = product(product_name="E", nutrition={"sugar_g": 3, "protein_g": 20}, category="Snack")
        balanced.assign_id(5)
        options = RecommendationOptions([RecommendationFocus.LOWEST_SUGAR, RecommendationFocus.HIGHEST_PROTEIN])
        names = self.names(logic.rank(self.catalogue() + [balanced], profile(SUGAR_MAX_10), options))
        assert names[0] == "E"
        assert "C" not in names and "D" not in names     # each is missing one of the two values

    def test_category_filter(self, logic):
        options = RecommendationOptions(categories=["drink"])
        assert self.names(logic.rank(self.catalogue(), profile(SUGAR_MAX_10), options)) == ["C"]

    def test_several_categories(self, logic):
        options = RecommendationOptions(categories=["Drink", "snack"])
        assert sorted(self.names(logic.rank(self.catalogue(), profile(SUGAR_MAX_10), options))) == ["A", "B", "C", "D"]

    def test_options_remove_duplicates_and_describe_themselves(self):
        options = RecommendationOptions([RecommendationFocus.LOWEST_SUGAR] * 2, ["Snack", "snack", "Any"])
        assert options.focuses == (RecommendationFocus.LOWEST_SUGAR,)
        assert options.categories == ("Snack",)
        assert options.describe_focus() == "Lowest sugar"
        same = RecommendationOptions([RecommendationFocus.LOWEST_SUGAR], ["SNACK"])
        assert options.cache_key() == same.cache_key()


class TestDietaryAnalysis:
    @pytest.mark.parametrize("checks", [["vegan"], ["dairy", "nuts"], ["vegetarian_no_dairy", "egg"], []])
    @pytest.mark.parametrize("text", ["Milk, almonds, eggs", "Coconut milk", ""])
    def test_dietary_selection_never_changes_score(self, checks, text):
        plain = self.evaluate(text, [], avoid=["milk"], sugar=13)
        chosen = self.evaluate(text, checks, avoid=["milk"], sugar=13)
        assert chosen.score == plain.score

    def test_ai_output_cannot_change_score(self, logic):
        prod = product(nutrition={"sugar_g": 13})
        prof = profile()
        assert logic.evaluate(prod, prof, ai_analysis(goal_alignment="ALIGNED")).score == 70
        assert logic.evaluate(prod, prof, ai_analysis(goal_alignment="POOR_ALIGNMENT")).score == 70

    def test_recommendation_filter_unknowns_exclusions_and_limit(self, logic):
        prof = Profile([SUGAR_MAX_10], dietary_checks=["dairy"])
        products = [product(product_name="Concern" + str(i), ingredient_text="Milk") for i in range(7)]
        products += [product(product_name="Unknown", ingredient_text=""),
                     product(product_name="Plant", ingredient_text="Coconut milk"),
                     product(product_name="Other category", ingredient_text="Milk", category="Spread")]
        picks, excluded = logic.recommendation_candidates(products, prof, RecommendationOptions(categories=["Cereal"]))
        assert [item.product.name for item in picks] == ["Unknown", "Plant"]
        assert len(excluded) == 7  # filter before applying the shortlist limit
        assert picks[0].ingredients_unknown
        assert picks[0].dietary_report.results[0].status.value == "NOT_CHECKED"
        assert all(item.dietary_report.has_concern for item in excluded)

    def evaluate(self, ingredients, checks, avoid=None, sugar=5):
        prod = product(ingredient_text=ingredients, nutrition={"sugar_g": sugar}, marketing_claim=None)
        prof = Profile([SUGAR_MAX_10], avoid or [], checks)
        ai = ai_analysis(goal_alignment="ALIGNED", claim_status="NO_CLAIM")
        return LogicManager().evaluate(prod, prof, ai)

    def test_concern_blocks_good_match_without_changing_score(self):
        result = self.evaluate("Gelatine, GELATINE, gelatine", ["vegan", "halal_friendly"])
        assert result.flags == (Flag.DIETARY_REVIEW,)
        assert result.score == 100 and result.dietary_report.score_penalty == 0
        assert result.dietary_report.concern_count == 2

    @pytest.mark.parametrize("text", ["Rice", ""])
    def test_no_match_and_missing_list_do_not_penalize_or_flag(self, text):
        result = self.evaluate(text, ["vegan", "dairy"])
        assert result.flags == (Flag.GOOD_MATCH,)
        assert result.score == 100 and result.dietary_report.score_penalty == 0

    @pytest.mark.parametrize("text,avoid", [("Milk", ["milk"]), ("MILK, milk", ["milk"]),
                                            ("Milk powder", ["milk"]), ("milk", ["ilk"]),
                                            ("Milk powder, milk", ["milk powder"]),
                                            ("Egg whites, egg yolk", ["egg whites"]),
                                            ("Skim milk, milks", ["skim milk"])])
    def test_avoid_hit_is_not_penalized_again(self, text, avoid):
        result = self.evaluate(text, ["vegan", "dairy", "egg"], avoid)
        assert result.score == 75  # existing avoid deduction only
        assert result.dietary_report.score_penalty == 0
        assert result.flags == (Flag.DIETARY_REVIEW,)

    def test_other_dietary_ingredients_do_not_add_adjustments(self):
        result = self.evaluate("Milk, pork, gelatine", ["vegan", "dairy", "halal_friendly"], ["milk"])
        assert result.score == 75 and result.dietary_report.score_penalty == 0

    def test_score_never_goes_below_zero(self):
        result = self.evaluate("Milk", ["vegan"], sugar=30)
        assert result.score == 0 and result.dietary_report.score_penalty == 0

    def test_no_selections_retains_flags_and_nutrition_score(self):
        prod = product(ingredient_text="Milk")
        old = Profile([SUGAR_MAX_10], ["milk"])
        chosen = Profile([SUGAR_MAX_10], ["milk"], ["dairy"])
        a = LabelAnalysisTask(prod, old).build_request()
        b = LabelAnalysisTask(prod, chosen).build_request()
        assert a.system_rules == b.system_rules and a.user_content != b.user_content
        result = LogicManager().evaluate(prod, old, ai_analysis())
        assert result.flags == (Flag.GOAL_MISMATCH, Flag.CLAIM_REVIEW)
        assert result.score == LogicManager().score(prod, old, ai_analysis())
        assert result.dietary_report.results == ()

    def test_recommendations_exclude_dietary_concerns(self):
        products = [product(product_name="Milk drink", ingredient_text="Milk", nutrition={"sugar_g": 5}),
                    product(product_name="Rice drink", ingredient_text="Rice", nutrition={"sugar_g": 8})]
        logic = LogicManager()
        before = logic.rank(products, Profile([SUGAR_MAX_10]), RecommendationOptions())
        after = logic.rank(products, Profile([SUGAR_MAX_10], dietary_checks=["vegan"]), RecommendationOptions())
        assert [p.product.name for p in before] == ["Milk drink", "Rice drink"]
        assert [p.product.name for p in after] == ["Rice drink"]
        assert after[0].score == before[1].score
