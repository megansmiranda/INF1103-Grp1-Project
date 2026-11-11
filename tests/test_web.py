"""Web IO Manager: pages, login, form validation, CSRF and the background job flow.
Uses the Flask test client and a fake AI, so no server, browser or API is needed."""
import io
import re
import time

import pytest

from conftest import Replies, analysis_answer, make_ai
from nutrilenz.app import NutriLenzApp
from nutrilenz.app_config import AppConfig
from nutrilenz.data.memory_store import InMemoryDataStore
from nutrilenz.domain.nutrients import Nutrient

PRODUCT_FORM = {"product_name": "Honey Oat Bar", "brand": "GoodGrain", "category": "Snack",
                "marketing_claim": "Only natural sugars",
                "ingredient_text": "Oats, honey, glucose syrup", "n_sugar_g": "12", "n_calories_kcal": "180"}


class Browser:
    """A logged-in (or not) test client that copies the CSRF token into each form."""

    def __init__(self, app: NutriLenzApp):
        self._client = app.web_app.test_client()

    def get(self, url):
        return self._client.get(url)

    def token(self) -> str:
        html = self._client.get("/login").get_data(as_text=True)
        found = re.search(r'name="csrf_token" value="([0-9a-f]+)"', html)
        if found:
            return found.group(1)
        html = self._client.get("/analyse").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([0-9a-f]+)"', html).group(1)

    def post(self, url, data=None, csrf=True, **kwargs):
        data = dict(data or {})
        if csrf:
            data["csrf_token"] = self.token()
        return self._client.post(url, data=data, **kwargs)

    def login(self, username="jane", password="jane12345"):
        return self.post("/login", {"username": username, "password": password})

    def finish_job(self, location):
        job_id = location.rsplit("/", 1)[1]
        for _ in range(500):
            if self.get("/api/jobs/" + job_id).get_json()["finished"]:
                return self.get("/jobs/" + job_id).get_data(as_text=True)
            time.sleep(0.01)
        raise AssertionError("job did not finish")


def build_app(*gemini_replies) -> NutriLenzApp:
    ai, _, _ = make_ai(*gemini_replies)
    config = AppConfig({"NUTRILENZ_STORAGE": "memory", "FLASK_SECRET_KEY": "test-secret"})
    app = NutriLenzApp(config, store=InMemoryDataStore(), ai=ai)
    app.prepare_data()
    return app


@pytest.fixture
def browser() -> Browser:
    return Browser(build_app(Replies.gemini(analysis_answer())))


class TestAccounts:
    def test_pages_need_login(self, browser):
        for url in ("/", "/history", "/analyse", "/recommendations", "/profile"):
            assert browser.get(url).status_code == 302

    def test_login_with_demo_account(self, browser):
        assert browser.login().location == "/"
        assert "Sugar at most 10 g per serving" in browser.get("/").get_data(as_text=True)

    def test_wrong_password(self, browser):
        response = browser.login(password="wrong")
        assert response.status_code == 401 and "Wrong username or password" in response.get_data(as_text=True)

    def test_signup_validation_and_success(self, browser):
        bad = browser.post("/signup", {"username": "x", "password": "short", "confirm_password": "short"})
        body = bad.get_data(as_text=True)
        assert bad.status_code == 400 and "3-40 letters" in body and "at least 8" in body and "at least one goal" in body
        good = browser.post("/signup", {"username": "newbie", "password": "longpass1",
                                        "confirm_password": "longpass1", "goal_HIGH_FIBRE": "on",
                                        "target_HIGH_FIBRE": "5", "avoid_ingredients": "peanuts, msg"})
        assert good.location == "/"
        assert "Dietary fibre at least 5 g" in browser.get("/").get_data(as_text=True)

    def test_duplicate_username(self, browser):
        response = browser.post("/signup", {"username": "jane", "password": "longpass1",
                                            "confirm_password": "longpass1", "goal_LOW_FAT": "on",
                                            "target_LOW_FAT": "5"})
        assert response.status_code == 400 and "already taken" in response.get_data(as_text=True)

    def test_update_goals(self, browser):
        browser.login()
        bad = browser.post("/profile", {"goal_LOW_FAT": "on", "target_LOW_FAT": "-1"})
        assert bad.status_code == 400
        browser.post("/profile", {"goal_LOW_FAT": "on", "target_LOW_FAT": "8"})
        assert "Total fat at most 8 g" in browser.get("/").get_data(as_text=True)

    def test_form_without_csrf_token_is_refused(self, browser):
        browser.login()
        response = browser.post("/profile", {"goal_LOW_FAT": "on", "target_LOW_FAT": "8"}, csrf=False)
        assert response.status_code == 302
        assert "Total fat" not in browser.get("/").get_data(as_text=True)

    def test_delete_account_needs_password(self, browser):
        browser.login()
        browser.post("/profile/delete", {"password": "wrong"})
        assert browser.get("/").status_code == 200
        browser.post("/profile/delete", {"password": "jane12345"})
        assert browser.get("/").status_code == 302
        assert browser.login().status_code == 401


