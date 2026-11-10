"""AI Manager: prompts, provider bodies, parsing, schema checks, retries and fallback.
The real provider classes run against FakeHttp, so no API key or internet is used."""
import pytest

from conftest import (FakeHttp, PROTEIN_MIN_15, SUGAR_MAX_10, Replies, analysis_answer, make_ai,
                      product, profile)
from nutrilenz.ai.ai_manager import AIManager
from nutrilenz.ai.providers import AIProvider, GeminiProvider, GroqProvider
from nutrilenz.ai.results import AIRequest, LabelImage
from nutrilenz.ai.tasks import LabelAnalysisTask, LabelExtractionTask, RecommendationTask
from nutrilenz.ai.validation import JsonReplyParser
from nutrilenz.domain.nutrients import Nutrient
from nutrilenz.domain.recommendation import RecommendationOptions, ScoredProduct
from nutrilenz.errors.ai_error import AIError

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def analyse(ai, prod=None, prof=None):
    return ai.analyse_label(prod or product(), prof or profile(SUGAR_MAX_10))


class TestParsing:
    def test_strips_markdown_fence(self):
        assert JsonReplyParser().parse('```json\n{"a": 1}\n```') == {"a": 1}

    @pytest.mark.parametrize("raw", ["", "   ", "not json", "[1, 2]", None])
    def test_rejects_non_objects(self, raw):
        with pytest.raises(ValueError):
            JsonReplyParser().parse(raw)


class TestLabelAnalysisSchema:
    def parse(self, answer, prod=None):
        return LabelAnalysisTask(prod or product(), profile(SUGAR_MAX_10)).parse(answer)

    def test_valid_answer(self):
        result = self.parse(analysis_answer())
        assert result.goal_alignment == "POOR_ALIGNMENT"
        assert result.suggested_products[0].brand == "FairPrice"

    @pytest.mark.parametrize("changes, message", [
        ({"confidence": "high"}, "Bad confidence"),                 # wrong case is rejected, not fixed
        ({"goal_alignment": "GOOD"}, "Bad goal_alignment"),
        ({"evidence": []}, "evidence"),
        ({"explanation": "  "}, "explanation"),
        ({"suggestions": []}, "suggestions"),
        ({"relevant_ingredients": "sugar"}, "must be a list"),
        ({"suggested_products": [{"name": "X", "brand": None}]}, "Missing fields"),
        ({"suggested_products": [{"name": "Oat", "brand": None, "reason": "r"}] * 2}, "repeat"),
        ({"suggested_products": [{"name": f"P{i}", "brand": None, "reason": "r"} for i in range(4)]},
         "at most 3"),
        ({"suggested_products": [{"name": "Example Cereal", "brand": None, "reason": "r"}]},
         "analysed product"),
    ])
    def test_bad_fields_rejected(self, changes, message):
        with pytest.raises(ValueError, match=message):
            self.parse(analysis_answer(**changes))

    def test_extra_and_missing_fields_rejected(self):
        with pytest.raises(ValueError, match="Unexpected"):
            self.parse(analysis_answer(flags=["GOOD_MATCH"]))
        answer = analysis_answer()
        del answer["confidence"]
        with pytest.raises(ValueError, match="Missing"):
            self.parse(answer)

    def test_claim_status_must_match_whether_a_claim_was_given(self):
        with pytest.raises(ValueError, match="NO_CLAIM"):
            self.parse(analysis_answer(claim_status="CONSISTENT"), product(marketing_claim=None))
        with pytest.raises(ValueError, match="cannot be NO_CLAIM"):
            self.parse(analysis_answer(claim_status="NO_CLAIM"))

    def test_empty_product_suggestions_allowed(self):
        assert self.parse(analysis_answer(suggested_products=[])).suggested_products == ()

    def test_prompt_keeps_target_numbers_out_and_marks_data(self):
        request = LabelAnalysisTask(product(), profile(SUGAR_MAX_10, PROTEIN_MIN_15)).build_request()
        assert "INPUT_DATA_JSON" in request.user_content
        assert "keep low: sugar" in request.user_content and "get more: protein" in request.user_content
        assert '"target"' not in request.user_content
        assert "Singapore" in request.system_rules
        assert "ignore previous instructions" in request.system_rules


