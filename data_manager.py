"""
data_manager.py - DATA LAYER  (owner: Data Manager)

The system's memory across runs. Stores two JSON files in the data folder:
  profiles.json  - list of user profiles
  analyses.json  - list of completed analyses (with a snapshot of the profile)

Every load/save function returns a status envelope:
  success: {"ok": True,  "data": [...],  "error_code": None}
  failure: {"ok": False, "data": None,   "error_code": "CORRUPT_DATA"}

Error codes: CORRUPT_DATA, READ_ERROR, WRITE_ERROR, DUPLICATE_PROFILE, PROFILE_NOT_FOUND
A MISSING file is normal on first run (empty list). A BROKEN file is an error and
is never overwritten, so the user does not silently lose data.
No printing, no keyboard input, no AI calls here.
"""

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path

PROFILES_FILE = "profiles.json"
ANALYSES_FILE = "analyses.json"

PROFILE_KEYS = ("profile_name", "primary_goal", "target_value", "target_unit", "avoid_ingredients")
ANALYSIS_KEYS = ("product_name", "brand", "category", "nutrition", "ingredient_text",
                 "marketing_claim", "profile_snapshot", "ai_analysis", "flags")


def _ok(data):
    return {"ok": True, "data": data, "error_code": None}


def _fail(error_code):
    return {"ok": False, "data": None, "error_code": error_code}


# ===========================================================================
# Low-level helpers: read and write a JSON list safely
# ===========================================================================

def _load_list(path, required_keys):
    """Read a JSON file that should contain a list of dictionaries."""
    path = Path(path)
    if not path.exists():
        return _ok([])                                   # first run: nothing saved yet
    try:
        with open(path, "r", encoding="utf-8") as file:
            records = json.load(file)
    except json.JSONDecodeError:
        return _fail("CORRUPT_DATA")                     # file exists but is broken
    except OSError:
        return _fail("READ_ERROR")                       # permission problem, etc.

    # Structure check: must be a list of dicts that have all required keys
    if not isinstance(records, list):
        return _fail("CORRUPT_DATA")
    for record in records:
        if not isinstance(record, dict) or any(key not in record for key in required_keys):
            return _fail("CORRUPT_DATA")
    return _ok(records)


def _write_list(path, records):
    """Save a list to JSON. We write to a temporary file first and then swap it in,
    so a crash halfway through cannot destroy the previous good file."""
    path = Path(path)
    temp_path = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, ensure_ascii=False, allow_nan=False)
        os.replace(temp_path, path)
        return True
    except (OSError, ValueError):
        if temp_path.exists():
            temp_path.unlink()
        return False


def _same_name(a, b):
    """Profile names are compared ignoring case and outer spaces."""
    return a.strip().casefold() == b.strip().casefold()


# ===========================================================================
# Profiles
# ===========================================================================

def load_profiles(data_dir):
    """Load all saved profiles (called on startup and when selecting)."""
    return _load_list(Path(data_dir) / PROFILES_FILE, PROFILE_KEYS)


def save_profile(profile, data_dir, create=True):
    """create=True  -> add a new profile (rejects duplicate names)
       create=False -> replace the existing profile with the same name"""
    loaded = load_profiles(data_dir)
    if not loaded["ok"]:
        return loaded                                    # never overwrite a broken file

    profiles = loaded["data"]
    index = None
    for i, existing in enumerate(profiles):
        if _same_name(existing["profile_name"], profile["profile_name"]):
            index = i

    if create and index is not None:
        return _fail("DUPLICATE_PROFILE")
    if not create and index is None:
        return _fail("PROFILE_NOT_FOUND")

    if create:
        profiles.append(deepcopy(profile))
    else:
        profiles[index] = deepcopy(profile)

    if not _write_list(Path(data_dir) / PROFILES_FILE, profiles):
        return _fail("WRITE_ERROR")
    return _ok(profiles)


# ===========================================================================
# Analyses (history)
# ===========================================================================

def load_history(data_dir):
    """Load all saved analyses."""
    return _load_list(Path(data_dir) / ANALYSES_FILE, ANALYSIS_KEYS)


def build_analysis(product, profile, ai_analysis, flags):
    """Combine everything into ONE record. deepcopy makes a frozen snapshot of the
    profile, so if the user later changes their target, old results still show
    the target that was used at the time."""
    record = deepcopy(product)
    record["profile_snapshot"] = deepcopy(profile)
    record["ai_analysis"] = deepcopy(ai_analysis)
    record["flags"] = list(flags)
    record["analysed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return record


def save_analysis(record, data_dir):
    """Append one completed record to analyses.json."""
    if any(key not in record for key in ANALYSIS_KEYS):
        return _fail("INVALID_RECORD")
    loaded = load_history(data_dir)
    if not loaded["ok"]:
        return loaded                                    # never overwrite a broken file

    records = loaded["data"] + [deepcopy(record)]
    if not _write_list(Path(data_dir) / ANALYSES_FILE, records):
        return _fail("WRITE_ERROR")
    return _ok(records)


# ===========================================================================
# Query / filter functions
# ===========================================================================

def query_history(records, profile_name, flag=None):
    """Return records belonging to one profile, in saved order.
    Optional: flag="GOAL_MISMATCH" keeps only records that have that flag."""
    results = []
    for record in records:
        if not _same_name(record["profile_snapshot"]["profile_name"], profile_name):
            continue
        if flag is not None and flag not in record["flags"]:
            continue
        results.append(record)
    return results