class TestAnalysisPages:
    def test_manual_analysis_runs_as_background_job(self, browser):
        browser.login()
        response = browser.post("/analyse", PRODUCT_FORM)
        assert response.location.startswith("/jobs/")
        html = browser.finish_job(response.location)
        assert "GOAL MISMATCH" in html and "CLAIM REVIEW" in html
        assert "Products to try in Singapore" in html and "FairPrice" in html
        assert "Honey Oat Bar" in browser.get("/history").get_data(as_text=True)

    def test_invalid_product_shows_every_problem(self, browser):
        browser.login()
        response = browser.post("/analyse", {"product_name": "", "ingredient_text": "",
                                             "n_sugar_g": "-1", "n_protein_g": "abc"})
        body = response.get_data(as_text=True)
        assert response.status_code == 400
        for text in ("Product name is required", "Sugar must be",
                     "Protein must be"):
            assert text in body

    def test_odd_numbers_need_confirmation(self, browser):
        browser.login()
        form = dict(PRODUCT_FORM, n_sugar_g="500")
        first = browser.post("/analyse", form)
        assert first.status_code == 200 and "is above 100" in first.get_data(as_text=True)
        confirmed = browser.post("/analyse", dict(form, confirmed="yes"))
        assert confirmed.location.startswith("/jobs/")

    def test_ai_failure_page(self):
        browser = Browser(build_app())                    # no replies: AI is unavailable
        browser.login()
        html = browser.finish_job(browser.post("/analyse", PRODUCT_FORM).location)
        assert "That did not work" in html and "No new record was saved" in html

    def test_photo_upload_then_review(self):
        reading = {"readable": True, "product_name": "Crunch Bar", "brand": "FitFuel", "category": "Snack",
                   "nutrition": {key: None for key in Nutrient.keys()}, "ingredient_text": "Soy protein, oats",
                   "marketing_claim": "High Protein", "notes": None}
        reading["nutrition"]["protein_g"] = 17
        browser = Browser(build_app(Replies.gemini(reading)))
        browser.login()
        response = browser.post("/upload", {"photos": (io.BytesIO(b"fake image"), "bar.png", "image/png")},
                                content_type="multipart/form-data")
        batch_id = response.location.rsplit("/", 1)[1]
        for _ in range(500):
            if browser.get("/api/batches/" + batch_id).get_json()["finished"]:
                break
            time.sleep(0.01)
        html = browser.get("/batches/" + batch_id).get_data(as_text=True)
        assert 'value="Crunch Bar"' in html and 'value="17"' in html

    def test_wrong_file_type(self, browser):
        browser.login()
        response = browser.post("/upload", {"photos": (io.BytesIO(b"GIF89a"), "x.gif", "image/gif")},
                                content_type="multipart/form-data")
        assert response.status_code == 400 and "Only JPG, PNG or WEBP" in response.get_data(as_text=True)


class TestHistoryPages:
    def test_filter_by_flag_and_search(self, browser):
        browser.login()
        assert browser.get("/history?flag=GOOD_MATCH").get_data(as_text=True).count("/delete") == 1
        assert "Example Cereal" in browser.get("/history?q=cereal").get_data(as_text=True)
        assert "No analyses match" in browser.get("/history?q=pizza").get_data(as_text=True)

    def test_cannot_open_someone_elses_record(self, browser):
        browser.login("sam", "sam12345")
        assert browser.get("/history/1").status_code == 404      # record 1 belongs to jane

    def test_delete_record(self, browser):
        browser.login()
        browser.post("/history/1/delete")
        assert browser.get("/history/1").status_code == 404


