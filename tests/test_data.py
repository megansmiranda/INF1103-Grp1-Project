"""Data Manager and both storage back ends.

The same contract tests run against InMemoryDataStore and MySQLDataStore (LSP: either
store can replace the other). MySQL tests run when NUTRILENZ_TEST_MYSQL=1 is set
(CI starts a MySQL service for this); otherwise they are skipped."""
import os
from datetime import datetime, timedelta

import pymysql
import pytest

from conftest import (CALORIES_MAX_200, PROTEIN_MIN_15, SUGAR_MAX_10, ai_analysis, product)
from nutrilenz.data.data_manager import DataManager
from nutrilenz.data.memory_store import InMemoryDataStore
from nutrilenz.data.mysql_store import MySQLDataStore
from nutrilenz.data.seeder import DemoDataSeeder
from nutrilenz.domain.analysis import Analysis
from nutrilenz.domain.flag import Flag
from nutrilenz.errors.auth_error import AuthError
from nutrilenz.errors.data_error import DataError
from nutrilenz.logic.logic_manager import LogicManager
from nutrilenz.domain.dietary_keywords import DietaryKeywords
from nutrilenz.domain.dietary_status import DietaryStatus
from conftest import Replies, analysis_answer, make_ai


def mysql_settings() -> dict:
    """Tests empty the tables, so they use their own database, never the app's one."""
    database = os.environ.get("TEST_DB_NAME", "nutrilenz_test")
    assert database != os.environ.get("DB_NAME", "nutrilenz"), "use a separate test database"
    return {"host": os.environ.get("DB_HOST", "127.0.0.1"), "port": int(os.environ.get("DB_PORT", "3306")),
            "user": os.environ.get("DB_USER", "nutrilenz"), "password": os.environ.get("DB_PASSWORD", ""),
            "database": database}


def empty_mysql_store() -> MySQLDataStore:
    settings = mysql_settings()
    store = MySQLDataStore(**settings)
    store.initialise()
    connection = pymysql.connect(**settings)
    with connection.cursor() as cursor:
        for table in ("analyses", "goals", "products", "users"):
            cursor.execute("DELETE FROM " + table)
    connection.commit()
    connection.close()
    return store


@pytest.fixture(params=["memory", "mysql"])
def manager(request) -> DataManager:
    if request.param == "mysql":
        if os.environ.get("NUTRILENZ_TEST_MYSQL") != "1":
            pytest.skip("set NUTRILENZ_TEST_MYSQL=1 to run against MySQL")
        store = empty_mysql_store()
    else:
        store = InMemoryDataStore()
    data = DataManager(store)
    data.ensure_ready()
    return data


def record(data: DataManager, user, prod=None, flags=(Flag.GOAL_MISMATCH,), when=None) -> Analysis:
    analysis = Analysis(user.user_id, prod or product(), user.profile.snapshot(), ai_analysis(),
                        list(flags), [], 42.5, "gemini", when)
    return data.save_analysis(analysis)


class TestAccounts:
    def test_register_and_login(self, manager):
        user = manager.register("Jane", "secret123", [SUGAR_MAX_10, CALORIES_MAX_200], ["msg"])
        assert user.user_id is not None
        again = manager.authenticate("jane", "secret123")          # username ignores case
        assert again.user_id == user.user_id
        assert [g.nutrient.key for g in again.profile.goals] == ["sugar_g", "calories_kcal"]
        assert again.profile.avoid_ingredients == ("msg",)

    def test_wrong_password_and_unknown_user(self, manager):
        manager.register("jane", "secret123", [SUGAR_MAX_10], [])
        for name, password in (("jane", "nope"), ("ghost", "secret123")):
            with pytest.raises(AuthError):
                manager.authenticate(name, password)

    def test_duplicate_username(self, manager):
        manager.register("jane", "secret123", [SUGAR_MAX_10], [])
        with pytest.raises(DataError) as error:
            manager.register("JANE", "other1234", [SUGAR_MAX_10], [])
        assert error.value.code == "DUPLICATE_USER"

    def test_update_profile(self, manager):
        user = manager.register("sam", "secret123", [SUGAR_MAX_10], [])
        manager.update_profile(user, [PROTEIN_MIN_15], ["peanuts"])
        loaded = manager.get_user(user.user_id)
        assert [g.describe() for g in loaded.profile.goals] == ["Protein at least 15 g per serving"]
        assert loaded.profile.avoid_ingredients == ("peanuts",)

    def test_delete_account_removes_history_but_keeps_products(self, manager):
        user = manager.register("sam", "secret123", [SUGAR_MAX_10], [])
        record(manager, user)
        manager.delete_account(user.user_id)
        with pytest.raises(DataError):
            manager.get_user(user.user_id)
        assert len(manager.catalogue()) == 1
        with pytest.raises(DataError):
            manager.delete_account(user.user_id)