class TestProviders:
    def test_gemini_body_and_key_in_header(self):
        http = FakeHttp([Replies.gemini(analysis_answer())])
        provider = GeminiProvider("secret-key", "gemini-test", http)
        provider.generate(AIRequest("rules", "data"))
        body = http.bodies[0]
        assert body["systemInstruction"]["parts"][0]["text"] == "rules"
        assert body["generationConfig"]["temperature"] == 0
        assert http.headers[0] == {"x-goog-api-key": "secret-key"}
        assert "secret-key" not in http.urls[0]

    def test_gemini_sends_photo_inline(self):
        http = FakeHttp([Replies.gemini("{}")])
        GeminiProvider("k", "m", http).generate(AIRequest("r", "d", LabelImage(PNG, "image/png")))
        assert http.bodies[0]["contents"][0]["parts"][0]["inline_data"]["mime_type"] == "image/png"

    def test_groq_uses_vision_model_only_for_photos(self):
        http = FakeHttp([Replies.groq("{}"), Replies.groq("{}")])
        groq = GroqProvider("k", "openai/gpt-oss-20b", http, "vision-model")
        groq.generate(AIRequest("r", "d"))
        groq.generate(AIRequest("r", "d", LabelImage(PNG, "image/png")))
        assert http.bodies[0]["model"] == "openai/gpt-oss-20b" and "reasoning_effort" in http.bodies[0]
        assert http.bodies[1]["model"] == "vision-model"

    def test_groq_without_vision_model_cannot_read_photos(self):
        groq = GroqProvider("k", "m", FakeHttp([]), vision_model=None)
        assert not groq.supports_images
        with pytest.raises(AIError) as error:
            groq.generate(AIRequest("r", "d", LabelImage(PNG, "image/png")))
        assert error.value.code == "NO_IMAGE_PROVIDER"

    @pytest.mark.parametrize("reply", [{}, {"candidates": []},
                                       {"candidates": [{"finishReason": "MAX_TOKENS"}]}])
    def test_odd_reply_shapes_are_invalid_response(self, reply):
        with pytest.raises(AIError) as error:
            GeminiProvider("k", "m", FakeHttp([reply])).generate(AIRequest("r", "d"))
        assert error.value.code == "INVALID_RESPONSE"

    def test_provider_is_abstract_and_needs_a_key(self):
        with pytest.raises(TypeError):
            AIProvider("k", "m", FakeHttp([]))
        with pytest.raises(ValueError):
            GeminiProvider("", "m", FakeHttp([]))

    def test_providers_are_interchangeable(self):
        # LSP: the manager works the same with either provider first
        for provider in (GeminiProvider("k", "m", FakeHttp([Replies.gemini(analysis_answer())])),
                         GroqProvider("k", "m", FakeHttp([Replies.groq(analysis_answer())]))):
            result = AIManager([provider]).analyse_label(product(), profile(SUGAR_MAX_10))
            assert result.provider == provider.name
            assert result.value.claim_status == "QUESTIONABLE"


