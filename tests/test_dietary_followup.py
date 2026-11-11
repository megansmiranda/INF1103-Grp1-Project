"""Follow-up acceptance tests; every AI response is mocked."""
import json
import re

import pytest

from conftest import Replies, SUGAR_MAX_10, analysis_answer, make_ai, product
from test_web import Browser, build_app
from test_web import TestDietaryPages as DietaryPageFixture
from nutrilenz.ai.prompt_text import DATA_REMINDER
from nutrilenz.ai.label_analysis_task import LabelAnalysisTask
from nutrilenz.ai.recommendation_task import RecommendationTask
from nutrilenz.domain.flag import Flag
from nutrilenz.domain.recommendation_options import RecommendationOptions
from nutrilenz.domain.profile import Profile
from nutrilenz.logic.dietary_checker import DietaryChecker
from nutrilenz.services.analysis_service import AnalysisService
from nutrilenz.services.recommendation_service import RecommendationService


def prompt_payload(http):
    body = http.bodies[-1]
    text = body["contents"][0]["parts"][0]["text"]
    return json.loads(text.split("INPUT_DATA_JSON:\n", 1)[1].removesuffix(DATA_REMINDER))


@pytest.mark.parametrize("ingredients,status,words", [
    ("MILK", "POSSIBLE_CONCERN", ["MILK"]), ("Rice", "NO_MATCH", []), ("", "NOT_CHECKED", [])])
def test_python_facts_sent_to_mocked_ai_and_saved_once(data, logic, monkeypatch, ingredients, status, words):
    ai, http, _ = make_ai(Replies.gemini(analysis_answer()))
    user = data.register("facts", "secret123", [SUGAR_MAX_10], [], ["dairy"])
    calls = []
    original = DietaryChecker.evaluate

    def record_check(self, text, checks):
        report = original(self, text, checks)
        calls.append(report)
        return report

    monkeypatch.setattr(DietaryChecker, "evaluate", record_check)
    outcome = AnalysisService(ai, logic, data).analyse(user, product(ingredient_text=ingredients))
    assert len(calls) == 1
    assert outcome.analysis.dietary_report is calls[0]
    assert prompt_payload(http)["dietary_results"] == [
        {"key": "dairy", "name": "Milk & dairy", "status": status, "matched_words": words}]
    assert data.get_analysis(user.user_id, outcome.analysis.analysis_id).dietary_report == calls[0]
    rules = http.bodies[0]["systemInstruction"]["parts"][0]["text"]
    assert "never add a dietary concern or contradict" in rules
    assert "Never describe any product as safe, suitable, free from anything, or certified" in rules


@pytest.mark.parametrize("phrase", ["safe", "suitable", "free from milk", "free-from nuts", "certified"])
def test_prohibited_ai_claims_are_rejected(phrase):
    task = LabelAnalysisTask(product(), Profile([SUGAR_MAX_10]))
    with pytest.raises(ValueError, match="Do not describe"):
        task.parse(analysis_answer(explanation="This product is " + phrase))
    recommendation = RecommendationTask(Profile([SUGAR_MAX_10]), RecommendationOptions(), [])
    with pytest.raises(ValueError, match="Do not describe"):
        recommendation.parse({"picks": [], "tips": ["This is " + phrase], "suggested_products": []})


def test_recommendation_dietary_filter_prompt_and_cache(data, logic):
    milk = data.save_product(product(product_name="Milk drink", ingredient_text="milk"))
    unknown = data.save_product(product(product_name="Unknown drink", ingredient_text=""))
    user = data.register("picks", "secret123", [SUGAR_MAX_10], [])

    def reply(ids):
        return Replies.gemini({"picks": [{"product_id": n, "reason": "Compare the nutrition."} for n in ids],
                              "tips": ["Check ingredients on the pack."], "suggested_products": []})

    ai, http, _ = make_ai(reply([milk.product_id, unknown.product_id]), reply([unknown.product_id]))
    service = RecommendationService(ai, logic, data)
    first = service.recommend(user, RecommendationOptions())
    assert first.product_ids() == [milk.product_id, unknown.product_id]
    assert service.recommend(user, RecommendationOptions()) is first
    data.update_profile(user, [SUGAR_MAX_10], [], ["vegan", "dairy"])
    second = service.recommend(user, RecommendationOptions())
    assert http.calls == 2 and second.product_ids() == [unknown.product_id]
    assert [item.product.product_id for item in second.excluded] == [milk.product_id]
    payload = prompt_payload(http)
    assert [check["key"] for check in payload["dietary_checks"]] == ["vegan", "dairy"]
    assert "milk" in payload["dietary_checks"][0]["words_to_avoid"]
    assert payload["candidates"][0]["dietary_results"][0]["status"] == "NOT_CHECKED"
    assert service.recommend(user, RecommendationOptions()) is second and http.calls == 2


