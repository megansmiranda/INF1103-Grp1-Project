"""Image-specified words, shared check contracts and backwards-compatible snapshots."""
from dataclasses import FrozenInstanceError

import pytest
from werkzeug.datastructures import MultiDict

from conftest import SUGAR_MAX_10, ai_analysis, product
from nutrilenz.data.mapper import RecordMapper
from nutrilenz.domain.analysis import Analysis
from nutrilenz.domain.dietary_check import DietaryCheck
from nutrilenz.domain.dietary_check_factory import DietaryCheckFactory
from nutrilenz.domain.dietary_keywords import DietaryKeywords
from nutrilenz.domain.dietary_report import DietaryReport
from nutrilenz.domain.dietary_result import DietaryResult
from nutrilenz.domain.dietary_status import DietaryStatus
from nutrilenz.domain.no_dairy_vegetarian_check import NoDairyVegetarianCheck
from nutrilenz.domain.vegetarian_check import VegetarianCheck
from nutrilenz.domain.vegan_check import VeganCheck
from nutrilenz.domain.profile import Profile
from nutrilenz.domain.user import User
from nutrilenz.errors.validation_error import ValidationError
from nutrilenz.logic.dietary_checker import DietaryChecker
from nutrilenz.web.dietary_presenter import DietaryPresenter
from nutrilenz.web.forms import FormParser

# Independent transcription: missing/extra words in the implementation must fail.
VEGETARIAN = "beef|pork|chicken|duck|lamb|mutton|turkey|bacon|ham|meat|lard|tallow|suet|fish|tuna|salmon|sardine|mackerel|anchovy|anchovies|fish sauce|oyster sauce|prawn|shrimp|crab|lobster|crayfish|krill|oyster|mussel|clam|scallop|squid|cuttlefish|octopus|gelatine|gelatin|collagen|isinglass|rennet|carmine|cochineal".split("|")
DAIRY = "milk|milk powder|dairy|whey|casein|caseinate|lactose|butter|buttermilk|cream|cheese|yoghurt|yogurt|ghee|curd".split("|")
VEGAN_EXTRA = DAIRY + "egg|egg white|egg yolk|albumen|albumin|mayonnaise|meringue|honey|beeswax|shellac|royal jelly".split("|")
HALAL = "pork|lard|bacon|ham|pancetta|gelatine|gelatin|alcohol|ethanol|wine|rum|beer|brandy|liqueur|mirin|sake".split("|")
EXAMPLES = {"vegetarian": "gelatine", "vegetarian_no_dairy": "milk", "vegan": "shellac",
            "halal_friendly": "mirin", "nuts": "almonds", "dairy": "curd", "gluten": "wheat",
            "egg": "mayonnaise", "soy": "soybeans", "shellfish": "prawns"}


@pytest.mark.parametrize("key,words", [("vegetarian", VEGETARIAN), ("vegan", VEGETARIAN + VEGAN_EXTRA),
                                      ("halal_friendly", HALAL), ("vegetarian_no_dairy", VEGETARIAN + DAIRY)])
def test_keyword_catalogue_matches_images_exactly(key, words):
    check = DietaryCheckFactory.create(key)
    actual = [word for group in check.keyword_groups for word in DietaryKeywords.GROUPS[group]]
    assert set(actual) == set(words) and len(actual) == len(words)
    assert len(VEGETARIAN) == 42 and len(VEGETARIAN + VEGAN_EXTRA) == 68


@pytest.mark.parametrize("key,word", [("vegetarian", w) for w in VEGETARIAN]
                         + [("vegan", w) for w in VEGETARIAN + VEGAN_EXTRA]
                         + [("halal_friendly", w) for w in HALAL])
def test_every_pictured_word_is_detected_case_insensitively(key, word):
    text = "Salt, " + word.upper() + ", water"
    result = DietaryChecker().check(text, DietaryCheckFactory.create(key))
    assert result.status is DietaryStatus.POSSIBLE_CONCERN
    assert result.matched_words == (word.upper(),)
    assert [text[a:b] for a, b in result.matched_spans] == [word.upper()]


