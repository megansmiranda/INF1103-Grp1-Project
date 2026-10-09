import http.client
import io
import json
import logging
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

import ai_manager
from sample_data import (SAMPLE_PROFILES, SAMPLE_PRODUCTS, RAW_VALID, RAW_FENCED,
                         RAW_NOT_JSON, RAW_LIST, SAMPLE_AI_RESPONSES)

# All output goes through io_manager. Until the I/O branch is merged,
# fall back to the built-in display so this test can run on its own.
try:
    from io_manager import show_message
except ImportError:
    show_message = print

# Logic is optional here: if it is merged, the live demo also shows the final flags.
try:
    import logic_manager
except ImportError:
    logic_manager = None


def expect_value_error(function, *args):
    """Helper: assert that calling function(*args) raises ValueError."""
    try:
        function(*args)
    except ValueError:
        return
    raise AssertionError(function.__name__ + " should have raised ValueError")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def test_damaged_env_file_does_not_crash():
    with tempfile.TemporaryDirectory() as folder:
        env_path = Path(folder) / ".env"
        env_path.write_bytes(b"\xff\xfe\x00GEMINI_API_KEY=abc")   # not valid UTF-8
        ai_manager.load_env_file(env_path)                         # must not raise


# ---------------------------------------------------------------------------
# Payload and prompt
# ---------------------------------------------------------------------------

def test_payload_has_no_target_and_does_not_change_inputs():
    product = deepcopy(SAMPLE_PRODUCTS["cereal"])
    profile = deepcopy(SAMPLE_PROFILES["jane"])
    payload = ai_manager.build_ai_payload(product, profile)
    assert "target_value" not in payload            # numeric target is Logic's job
    assert payload["primary_goal"] == "REDUCE_SUGAR"
    assert product == SAMPLE_PRODUCTS["cereal"]     # input not modified
    # Changing the target must NOT change what the AI sees
    profile["target_value"] = 12.0
    assert ai_manager.build_ai_payload(product, profile) == payload


def test_prompt_contains_label_data():
    payload = ai_manager.build_ai_payload(SAMPLE_PRODUCTS["cereal"], SAMPLE_PROFILES["jane"])
    prompt = ai_manager.build_prompt(payload)
    assert "brown rice syrup" in prompt
    assert "REDUCE_SUGAR" in prompt
    for field in ai_manager.REQUIRED_FIELDS:
        assert field in prompt


def test_missing_value_sent_as_null():
    payload = ai_manager.build_ai_payload(SAMPLE_PRODUCTS["missing_sugar"], SAMPLE_PROFILES["jane"])
    assert '"sugar_g": null' in ai_manager.build_prompt(payload)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_parse_valid_and_fenced():
    assert ai_manager.parse_ai_response(RAW_VALID)["confidence"] == "HIGH"
    assert ai_manager.parse_ai_response(RAW_FENCED)["confidence"] == "HIGH"


def test_parse_rejects_bad_text():
    expect_value_error(ai_manager.parse_ai_response, RAW_NOT_JSON)
    expect_value_error(ai_manager.parse_ai_response, RAW_LIST)
    expect_value_error(ai_manager.parse_ai_response, "")


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_validate_accepts_good_response():
    good = deepcopy(SAMPLE_AI_RESPONSES["questionable_high"])
    assert ai_manager.validate_ai_response(good, has_claim=True) == good


def test_validate_rejects_bad_responses():
    base = SAMPLE_AI_RESPONSES["questionable_high"]

    missing = deepcopy(base)
    del missing["explanation"]
    expect_value_error(ai_manager.validate_ai_response, missing, True)

    extra = deepcopy(base)
    extra["flags"] = ["GOOD_MATCH"]                 # AI must not decide flags
    expect_value_error(ai_manager.validate_ai_response, extra, True)

    lowercase = deepcopy(base)
    lowercase["confidence"] = "high"
    expect_value_error(ai_manager.validate_ai_response, lowercase, True)

    evidence_string = deepcopy(base)
    evidence_string["evidence"] = "just a string"
    expect_value_error(ai_manager.validate_ai_response, evidence_string, True)

    no_evidence = deepcopy(base)
    no_evidence["evidence"] = []                    # every answer must quote the label
    expect_value_error(ai_manager.validate_ai_response, no_evidence, True)

    # has a claim status but the user never typed a claim
    expect_value_error(ai_manager.validate_ai_response, deepcopy(base), False)

    # user typed a claim but AI said NO_CLAIM
    no_claim = deepcopy(SAMPLE_AI_RESPONSES["aligned_no_claim"])
    expect_value_error(ai_manager.validate_ai_response, no_claim, True)