SIGNUP = {"username": "newdiet", "password": "longpass1", "confirm_password": "longpass1",
          "goal_REDUCE_SUGAR": "on", "target_REDUCE_SUGAR": "10", "avoid_ingredients": "palm oil"}


@pytest.mark.parametrize("keys", [[], ["vegetarian_no_dairy", "egg"], ["vegan", "nuts", "halal_friendly"]])
def test_signup_optional_checks_saved_and_shared_warning(keys):
    browser = Browser(build_app())
    signup = browser.get("/signup").get_data(as_text=True)
    assert signup.count('name="dietary_checks"') == 7
    assert not re.search(r'name="dietary_checks"[^>]*checked', signup)
    assert signup.index('id="dietary-heading"') < signup.index('name="avoid_ingredients"')
    response = browser.post("/signup", dict(SIGNUP, dietary_checks=keys))
    assert response.status_code == 302
    profile = browser.get("/profile").get_data(as_text=True)
    assert "NEW" not in profile
    for key in keys:
        assert re.search('value="' + key + r'"[^>]*checked', profile)
    assert 'value="palm oil"' in profile
    for page in (profile, signup):
        assert "These checks can miss things." in page
        assert "Don't eat eggs? Also tick Egg below." not in page
        assert "Allergens \u00b7 tick any" in page


@pytest.mark.parametrize("keys", [["invented"], ["vegetarian", "vegetarian_no_dairy"], ["<script>x</script>"]])
def test_signup_rejects_tampered_checks_without_creating_account(keys):
    browser = Browser(build_app())
    response = browser.post("/signup", dict(SIGNUP, dietary_checks=keys))
    assert response.status_code == 400
    assert '<script>x</script>' not in response.get_data(as_text=True)
    assert browser.login("newdiet", "longpass1").status_code == 401


def test_signup_other_errors_keep_dietary_choices():
    browser = Browser(build_app())
    response = browser.post("/signup", dict(SIGNUP, password="short", dietary_checks=["vegan"]))
    assert response.status_code == 400
    assert re.search(r'value="vegan"[^>]*checked', response.get_data(as_text=True))


def test_pre_feature_history_never_uses_current_profile(monkeypatch):
    browser = Browser(build_app())
    browser.login()
    browser.post("/profile", DietaryPageFixture.PROFILE)
    monkeypatch.setattr(DietaryChecker, "evaluate", lambda *args: pytest.fail("History recalculated"))
    html = browser.get("/history/1").get_data(as_text=True)
    assert "Dietary checks weren't run for this analysis" in html
    assert "possible concerns found" not in html
    assert "DIETARY REVIEW" not in html
    assert "GOAL MISMATCH" in html and "CLAIM REVIEW" in html
    assert html.index("Your goals") < html.index("Ingredients you confirmed") < html.index("What the AI says")
    assert "How this product matches you" not in html
    assert "Concerns are found by NutriLenz's rules; the AI only explains them." in html


def test_recommendation_page_exclusions_unknowns_and_notice():
    # Build an isolated catalogue so rendering tests never depend on seed ids.
    from nutrilenz.app import NutriLenzApp
    from nutrilenz.app_config import AppConfig
    from nutrilenz.data.data_manager import DataManager
    from nutrilenz.data.memory_store import InMemoryDataStore
    store = InMemoryDataStore()
    data = DataManager(store)
    data.ensure_ready()
    data.register("jane", "jane12345", [SUGAR_MAX_10], [], ["dairy"])
    data.save_product(product(product_name='<script>Milk drink</script>', ingredient_text="MILK"))
    unknown = data.save_product(product(product_name="Unknown drink", ingredient_text=""))
    ai, _, _ = make_ai(Replies.gemini({"picks": [{"product_id": unknown.product_id, "reason": "Compare nutrition."}],
        "tips": ["Check the pack."], "suggested_products": [{"name": "Example oats", "brand": None, "reason": "Compare ingredients."}]}))
    app = NutriLenzApp(AppConfig({"NUTRILENZ_STORAGE": "memory", "FLASK_SECRET_KEY": "test"}), store=store, ai=ai)
    browser = Browser(app)
    browser.login()
    assert "Using your dietary checks: Milk &amp; dairy" in browser.get("/recommendations").get_data(as_text=True)
    html = browser.finish_job(browser.post("/recommendations", {"focus": ["BEST_MATCH"]}).location)
    assert "Ingredients unknown – not checked" in html
    assert "Left out because of possible dietary concerns (1)" in html
    assert '<mark>MILK</mark>' in html and '<script>Milk drink</script>' not in html
    assert '&lt;script&gt;Milk drink&lt;/script&gt;' in html
    assert re.search(r'<details class="card dietary-exclusions"[^>]*>', html)
    assert not re.search(r'<details class="card dietary-exclusions"[^>]*\bopen\b', html)
    assert "not checked against any shop" in html
    browser.post("/profile", dict(DietaryPageFixture.PROFILE, dietary_checks=[]))
    assert "No dietary checks set" in browser.get("/recommendations").get_data(as_text=True)