class TestAnalyses:
    def test_save_and_load_round_trip(self, manager):
        user = manager.register("jane", "secret123", [SUGAR_MAX_10], [])
        saved = record(manager, user)
        loaded = manager.get_analysis(user.user_id, saved.analysis_id)
        assert loaded.product.name == "Example Cereal"
        assert loaded.flags == (Flag.GOAL_MISMATCH,)
        assert loaded.ai_analysis.to_dict() == ai_analysis().to_dict()
        assert loaded.profile_snapshot == user.profile.snapshot()
        assert loaded.score == 42.5

    def test_history_newest_first_and_filters(self, manager):
        user = manager.register("jane", "secret123", [SUGAR_MAX_10], [])
        now = datetime(2026, 10, 30, 12, 0)
        record(manager, user, product(product_name="Old Oats"), [Flag.GOOD_MATCH], now - timedelta(days=2))
        record(manager, user, product(product_name="New Cereal"), [Flag.CLAIM_REVIEW], now)
        names = [r.product.name for r in manager.history(user.user_id)]
        assert names == ["New Cereal", "Old Oats"]
        assert [r.product.name for r in manager.history(user.user_id, Flag.GOOD_MATCH)] == ["Old Oats"]
        assert [r.product.name for r in manager.history(user.user_id, search="cere")] == ["New Cereal"]
        assert manager.history(user.user_id, Flag.MANUAL_REVIEW) == []

    def test_users_only_see_their_own_records(self, manager):
        jane = manager.register("jane", "secret123", [SUGAR_MAX_10], [])
        sam = manager.register("sam", "secret123", [SUGAR_MAX_10], [])
        saved = record(manager, jane)
        assert manager.history(sam.user_id) == []
        with pytest.raises(DataError):
            manager.get_analysis(sam.user_id, saved.analysis_id)
        with pytest.raises(DataError):
            manager.delete_analysis(sam.user_id, saved.analysis_id)

    def test_delete_one_analysis(self, manager):
        user = manager.register("jane", "secret123", [SUGAR_MAX_10], [])
        first, second = record(manager, user), record(manager, user)
        manager.delete_analysis(user.user_id, first.analysis_id)
        assert [r.analysis_id for r in manager.history(user.user_id)] == [second.analysis_id]

    def test_identical_products_are_stored_once(self, manager):
        user = manager.register("jane", "secret123", [SUGAR_MAX_10], [])
        record(manager, user, product())
        record(manager, user, product())
        record(manager, user, product(product_name="Other"))
        assert len(manager.catalogue()) == 2
        assert manager.previous_analyses(user.user_id, "example cereal") == 2


class TestFailuresAndSeeding:
    def test_unreachable_database_is_reported_not_crashed(self):
        store = MySQLDataStore("127.0.0.1", 1, "nobody", "x", "none", connect_timeout=1)
        data = DataManager(store)
        with pytest.raises(DataError) as error:
            data.ensure_ready()
        assert error.value.code == "DB_UNAVAILABLE" and not data.is_ready

    def test_schema_file_splits_into_four_tables(self):
        statements = MySQLDataStore.schema_statements()
        assert len(statements) == 4
        assert all(s.startswith("CREATE TABLE IF NOT EXISTS") for s in statements)

    def test_corrupt_json_column(self):
        with pytest.raises(DataError) as error:
            MySQLDataStore._json("{not json")
        assert error.value.code == "CORRUPT_DATA"

    def test_demo_data_seeded_once(self, manager):
        logic = LogicManager()
        assert DemoDataSeeder(manager, logic).seed_if_empty()
        assert not DemoDataSeeder(manager, logic).seed_if_empty()
        jane = manager.authenticate("jane", "jane12345")
        sam = manager.authenticate("sam", "sam12345")
        assert len(jane.profile.goals) == 2 and len(sam.profile.goals) == 2
        assert {g.nutrient.key for g in jane.profile.goals} != {g.nutrient.key for g in sam.profile.goals}
        assert len(manager.history(jane.user_id)) == 2 and len(manager.history(sam.user_id)) == 3
        assert len(manager.catalogue()) >= 10

    def test_broken_demo_file_is_skipped(self, tmp_path, data):
        broken = tmp_path / "demo.json"
        broken.write_text("{oops", encoding="utf-8")
        assert not DemoDataSeeder(data, LogicManager(), broken).seed_if_empty()
        assert data.is_empty()


