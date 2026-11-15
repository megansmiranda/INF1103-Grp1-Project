"""Shelf Compare: Logic ranks 2-4 products, the AI explains the ranking in one call.
Uses fake AI replies, so no API key is needed."""
from conftest import CALORIES_MAX_200, SUGAR_MAX_10, product, profile
from nutrilenz.domain.profile import Profile

LOW_SUGAR = {"product_name": "Plain Oats", "nutrition": {"sugar_g": 1.0, "calories_kcal": 150.0},
             "ingredient_text": "Whole grain oats", "marketing_claim": None}
HIGH_SUGAR = {"product_name": "Choco Puffs", "nutrition": {"sugar_g": 18.0, "calories_kcal": 230.0},
              "ingredient_text": "Corn, sugar, cocoa", "marketing_claim": None}


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
