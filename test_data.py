"""
test_data.py - persistence tests for the Data Manager

Runs inside a temporary folder, so your real data/ files are never touched.
Run:  python test_data.py
"""

import tempfile
from copy import deepcopy
from pathlib import Path

import data_manager
import io_manager
from sample_data import SAMPLE_PROFILES, SAMPLE_PRODUCTS, SAMPLE_AI_RESPONSES


def test_missing_files_mean_empty_lists(folder):
    assert data_manager.load_profiles(folder) == {"ok": True, "data": [], "error_code": None}
    assert data_manager.load_history(folder)["data"] == []


def test_save_reload_and_duplicate(folder):
    assert data_manager.save_profile(SAMPLE_PROFILES["jane"], folder)["ok"]
    assert data_manager.save_profile(SAMPLE_PROFILES["ari"], folder)["ok"]
    duplicate = dict(SAMPLE_PROFILES["jane"], profile_name="  jane ")
    assert data_manager.save_profile(duplicate, folder)["error_code"] == "DUPLICATE_PROFILE"
    assert len(data_manager.load_profiles(folder)["data"]) == 2


def test_snapshot_keeps_old_target(folder):
    jane = deepcopy(SAMPLE_PROFILES["jane"])
    record = data_manager.build_analysis(SAMPLE_PRODUCTS["cereal"], jane,
                                         SAMPLE_AI_RESPONSES["questionable_high"],
                                         ["GOAL_MISMATCH", "CLAIM_REVIEW"])
    assert data_manager.save_analysis(record, folder)["ok"]

    # Jane changes her target from 10 to 12
    jane["target_value"] = 12.0
    assert data_manager.save_profile(jane, folder, create=False)["ok"]

    history = data_manager.load_history(folder)["data"]
    assert history[0]["profile_snapshot"]["target_value"] == 10.0   # old record unchanged


def test_none_survives_round_trip(folder):
    record = data_manager.build_analysis(SAMPLE_PRODUCTS["missing_sugar"], SAMPLE_PROFILES["jane"],
                                         SAMPLE_AI_RESPONSES["questionable_low"], ["MANUAL_REVIEW"])
    data_manager.save_analysis(record, folder)
    saved = data_manager.load_history(folder)["data"][-1]
    assert saved["nutrition"]["sugar_g"] is None                     # null, not 0


def test_query_and_filter(folder):
    records = data_manager.load_history(folder)["data"]
    assert len(data_manager.query_history(records, "JANE")) == 2
    assert len(data_manager.query_history(records, "Jane", flag="MANUAL_REVIEW")) == 1
    assert data_manager.query_history(records, "Nobody") == []


def test_corrupt_file_is_not_overwritten(folder):
    path = Path(folder) / "profiles.json"
    path.write_text("{ this is broken", encoding="utf-8")
    assert data_manager.load_profiles(folder)["error_code"] == "CORRUPT_DATA"
    result = data_manager.save_profile(SAMPLE_PROFILES["sam"], folder)
    assert result["ok"] is False
    assert path.read_text(encoding="utf-8") == "{ this is broken"     # file left as it was


def run_tests():
    tests = [test_missing_files_mean_empty_lists, test_save_reload_and_duplicate,
             test_snapshot_keeps_old_target, test_none_survives_round_trip,
             test_query_and_filter, test_corrupt_file_is_not_overwritten]
    with tempfile.TemporaryDirectory() as folder:      # tests run in order, sharing this folder
        for test in tests:
            test(folder)
            io_manager.show_message("PASS  " + test.__name__)
    io_manager.show_message("\nAll {} data tests passed.".format(len(tests)))


if __name__ == "__main__":
    run_tests()