# ---------------------------------------------------------------------------
# Broken API replies, using a FAKE urlopen (no internet)
# ---------------------------------------------------------------------------

def post_with_fake_reply(body):
    """Run _post_json with urlopen replaced by a fake.
    body is the reply bytes, or an exception to raise as if the download failed."""
    def fake_urlopen(request, timeout):
        if isinstance(body, Exception):
            raise body
        return io.BytesIO(body)      # behaves like a reply: supports 'with' and read()

    original = ai_manager.urllib.request.urlopen
    ai_manager.urllib.request.urlopen = fake_urlopen
    try:
        return ai_manager._post_json("https://example.test", {}, {})
    finally:
        ai_manager.urllib.request.urlopen = original


def test_cut_off_download_is_connection_error():
    cut_off = http.client.IncompleteRead(b'{"candidates": [', 500)
    assert post_with_fake_reply(cut_off) == (None, "API_CONNECTION_ERROR")


def test_unreadable_or_wrong_shape_reply_is_invalid_response():
    assert post_with_fake_reply(b"\xff\xfe not utf-8") == (None, "INVALID_RESPONSE")
    assert post_with_fake_reply(b"<html>Bad Gateway</html>") == (None, "INVALID_RESPONSE")
    assert post_with_fake_reply(b"[1, 2, 3]") == (None, "INVALID_RESPONSE")
    assert post_with_fake_reply(b'{"ok": 1}') == ({"ok": 1}, None)


def make_http_error(code, body):
    return ai_manager.urllib.error.HTTPError("https://example.test", code, "Bad Request",
                                             {}, io.BytesIO(body))


def test_http_errors_map_to_codes_and_log_provider_reason():
    wrong_model = b'{"error": {"message": "models/gemini-x is not found"}}'
    assert ai_manager._error_reason(make_http_error(404, wrong_model)) == "models/gemini-x is not found"
    assert ai_manager._error_reason(make_http_error(500, b"not json")) == "Bad Request"
    assert post_with_fake_reply(make_http_error(404, wrong_model)) == (None, "CONFIGURATION_ERROR")
    assert post_with_fake_reply(make_http_error(401, b"")) == (None, "AUTHENTICATION_ERROR")
    assert post_with_fake_reply(make_http_error(429, b"")) == (None, "API_UNAVAILABLE")


# ---------------------------------------------------------------------------
# Retry + fallback logic, using FAKE providers (no internet)
# ---------------------------------------------------------------------------

def run_with_fake_providers(fake_providers):
    """Temporarily replace get_providers() with fakes, run analyse_product, restore."""
    original = ai_manager.get_providers
    ai_manager.get_providers = lambda: fake_providers
    try:
        return ai_manager.analyse_product(SAMPLE_PRODUCTS["cereal"], SAMPLE_PROFILES["jane"])
    finally:
        ai_manager.get_providers = original


def make_fake(name, replies, call_log):
    """A fake provider that returns the given (text, error) replies in order."""
    def fake_call(prompt, api_key, model):
        call_log.append(name)
        return replies[len([n for n in call_log if n == name]) - 1]
    return {"name": name, "api_key": "x", "model": "fake", "call": fake_call}


def test_retry_once_after_invalid_output():
    calls = []
    fake = make_fake("gemini", [(RAW_NOT_JSON, None), (RAW_VALID, None)], calls)
    result = run_with_fake_providers([fake])
    assert result["ok"] is True
    assert calls == ["gemini", "gemini"]