class TestRetryAndFallback:
    def test_success_first_time(self):
        ai, gemini, groq = make_ai(Replies.gemini(analysis_answer()))
        assert analyse(ai).provider == "gemini"
        assert gemini.calls == 1 and groq.calls == 0

    def test_bad_output_is_retried_with_feedback(self):
        ai, gemini, _ = make_ai(Replies.gemini("Sure! here you go"), Replies.gemini(analysis_answer()))
        assert analyse(ai).provider == "gemini"
        assert "previous reply was rejected" in gemini.bodies[1]["contents"][0]["parts"][-1]["text"]

    def test_falls_back_to_groq(self):
        ai, gemini, groq = make_ai(Replies.gemini("bad"), Replies.gemini("still bad"),
                                   groq_replies=[Replies.groq(analysis_answer())])
        assert analyse(ai).provider == "groq"
        assert gemini.calls == 2 and groq.calls == 1

    def test_wrong_key_skips_retry(self):
        ai, gemini, groq = make_ai(AIError("AUTHENTICATION_ERROR"),
                                   groq_replies=[Replies.groq(analysis_answer())])
        assert analyse(ai).provider == "groq"
        assert gemini.calls == 1

    def test_busy_server_waits_before_retry(self):
        waits = []
        ai, _, _ = make_ai(AIError("API_UNAVAILABLE"), Replies.gemini(analysis_answer()),
                           sleep=waits.append)
        analyse(ai)
        assert waits == [1]

    def test_everything_fails_gives_last_error(self):
        ai, _, _ = make_ai(AIError("API_CONNECTION_ERROR"), AIError("API_CONNECTION_ERROR"),
                           groq_replies=[AIError("API_CONNECTION_ERROR")] * 2)
        with pytest.raises(AIError) as error:
            analyse(ai)
        assert error.value.code == "API_CONNECTION_ERROR"

    def test_no_keys_is_configuration_error(self):
        with pytest.raises(AIError) as error:
            AIManager([]).analyse_label(product(), profile())
        assert error.value.code == "CONFIGURATION_ERROR"

    def test_photo_task_skips_providers_without_vision(self):
        http = FakeHttp([])
        ai = AIManager([GroqProvider("k", "m", http, vision_model=None)])
        with pytest.raises(AIError) as error:
            ai.read_label_image(LabelImage(PNG, "image/png"))
        assert error.value.code == "NO_IMAGE_PROVIDER" and http.calls == 0


class TestExtractionAndRecommendationTasks:
    def reading(self, **changes):
        answer = {"readable": True, "product_name": "Bar", "brand": None, "category": "Snack",
                  "nutrition": {key: None for key in Nutrient.keys()},
                  "ingredient_text": "Oats", "marketing_claim": None, "notes": None}
        answer["nutrition"]["sugar_g"] = 4
        answer.update(changes)
        return answer

    def test_label_reading(self):
        result = LabelExtractionTask(LabelImage(PNG, "image/png")).parse(self.reading())
        assert result.readable and result.product_fields["nutrition"]["sugar_g"] == 4.0

    @pytest.mark.parametrize("changes", [
        {"readable": "yes"},
        {"nutrition": {"sugar_g": 4}},                               # missing nutrient keys
        {"nutrition": {**{key: None for key in Nutrient.keys()}, "sugar_g": -2}},
    ])
    def test_bad_label_reading(self, changes):
        with pytest.raises(ValueError):
            LabelExtractionTask(LabelImage(PNG, "image/png")).parse(self.reading(**changes))

    @pytest.mark.parametrize("data, mime", [(b"", "image/png"), (PNG, "image/gif"),
                                            (b"0" * (8 * 1024 * 1024 + 1), "image/png")])
    def test_bad_photos_rejected_before_any_ai_call(self, data, mime):
        with pytest.raises(ValueError):
            LabelImage(data, mime)

    def shortlist(self):
        items = []
        for product_id, name in ((1, "Tuna"), (2, "Yoghurt")):
            prod = product(product_name=name)
            prod.assign_id(product_id)
            items.append(ScoredProduct(prod, 90, []))
        return items

    def advise(self, answer):
        return RecommendationTask(profile(PROTEIN_MIN_15), RecommendationOptions(),
                                  self.shortlist()).parse(answer)

    def test_recommendation_only_uses_shortlisted_ids(self):
        good = {"picks": [{"product_id": 1, "reason": "22 g protein"}], "tips": ["Eat fish"],
                "suggested_products": [{"name": "Ayam Brand Tuna", "brand": "Ayam Brand", "reason": "High protein"}]}
        advice = self.advise(good)
        assert advice.reasons == {1: "22 g protein"}
        assert advice.suggested_products[0].name == "Ayam Brand Tuna"
        for bad_id in (99, "1", True):
            with pytest.raises(ValueError):
                self.advise({**good, "picks": [{"product_id": bad_id, "reason": "x"}]})

    def test_recommendation_must_pick_one_and_not_repeat_candidates(self):
        with pytest.raises(ValueError, match="at least one"):
            self.advise({"picks": [], "tips": ["t"], "suggested_products": []})
        with pytest.raises(ValueError, match="repeat a candidate"):
            self.advise({"picks": [{"product_id": 1, "reason": "x"}], "tips": ["t"],
                         "suggested_products": [{"name": "Tuna", "brand": None, "reason": "r"}]})