@pytest.mark.parametrize("key", EXAMPLES)
@pytest.mark.parametrize("status", list(DietaryStatus))
def test_each_status_for_each_check(key, status):
    text = {DietaryStatus.POSSIBLE_CONCERN: EXAMPLES[key], DietaryStatus.NO_MATCH: "Rice, water",
            DietaryStatus.NOT_CHECKED: " \n "}[status]
    result = DietaryChecker().check(text, DietaryCheckFactory.create(key))
    assert result.status is status
    assert bool(result.matched_words) == (status is DietaryStatus.POSSIBLE_CONCERN)


@pytest.mark.parametrize("key", EXAMPLES)
def test_none_is_not_checked(key):
    assert DietaryChecker().check(None, DietaryCheckFactory.create(key)).status is DietaryStatus.NOT_CHECKED


@pytest.mark.parametrize("word", VEGETARIAN)
def test_vegetarian_subclasses_preserve_all_parent_matches(word):
    for check in (VegetarianCheck(), NoDairyVegetarianCheck(), VeganCheck()):
        assert isinstance(check, VegetarianCheck)
        assert DietaryChecker().check(word, check).status is DietaryStatus.POSSIBLE_CONCERN


def test_vegetarian_dairy_options_and_separate_egg_check():
    checker = DietaryChecker()
    assert checker.check("Milk, eggs", VegetarianCheck()).status is DietaryStatus.NO_MATCH
    assert checker.check("Milk, eggs", NoDairyVegetarianCheck()).matched_words == ("Milk",)
    assert checker.check("eggs", NoDairyVegetarianCheck()).status is DietaryStatus.NO_MATCH
    assert checker.check("eggs", DietaryCheckFactory.create("egg")).matched_words == ("eggs",)
    assert checker.check("Milk, eggs, honey", VeganCheck()).matched_words == ("Milk", "eggs", "honey")


@pytest.mark.parametrize("text", ["nutmeg", "coconut", "butternut", "coconut milk", "COCONUT   MILKS"])
@pytest.mark.parametrize("key", ["nuts", "dairy"])
def test_required_false_positives(text, key):
    assert DietaryChecker().check(text, DietaryCheckFactory.create(key)).status is DietaryStatus.NO_MATCH


@pytest.mark.parametrize("text", ["coconut milk powder", "coconut cream", "cocoa butter", "peanut butter", "almond milk"])
def test_dairy_phrase_exceptions(text):
    assert DietaryChecker().check(text, DietaryCheckFactory.create("dairy")).status is DietaryStatus.NO_MATCH


def test_exceptions_do_not_hide_separate_matches_and_plurals_work():
    text = "Coconut milk, MILK powder, almond milk, almonds, cashews, egg whites"
    checks = DietaryCheckFactory.from_keys(["dairy", "nuts", "egg"])
    results = DietaryChecker().evaluate(text, checks).results
    assert results[0].matched_words == ("MILK powder",)
    assert results[1].matched_words == ("almond", "almonds", "cashews")
    assert results[2].matched_words == ("egg whites",)


def test_whole_words_and_longest_phrase():
    checker = DietaryChecker()
    assert checker.check("hamper, fishy, beerbread, nutmeg", VeganCheck()).status is DietaryStatus.NO_MATCH
    assert checker.check("oyster sauce", VeganCheck()).matched_words == ("oyster sauce",)
    assert product(ingredient_text="coconut milk").ingredients_found(["nut", "milk"]) == ["nut", "milk"]


def test_immutable_results_and_reports():
    words, spans = ["milk"], [[0, 4]]
    result = DietaryResult("dairy", "Milk & dairy", DietaryStatus.POSSIBLE_CONCERN, words, spans)
    report = DietaryReport([result], "milk", score_penalty=25)
    words.clear()
    spans[0][1] = 99
    assert result.matched_words == ("milk",) and result.matched_spans == ((0, 4),)
    for obj, attr, value in [(result, "status", DietaryStatus.NO_MATCH), (report, "score_penalty", 0)]:
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attr, value)
    assert DietaryReport.from_dict(report.to_dict()) == report


