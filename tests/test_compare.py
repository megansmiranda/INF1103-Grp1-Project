"""Shelf Compare: Logic ranks 2-4 products, the AI explains the ranking in one call.
Uses fake AI replies, so no API key is needed."""
import pytest

from conftest import CALORIES_MAX_200, SUGAR_MAX_10, product, profile
from nutrilenz.ai.comparison_task import ComparisonTask
from nutrilenz.domain.profile import Profile

LOW_SUGAR = {"product_name": "Plain Oats", "nutrition": {"sugar_g": 1.0, "calories_kcal": 150.0},
             "ingredient_text": "Whole grain oats", "marketing_claim": None}
HIGH_SUGAR = {"product_name": "Choco Puffs", "nutrition": {"sugar_g": 18.0, "calories_kcal": 230.0},
              "ingredient_text": "Corn, sugar, cocoa", "marketing_claim": None}


def advice(count=2, **changes) -> dict:
    answer = {"summary": "Plain Oats fits best: far less sugar and fewer calories.",
              "notes": [{"item": n, "strength": f"Point {n} in favour.", "drawback": f"Point {n} to check."}
                        for n in range(1, count + 1)]}
    answer.update(changes)
    return answer


def ranked_pair(logic):
    return logic.compare([product(**HIGH_SUGAR), product(**LOW_SUGAR)], profile(SUGAR_MAX_10, CALORIES_MAX_200))


class TestLogicRanking:
    def test_best_goal_fit_comes_first(self, logic):
        ranked = ranked_pair(logic)
        assert [item.product.name for item in ranked] == ["Plain Oats", "Choco Puffs"]
        assert ranked[0].score > ranked[1].score

    def test_dietary_concern_never_wins(self, logic):
        dairy_low_sugar = product(product_name="Milk Oats", ingredient_text="Oats, milk powder",
                                  nutrition={"sugar_g": 1.0, "calories_kcal": 150.0})
        plain_high_sugar = product(**HIGH_SUGAR)
        ranked = logic.compare([dairy_low_sugar, plain_high_sugar],
                               Profile([SUGAR_MAX_10], [], ["dairy"]))
        assert ranked[0].product.name == "Choco Puffs"
        assert ranked[1].dietary_report.has_concern and ranked[1].score > ranked[0].score

    def test_avoided_ingredient_never_wins_even_with_better_numbers(self, logic):
        palm_low_sugar = product(product_name="Palm Flakes", ingredient_text="Corn, palm oil",
                                 nutrition={"sugar_g": 0.5, "calories_kcal": 120.0})
        clean_higher_sugar = product(product_name="Corn Flakes", ingredient_text="Corn, salt",
                                     nutrition={"sugar_g": 9.0, "calories_kcal": 190.0})
        ranked = logic.compare([palm_low_sugar, clean_higher_sugar],
                               profile(SUGAR_MAX_10, CALORIES_MAX_200, avoid=["palm oil"]))
        assert [item.product.name for item in ranked] == ["Corn Flakes", "Palm Flakes"]

    def test_avoided_products_are_kept_but_score_lower(self, logic):
        ranked = logic.compare([product(**LOW_SUGAR), product(**dict(LOW_SUGAR, product_name="Palm Oats",
                                                                     ingredient_text="Oats, palm oil"))],
                               profile(SUGAR_MAX_10, avoid=["palm oil"]))
        assert [item.product.name for item in ranked] == ["Plain Oats", "Palm Oats"]


class TestComparisonTask:
    def test_request_sends_products_in_ranked_order(self, logic):
        request = ComparisonTask(profile(SUGAR_MAX_10), ranked_pair(logic)).build_request()
        assert request.user_content.index('"item": 1') < request.user_content.index('"item": 2')
        assert request.user_content.index("Plain Oats") < request.user_content.index("Choco Puffs")
        assert "app_score" in request.user_content and "Never change this order" in request.system_rules

    def test_valid_reply(self, logic):
        result = ComparisonTask(profile(SUGAR_MAX_10), ranked_pair(logic)).parse(advice())
        assert result.summary.startswith("Plain Oats") and result.drawback(2) == "Point 2 to check."

    @pytest.mark.parametrize("notes", [
        [{"item": 1, "strength": "a", "drawback": "b"}],                                          # one missing
        [{"item": 1, "strength": "a", "drawback": "b"}, {"item": 1, "strength": "a", "drawback": "b"}],
        [{"item": 1, "strength": "a", "drawback": "b"}, {"item": 3, "strength": "a", "drawback": "b"}],
        [{"item": 1, "strength": "a", "drawback": "b"}, {"item": True, "strength": "a", "drawback": "b"}],
        [{"item": 1, "strength": "a"}, {"item": 2, "strength": "a", "drawback": "b"}],
    ])
    def test_bad_notes_are_rejected(self, logic, notes):
        with pytest.raises(ValueError):
            ComparisonTask(profile(SUGAR_MAX_10), ranked_pair(logic)).parse(advice(notes=notes))

    def test_unsafe_wording_and_extra_fields_are_rejected(self, logic):
        task = ComparisonTask(profile(SUGAR_MAX_10), ranked_pair(logic))
        with pytest.raises(ValueError):
            task.parse(advice(summary="Plain Oats is safe for you."))
        with pytest.raises(ValueError):
            task.parse(dict(advice(), winner=2))

    def test_needs_two_products(self, logic):
        with pytest.raises(ValueError):
            ComparisonTask(profile(SUGAR_MAX_10), ranked_pair(logic)[:1])
