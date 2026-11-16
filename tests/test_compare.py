"""Shelf Compare: Logic ranks 2-4 products, the AI explains the ranking in one call.
Uses fake AI replies, so no API key is needed."""
import io
import time

import pytest

from conftest import CALORIES_MAX_200, SUGAR_MAX_10, Replies, make_ai, product, profile
from test_web import Browser, build_app
from nutrilenz.ai.comparison_task import ComparisonTask
from nutrilenz.domain.comparison import Comparison
from nutrilenz.domain.nutrients import Nutrient
from nutrilenz.domain.profile import Profile
from nutrilenz.domain.user import User
from nutrilenz.errors.ai_error import AIError
from nutrilenz.services.comparison_service import ComparisonService
from nutrilenz.services.job import Job

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

    def test_request_explains_why_a_lower_score_can_win(self, logic):
        dairy_low_sugar = product(product_name="Milk Oats", ingredient_text="Oats, milk powder",
                                  nutrition={"sugar_g": 1.0, "calories_kcal": 150.0})
        user_profile = Profile([SUGAR_MAX_10], [], ["dairy"])
        ranked = logic.compare([dairy_low_sugar, product(**HIGH_SUGAR)], user_profile)
        request = ComparisonTask(user_profile, ranked).build_request()
        assert '"has_concern": false' in request.user_content
        assert '"has_concern": true' in request.user_content
        assert '"status": "MISMATCH"' in request.user_content
        assert "ranks below every product without one" in request.system_rules

    def test_summary_must_name_the_ranked_winner(self, logic):
        task = ComparisonTask(profile(SUGAR_MAX_10), ranked_pair(logic))
        with pytest.raises(ValueError, match="item 1"):
            task.parse(advice(summary="Choco Puffs is the best fit for your goals."))
        assert task.parse(advice(summary="plain oats wins on sugar.")).summary == "plain oats wins on sugar."


class TestComparisonService:
    def user(self) -> User:
        return User("jane", "hash", [SUGAR_MAX_10, CALORIES_MAX_200], [], user_id=1)

    def test_logic_ranks_and_ai_is_called_once(self, logic):
        ai, gemini, _ = make_ai(Replies.gemini(advice()))
        job = Job(1, "comparison", [])
        comparison = ComparisonService(ai, logic).compare(
            self.user(), [product(**HIGH_SUGAR), product(**LOW_SUGAR)], job)
        assert gemini.calls == 1
        assert comparison.winner.product.name == "Plain Oats" and comparison.provider == "gemini"
        assert comparison.strength(1) == "Point 1 in favour."

    def test_ai_failure_is_reported(self, logic):
        ai, _, _ = make_ai(AIError("API_UNAVAILABLE"), AIError("API_UNAVAILABLE"))
        with pytest.raises(AIError):
            ComparisonService(ai, logic).compare(self.user(), [product(**HIGH_SUGAR), product(**LOW_SUGAR)])

    @pytest.mark.parametrize("count", [1, 5])
    def test_two_to_four_products_only(self, logic, count):
        ai, gemini, _ = make_ai()
        with pytest.raises(ValueError):
            ComparisonService(ai, logic).compare(self.user(), [product(**LOW_SUGAR)] * count)
        assert gemini.calls == 0


class TestComparisonDomain:
    def test_goal_rows_line_up_by_goal(self, logic):
        comparison = Comparison(1, ranked_pair(logic), "s", {1: "a", 2: "b"}, {1: "c", 2: "d"}, "gemini")
        rows = comparison.goal_rows()
        assert [label for label, _ in rows] == ["Sugar at most 10 g per serving",
                                                "Calories at most 200 kcal per serving"]
        assert rows[0][1][0].value == 1.0 and rows[0][1][1].value == 18.0

    def test_winner_is_not_clean_when_every_product_has_a_problem(self, logic):
        user_profile = profile(SUGAR_MAX_10, avoid=["sugar"])
        ranked = logic.compare([product(**HIGH_SUGAR), product(**dict(LOW_SUGAR, ingredient_text="Oats, sugar"))],
                               user_profile)
        matches = {rank: item.product.ingredients_found(["sugar"]) for rank, item in enumerate(ranked, 1)}
        comparison = Comparison(1, ranked, "s", {}, {}, "gemini", matches)
        assert not comparison.winner_is_clean and not comparison.is_close_call
        assert comparison.avoid_matches(1) == ("sugar",)

    def test_close_call(self, logic):
        twins = logic.compare([product(**LOW_SUGAR), product(**dict(LOW_SUGAR, product_name="Oats B"))],
                              profile(SUGAR_MAX_10))
        assert Comparison(1, twins, "s", {}, {}, "gemini").is_close_call
        assert not Comparison(1, ranked_pair(logic), "s", {}, {}, "gemini").is_close_call