def test_profile_snapshot_and_legacy_records():
    profile = Profile([SUGAR_MAX_10], ["palm oil"], ["vegetarian_no_dairy", "egg"])
    snapshot = profile.snapshot()
    assert Profile.from_snapshot(snapshot).snapshot() == snapshot
    snapshot["dietary_checks"].clear()
    assert len(profile.dietary_checks) == 2
    mapper = RecordMapper()
    row = mapper.user_to_row(User("legacy", "hash", [SUGAR_MAX_10], user_id=1))
    row.pop("dietary_checks")
    assert mapper.user_from_row(row).profile.dietary_checks == ()
    prod = product(product_id=1)
    old = Analysis(1, prod, {"goals": [SUGAR_MAX_10]}, ai_analysis(), [], [], 42, "gemini")
    record = mapper.analysis_to_row(old)
    record.pop("dietary_results")
    assert mapper.analysis_from_row(record, prod).dietary_report.results == ()
    legacy = DietaryChecker().check("milk", VeganCheck())
    loaded = DietaryReport.from_dict([legacy.to_dict()], "milk")
    assert loaded.results == (legacy,) and loaded.rules_version == "legacy" and loaded.score_penalty == 0


def test_legacy_concern_flag_comes_only_from_saved_statuses(monkeypatch):
    from nutrilenz.domain.flag import Flag
    prod = product(product_id=1, ingredient_text="HAZELNUTS, MILK")
    report = DietaryChecker().evaluate(prod.ingredient_text, DietaryCheckFactory.from_keys(["nuts", "dairy"]))
    mapper = RecordMapper()
    original = Analysis(1, prod, {"goals": [SUGAR_MAX_10]}, ai_analysis(),
                        [Flag.GOAL_MISMATCH, Flag.MANUAL_REVIEW], [], 42, "gemini")
    row = mapper.analysis_to_row(original)
    row["dietary_results"] = [r.to_dict() for r in report.results]
    monkeypatch.setattr(DietaryChecker, "evaluate", lambda *args: pytest.fail("History must not recheck"))
    loaded = mapper.analysis_from_row(row, prod)
    assert loaded.dietary_report.concern_count == 2
    assert loaded.flags == (Flag.GOAL_MISMATCH, Flag.MANUAL_REVIEW, Flag.DIETARY_REVIEW)
    assert loaded.score == 42
    row["dietary_results"] = None
    old = mapper.analysis_from_row(row, prod)
    assert old.dietary_report.results == ()
    assert old.dietary_report.rules_version == "not-run"
    assert old.flags == original.flags


@pytest.mark.parametrize("keys", [["unknown"], ["nuts", "NUTS"], ["<script>"], ["vegetarian", "vegetarian_no_dairy"]])
def test_unknown_or_conflicting_form_keys_are_rejected(keys):
    with pytest.raises(ValidationError):
        FormParser().dietary_checks(MultiDict([("dietary_checks", key) for key in keys]))


def test_abstract_contract_and_registry_extension(monkeypatch):
    with pytest.raises(TypeError):
        DietaryCheck()

    class ExtraCheck(DietaryCheck):
        key = "extra"
        label = "Extra"
        keyword_groups = ("soy",)

    monkeypatch.setitem(DietaryCheckFactory.TYPES, "extra", (ExtraCheck, ()))
    checks = Profile([SUGAR_MAX_10], dietary_checks=["extra"]).dietary_checks
    assert DietaryChecker().evaluate("Soy", checks).has_concern


def test_highlighting_preserves_text_and_merges_overlapping_checks():
    text = '<script>alert(1)</script> MILK & coconut milk, almonds'
    report = DietaryChecker().evaluate(text, DietaryCheckFactory.from_keys(["vegan", "dairy", "nuts"]))
    parts = DietaryPresenter.ingredient_segments(report)
    assert "".join(text for text, matched in parts) == report.ingredient_text
    assert [text for text, matched in parts if matched] == ["MILK", "almonds"]