class TestDietaryStorage:
    def test_multiple_saved_diets_load_strictest_in_both_stores(self, manager, caplog):
        import json
        user = manager.register("legacyradio", "secret123", [SUGAR_MAX_10], ["palm oil"], ["vegetarian"])
        legacy = ["vegetarian", "vegetarian_no_dairy", "vegan", "egg", "halal_friendly"]
        store = manager._store
        if isinstance(store, InMemoryDataStore):
            store._users[user.user_id]["dietary_checks"] = legacy
        else:
            connection = pymysql.connect(**mysql_settings())
            with connection.cursor() as cursor:
                cursor.execute("UPDATE users SET dietary_checks=%s WHERE user_id=%s",
                               (json.dumps(legacy), user.user_id))
            connection.commit()
            connection.close()
        loaded = manager.get_user(user.user_id)
        assert [check.key for check in loaded.profile.dietary_checks] == ["vegan", "egg", "halal_friendly"]
        assert loaded.profile.avoid_ingredients == ("palm oil",)
        assert 'multiple saved diets' in caplog.text

    def test_legacy_flags_and_history_filter_use_saved_concerns(self, manager, monkeypatch):
        from nutrilenz.logic.dietary_checker import DietaryChecker
        user = manager.register("legacydiet", "secret123", [SUGAR_MAX_10], [], ["nuts", "dairy"])
        prod = product(ingredient_text="HAZELNUTS, MILK")
        report = LogicManager().check_dietary(prod, user.profile)
        # Reproduce old rows with two saved concerns but missing DIETARY_REVIEW.
        saved = manager.save_analysis(Analysis(user.user_id, prod, user.profile.snapshot(), ai_analysis(),
            [Flag.GOAL_MISMATCH, Flag.GOOD_MATCH], [], 42, "gemini", dietary_report=report))
        old = record(manager, user, product(product_name="Before feature", ingredient_text="MILK"))
        manager.update_profile(user, [SUGAR_MAX_10], [], ["vegan"])
        monkeypatch.setattr(DietaryChecker, "evaluate", lambda *args: pytest.fail("History recalculated"))
        loaded = manager.get_analysis(user.user_id, saved.analysis_id)
        assert loaded.dietary_report == report and loaded.score == 42
        assert loaded.flags == (Flag.GOAL_MISMATCH, Flag.DIETARY_REVIEW)
        assert [r.analysis_id for r in manager.history(user.user_id, Flag.DIETARY_REVIEW)] == [saved.analysis_id]
        assert manager.history(user.user_id, Flag.GOOD_MATCH) == []
        assert manager.get_analysis(user.user_id, old.analysis_id).dietary_report.rules_version == "not-run"

    def test_profile_options_round_trip_and_clear(self, manager):
        user = manager.register("diet", "secret123", [SUGAR_MAX_10], ["palm oil"], ["vegetarian", "egg"])
        manager.update_profile(user, [SUGAR_MAX_10], ["palm oil"], ["vegetarian_no_dairy", "egg"])
        loaded = manager.get_user(user.user_id)
        assert [c.key for c in loaded.profile.dietary_checks] == ["vegetarian_no_dairy", "egg"]
        assert loaded.profile.avoid_ingredients == ("palm oil",)
        manager.update_profile(user, [SUGAR_MAX_10], ["palm oil"], [])
        assert manager.get_user(user.user_id).profile.dietary_checks == ()

    @pytest.mark.parametrize("text,status", [("MILK", DietaryStatus.POSSIBLE_CONCERN),
                                             ("Rice", DietaryStatus.NO_MATCH), ("", DietaryStatus.NOT_CHECKED)])
    def test_reports_and_scores_are_saved_not_recomputed(self, manager, monkeypatch, text, status):
        # Skipped until the services package is merged (step 4)
        AnalysisService = pytest.importorskip("nutrilenz.services.analysis_service").AnalysisService
        user = manager.register("diet", "secret123", [SUGAR_MAX_10], [], ["dairy"])
        ai, _, _ = make_ai(Replies.gemini(analysis_answer(goal_alignment="ALIGNED", claim_status="NO_CLAIM")))
        outcome = AnalysisService(ai, LogicManager(), manager).analyse(
            user, product(ingredient_text=text, nutrition={"sugar_g": 5}, marketing_claim=None))
        assert outcome.saved
        original = outcome.analysis
        assert original.dietary_report.results[0].status is status
        assert original.score == 100
        manager.update_profile(user, [PROTEIN_MIN_15], [], ["nuts"])
        monkeypatch.setitem(DietaryKeywords.GROUPS, "dairy", ("rice",))
        loaded = manager.get_analysis(user.user_id, original.analysis_id)
        assert loaded.dietary_report == original.dietary_report
        assert loaded.score == original.score
        assert loaded.profile_snapshot["dietary_checks"] == ["dairy"]
        assert bool(manager.history(user.user_id, Flag.DIETARY_REVIEW)) == (status is DietaryStatus.POSSIBLE_CONCERN)


@pytest.mark.skipif(os.environ.get("NUTRILENZ_TEST_MYSQL") != "1", reason="requires isolated MySQL test DB")
def test_mysql_legacy_upgrade_is_repeatable_and_keeps_records():
    store = empty_mysql_store()
    data = DataManager(store)
    data.ensure_ready()
    user = data.register("legacy", "secret123", [SUGAR_MAX_10], ["palm oil"])
    saved = record(data, user)
    connection = pymysql.connect(**mysql_settings())
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE users DROP COLUMN dietary_checks")
        cursor.execute("ALTER TABLE analyses DROP COLUMN dietary_results")
    connection.close()
    store.initialise()
    store.initialise()
    assert store.get_user(user.user_id).profile.dietary_checks == ()
    loaded = store.get_analysis(user.user_id, saved.analysis_id)
    assert loaded.dietary_report.results == () and loaded.flags == saved.flags
    assert loaded.score == saved.score