def reading(name: str) -> dict:
    found = {"readable": True, "product_name": name, "brand": None, "category": "Cereal",
             "nutrition": {key: None for key in Nutrient.keys()}, "ingredient_text": "Oats",
             "marketing_claim": None, "notes": None}
    return found


def wait_for_batch(browser, batch_id):
    for _ in range(500):
        if browser.get("/api/batches/" + batch_id).get_json()["finished"]:
            return
        time.sleep(0.01)
    raise AssertionError("batch did not finish")


class TestComparePages:
    FORM = {"include_0": "on", "p0_product_name": "Choco Puffs", "p0_ingredient_text": "Corn, sugar",
            "p0_n_sugar_g": "18", "p0_n_calories_kcal": "230",
            "include_1": "on", "p1_product_name": "Plain Oats", "p1_ingredient_text": "Oats",
            "p1_n_sugar_g": "1", "p1_n_calories_kcal": "150"}

    def upload_two(self, browser) -> str:
        photos = [(io.BytesIO(b"one"), "a.png", "image/png"), (io.BytesIO(b"two"), "b.png", "image/png")]
        response = browser.post("/upload", {"photos": photos, "mode": "compare"},
                                content_type="multipart/form-data")
        assert response.location.endswith("?mode=compare")
        batch_id = response.location.split("?")[0].rsplit("/", 1)[1]
        wait_for_batch(browser, batch_id)
        return batch_id

    def test_compare_page_needs_login_and_shows_upload(self):
        browser = Browser(build_app())
        assert browser.get("/compare").status_code == 302
        browser.login()
        html = browser.get("/compare").get_data(as_text=True)
        assert 'name="mode" value="compare"' in html and "Which one should I buy?" in html

    def test_full_flow_ranks_and_explains(self):
        browser = Browser(build_app(Replies.gemini(reading("A")), Replies.gemini(reading("B")),
                                    Replies.gemini(advice())))
        browser.login()
        batch_id = self.upload_two(browser)
        review = browser.get(f"/batches/{batch_id}?mode=compare").get_data(as_text=True)
        assert "Compare side by side" in review
        response = browser.post(f"/batches/{batch_id}/compare", self.FORM)
        html = browser.finish_job(response.location)
        assert "Best fit for your goals" in html
        assert html.index("Plain Oats") < html.index("Choco Puffs")
        assert "Point 2 to check." in html and "Not saved to your history" in html

    def test_one_product_is_not_enough(self):
        browser = Browser(build_app(Replies.gemini(reading("A")), Replies.gemini(reading("B"))))
        browser.login()
        batch_id = self.upload_two(browser)
        form = {key: value for key, value in self.FORM.items() if not key.startswith("include_1")}
        response = browser.post(f"/batches/{batch_id}/compare", form)
        assert response.status_code == 400 and "Tick 2 to 4 products" in response.get_data(as_text=True)

    def test_one_photo_is_refused_at_upload(self):
        browser = Browser(build_app())
        browser.login()
        response = browser.post("/upload", {"photos": (io.BytesIO(b"one"), "a.png", "image/png"),
                                            "mode": "compare"}, content_type="multipart/form-data")
        assert response.location.endswith("/compare")
        assert "Choose 2 to 4 photos" in browser.get(response.location).get_data(as_text=True)

    def test_page_warns_when_winner_has_a_problem(self):
        browser = Browser(build_app(Replies.gemini(reading("A")), Replies.gemini(reading("B")),
                                    Replies.gemini(advice())))
        browser.login()                                   # jane avoids maltodextrin
        batch_id = self.upload_two(browser)
        form = dict(self.FORM, p0_ingredient_text="Corn, maltodextrin", p1_ingredient_text="Oats, maltodextrin")
        html = browser.finish_job(browser.post(f"/batches/{batch_id}/compare", form).location)
        assert "Highest score, but check the label" in html and "Best fit for your goals" not in html
        assert "Contains maltodextrin" in html

    def test_bad_upload_goes_back_to_compare_page(self):
        browser = Browser(build_app())
        browser.login()
        response = browser.post("/upload", {"photos": (io.BytesIO(b"GIF89a"), "x.gif", "image/gif"),
                                            "mode": "compare"}, content_type="multipart/form-data")
        assert "/compare" in response.location
        assert "Only JPG, PNG or WEBP" in browser.get(response.location).get_data(as_text=True)
