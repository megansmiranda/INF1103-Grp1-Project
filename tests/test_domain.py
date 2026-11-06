"""Domain classes: goals, products, profiles and users."""
import pytest

from conftest import CALORIES_MAX_200, PROTEIN_MIN_15, SUGAR_MAX_10, product, profile
from nutrilenz.domain.goals import Goal, GoalFactory, LimitGoal, MinimumGoal, TargetStatus
from nutrilenz.domain.nutrients import Nutrient
from nutrilenz.domain.product import NutritionFacts


class TestGoals:
    def test_goal_is_abstract(self):
        with pytest.raises(TypeError):
            Goal(Nutrient.SUGAR, 10)

    def test_limit_goal_equal_counts_as_met(self):
        goal = LimitGoal(Nutrient.SUGAR, 10)
        assert goal.evaluate(NutritionFacts({Nutrient.SUGAR: 10})) is TargetStatus.MET
        assert goal.evaluate(NutritionFacts({Nutrient.SUGAR: 10.1})) is TargetStatus.MISMATCH

    def test_minimum_goal_equal_counts_as_met(self):
        goal = MinimumGoal(Nutrient.PROTEIN, 15)
        assert goal.evaluate(NutritionFacts({Nutrient.PROTEIN: 15})) is TargetStatus.MET
        assert goal.evaluate(NutritionFacts({Nutrient.PROTEIN: 14.9})) is TargetStatus.MISMATCH

    def test_missing_value_is_not_zero(self):
        # Part 1 rule kept: a blank label value is MISSING, never treated as 0
        goal = LimitGoal(Nutrient.SUGAR, 10)
        assert goal.evaluate(NutritionFacts({Nutrient.SUGAR: None})) is TargetStatus.MISSING
        assert goal.evaluate(NutritionFacts({})) is TargetStatus.MISSING

    @pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True, "10"])
    def test_bad_targets_rejected(self, bad):
        with pytest.raises(ValueError):
            LimitGoal(Nutrient.SUGAR, bad)

    def test_factory_builds_right_subclass(self):
        assert isinstance(GoalFactory.create("sugar_g", "MAX", 10), LimitGoal)
        assert isinstance(GoalFactory.create("fibre_g", "MIN", 5), MinimumGoal)
        assert isinstance(GoalFactory.from_preset("LOW_CALORIES", 200), LimitGoal)
        with pytest.raises(ValueError):
            GoalFactory.create("sugar_g", "SIDEWAYS", 10)
        with pytest.raises(ValueError):
            GoalFactory.create("vitamin_q", "MAX", 10)

    def test_part1_goals_are_presets(self):
        for name in ("REDUCE_SUGAR", "HIGH_PROTEIN", "LOWER_SODIUM"):
            assert name in GoalFactory.PRESETS

    def test_closeness_used_for_scoring(self):
        assert LimitGoal(Nutrient.SUGAR, 10).closeness(5) == 1.0
        assert LimitGoal(Nutrient.SUGAR, 10).closeness(15) == pytest.approx(0.5)
        assert MinimumGoal(Nutrient.PROTEIN, 20).closeness(10) == pytest.approx(0.5)


class TestProductAndProfile:
    def test_negative_nutrition_rejected(self):
        with pytest.raises(ValueError):
            NutritionFacts({Nutrient.SUGAR: -1})

    def test_product_requires_name_and_ingredients(self):
        with pytest.raises(ValueError):
            product(product_name=" ")
        with pytest.raises(ValueError):
            product(ingredient_text="")

    def test_blank_claim_means_no_claim(self):
        assert not product(marketing_claim="   ").has_claim

    def test_ingredients_found_ignores_case(self):
        assert product().ingredients_found(["MALTODEXTRIN", "peanuts"]) == ["MALTODEXTRIN"]

    def test_product_round_trip(self):
        original = product(brand="GoodGrain")
        copy = type(original).from_dict(original.to_dict())
        assert copy.to_dict() == original.to_dict()

    def test_profile_owns_goals_and_rejects_duplicates(self):
        p = profile(SUGAR_MAX_10, CALORIES_MAX_200)
        assert [g.nutrient for g in p.goals] == [Nutrient.SUGAR, Nutrient.CALORIES]
        with pytest.raises(ValueError):
            profile(SUGAR_MAX_10, {"nutrient": "sugar_g", "direction": "MAX", "target": 5})
        with pytest.raises(ValueError):
            profile().replace_goals([])

    def test_goals_cannot_be_changed_from_outside(self):
        p = profile(SUGAR_MAX_10)
        assert isinstance(p.goals, tuple)

    def test_snapshot_is_a_copy(self):
        p = profile(SUGAR_MAX_10, PROTEIN_MIN_15, avoid=["peanuts"])
        snap = p.snapshot()
        p.replace_goals([CALORIES_MAX_200])
        assert snap["goals"][0]["nutrient"] == "sugar_g"
        assert snap["avoid_ingredients"] == ["peanuts"]

    def test_avoid_list_is_cleaned(self):
        p = profile(avoid=[" Peanuts ", "peanuts", "", "MSG"])
        assert p.avoid_ingredients == ("Peanuts", "MSG")