class TestRecommendationPages:
    def test_only_listed_options_accepted(self, browser):
        browser.login()
        assert browser.post("/recommendations", {"focus": "ANYTHING"}).status_code == 400
        assert browser.post("/recommendations", {"focus": "BEST_MATCH", "category": "Pizza"}).status_code == 400
        response = browser.post("/recommendations", {})
        assert response.status_code == 400 and "at least one focus" in response.get_data(as_text=True)

    def test_several_options_can_be_ticked(self):
        app = build_app()
        browser = Browser(app)
        browser.login("sam", "sam12345")
        page = browser.get("/recommendations").get_data(as_text=True)
        assert page.count('type="checkbox" name="focus"') == 7
        response = browser.post("/recommendations", {"focus": ["LOWEST_SODIUM", "HIGHEST_PROTEIN"],
                                                      "category": ["Snack", "Dairy"]})
        assert response.location.startswith("/jobs/")


class TestDietaryPages:
    PROFILE = {"goal_REDUCE_SUGAR": "on", "target_REDUCE_SUGAR": "10", "avoid_ingredients": "palm oil",
               "dietary_checks": ["vegetarian", "halal_friendly", "nuts", "dairy"]}

    def test_profile_controls_hint_save_switch_and_clear(self, browser):
        browser.login()
        page = browser.get("/profile").get_data(as_text=True)
        assert page.count('name="dietary_checks"') == 7
        assert "Don't eat eggs? Also tick Egg below." not in page
        assert "Allergens \u00b7 tick any" in page
        assert browser.post("/profile", self.PROFILE).location == "/profile"
        html = browser.get("/profile").get_data(as_text=True)
        assert 'value="palm oil"' in html
        assert re.search(r'value="vegetarian"[^>]*checked', html)
        browser.post("/profile", dict(self.PROFILE, dietary_checks=["vegetarian_no_dairy", "egg"]))
        html = browser.get("/profile").get_data(as_text=True)
        assert re.search(r'value="vegetarian_no_dairy"[^>]*checked', html)
        assert not re.search(r'value="vegetarian"[^>]*checked', html)
        browser.post("/profile", dict(self.PROFILE, dietary_checks=[]))
        assert not re.search(r'name="dietary_checks"[^>]*checked', browser.get("/profile").get_data(as_text=True))

    @pytest.mark.parametrize("keys", [["tampered"], ["vegetarian", "vegetarian_no_dairy"]])
    def test_invalid_checks_do_not_save_profile(self, browser, keys):
        browser.login()
        browser.post("/profile", self.PROFILE)
        response = browser.post("/profile", dict(self.PROFILE, dietary_checks=keys, avoid_ingredients="milk"))
        assert response.status_code == 400
        assert 'value="palm oil"' in browser.get("/profile").get_data(as_text=True)

    def test_job_result_highlights_and_history_survive_profile_edits(self, browser):
        browser.login()
        browser.post("/profile", self.PROFILE)
        text = '<script>alert("x")</script> Rolled oats, almonds (8%), coconut milk, gelatine.'
        response = browser.post("/analyse", dict(PRODUCT_FORM, ingredient_text=text))
        html = browser.finish_job(response.location)
        assert "3 possible concerns" in html and "DIETARY REVIEW" in html
        assert "Possible concern" in html and "No match found" in html
        assert '<mark>almonds</mark>' in html and '<mark>gelatine</mark>' in html
        assert '<mark>milk</mark>' not in html
        assert '&lt;script&gt;' in html and '<script>alert' not in html
        assert "Dietary score adjustment" not in html
        assert not re.search(r'\b(safe|suitable|certified)\b|free from', html, re.I)
        history = browser.get("/history?flag=DIETARY_REVIEW").get_data(as_text=True)
        assert 'value="DIETARY_REVIEW"' in history
        record_id = re.search(r'href="/history/(\d+)"', history).group(1)
        browser.post("/profile", dict(self.PROFILE, dietary_checks=[]))
        saved = browser.get("/history/" + record_id).get_data(as_text=True)
        assert '<mark>almonds</mark>' in saved and "3 possible concerns" in saved

    def test_blank_ingredients_not_checked_and_unselected_unchanged(self, browser):
        browser.login()
        browser.post("/profile", self.PROFILE)
        html = browser.finish_job(browser.post("/analyse", dict(PRODUCT_FORM, ingredient_text="")).location)
        assert html.count("Not checked – no ingredient list") == 8
        assert "DIETARY REVIEW" not in html and "Dietary score adjustment" not in html

    def test_signup_controls_without_dashboard_summary(self, browser):
        assert browser.get("/signup").get_data(as_text=True).count('name="dietary_checks"') == 7
        browser.login()
        assert 'flag=DIETARY_REVIEW' not in browser.get("/").get_data(as_text=True)
        html = browser.finish_job(browser.post("/analyse", PRODUCT_FORM).location)
        assert "No dietary checks selected for this analysis" in html