def test_gives_up_after_two_bad_answers():
    calls = []
    fake = make_fake("gemini", [(RAW_NOT_JSON, None), (RAW_LIST, None)], calls)
    result = run_with_fake_providers([fake])
    assert result == {"ok": False, "ai_analysis": None,
                      "error_code": "INVALID_RESPONSE", "provider": None}
    assert len(calls) == 2                          # bounded: no infinite retry


def test_falls_back_to_groq_when_gemini_key_rejected():
    calls = []
    gemini = make_fake("gemini", [(None, "AUTHENTICATION_ERROR")], calls)
    groq = make_fake("groq", [(RAW_VALID, None)], calls)
    result = run_with_fake_providers([gemini, groq])
    assert result["ok"] is True and result["provider"] == "groq"
    assert calls == ["gemini", "groq"]              # bad key is not retried


def test_all_attempts_fail_with_one_pause_per_retry_only():
    calls, pauses = [], []
    gemini = make_fake("gemini", [(None, "API_UNAVAILABLE")] * 2, calls)
    groq = make_fake("groq", [(None, "API_UNAVAILABLE")] * 2, calls)
    original_sleep = ai_manager.time.sleep
    ai_manager.time.sleep = pauses.append            # record pauses instead of waiting
    try:
        result = run_with_fake_providers([gemini, groq])
    finally:
        ai_manager.time.sleep = original_sleep
    assert result == {"ok": False, "ai_analysis": None,
                      "error_code": "API_UNAVAILABLE", "provider": None}
    assert calls == ["gemini", "gemini", "groq", "groq"]
    assert len(pauses) == 2                         # before each retry, none after the last try


def test_no_api_keys_is_configuration_error():
    result = run_with_fake_providers([])
    assert result["ok"] is False and result["error_code"] == "CONFIGURATION_ERROR"


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

def run_offline_tests():
    tests = [
        test_damaged_env_file_does_not_crash,
        test_payload_has_no_target_and_does_not_change_inputs,
        test_prompt_contains_label_data,
        test_missing_value_sent_as_null,
        test_parse_valid_and_fenced,
        test_parse_rejects_bad_text,
        test_validate_accepts_good_response,
        test_validate_rejects_bad_responses,
        test_cut_off_download_is_connection_error,
        test_unreadable_or_wrong_shape_reply_is_invalid_response,
        test_http_errors_map_to_codes_and_log_provider_reason,
        test_retry_once_after_invalid_output,
        test_gives_up_after_two_bad_answers,
        test_falls_back_to_groq_when_gemini_key_rejected,
        test_all_attempts_fail_with_one_pause_per_retry_only,
        test_no_api_keys_is_configuration_error,
    ]
    logging.disable(logging.CRITICAL)   # hide the expected warnings from the fake failures
    for test in tests:
        test()
        show_message("PASS  " + test.__name__)
    show_message("\nAll {} AI manager offline tests passed.".format(len(tests)))


def run_live_demo():
    """Send each hardcoded sample through the REAL API, then through Logic."""
    if "groq" in sys.argv:
        os.environ["GEMINI_API_KEY"] = ""           # disable Gemini to test the backup
    pairs = [("cereal", "jane"), ("protein_bar", "sam"),
             ("noodles", "ari"), ("missing_sugar", "jane")]
    for product_key, profile_key in pairs:
        product, profile = SAMPLE_PRODUCTS[product_key], SAMPLE_PROFILES[profile_key]
        show_message("\n=== {} for {} ===".format(product["product_name"],
                                                            profile["profile_name"]))
        result = ai_manager.analyse_product(product, profile)
        show_message(json.dumps(result, indent=2))
        if result["ok"] and logic_manager:
            flags = logic_manager.evaluate_product(product, profile, result["ai_analysis"])
            show_message("Logic flags: " + str(flags))


if __name__ == "__main__":
    if "live" in sys.argv:
        run_live_demo()
    else:
        run_offline_tests()
