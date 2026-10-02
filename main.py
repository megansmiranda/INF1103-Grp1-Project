"""
main.py - PROGRAM ENTRY POINT  (owner: integration / main.py owner)

main.py is the "conductor". It holds no business rules, no prints and no file
code. It only calls the four managers in the right order:

   User -> io_manager -> ai_manager -> logic_manager -> data_manager -> io_manager

Run with:  python main.py
"""

import logging
import os
from pathlib import Path

import io_manager
import ai_manager
import logic_manager
import data_manager

# Where JSON files and the log live. Docker sets NUTRILENZ_DATA_DIR=/app/data.
DATA_DIR = Path(os.environ.get(
    "NUTRILENZ_DATA_DIR", str(Path(__file__).resolve().parent / "data")))

# Turn error codes from the managers into friendly messages for the user
ERROR_MESSAGES = {
    "CORRUPT_DATA": "A saved data file is damaged. It was NOT changed. Please check the data folder.",
    "READ_ERROR": "A saved data file could not be read.",
    "WRITE_ERROR": "The data could not be saved to disk.",
    "DUPLICATE_PROFILE": "A profile with that name already exists. Please choose another name.",
    "PROFILE_NOT_FOUND": "That profile no longer exists in the saved file.",
    "INVALID_RECORD": "The analysis record was incomplete and was not saved.",
    "CONFIGURATION_ERROR": "AI is not configured correctly (check the API keys/model in .env).",
    "AUTHENTICATION_ERROR": "The AI service rejected the API key.",
    "API_CONNECTION_ERROR": "Could not reach the AI service. Check your internet connection.",
    "API_UNAVAILABLE": "The AI service is busy or unavailable. Please try again later.",
    "INVALID_RESPONSE": "The AI gave an unusable answer twice. Please try again.",
}


def error_text(error_code):
    return ERROR_MESSAGES.get(error_code, "Something went wrong (" + str(error_code) + ").")


def setup_logging():
    """Send warnings/errors (e.g. API failures) to data/nutrilenz.log, not the screen."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(DATA_DIR / "nutrilenz.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# ===========================================================================
# One small function per menu option. Each returns the (possibly new) active profile.
# ===========================================================================

def handle_create_profile(active_profile):
    profile = io_manager.collect_profile()
    result = data_manager.save_profile(profile, DATA_DIR, create=True)
    if result["ok"]:
        io_manager.show_message("Profile saved. Active profile: " + profile["profile_name"])
        return profile
    io_manager.show_message("Profile was not saved. " + error_text(result["error_code"]))
    return active_profile


def handle_select_profile(active_profile):
    loaded = data_manager.load_profiles(DATA_DIR)
    if not loaded["ok"]:
        io_manager.show_message(error_text(loaded["error_code"]))
        return active_profile
    chosen = io_manager.select_profile(loaded["data"])
    if chosen is None:                     # Back: keep whatever was active before
        return active_profile
    io_manager.show_message("Active profile: " + chosen["profile_name"])
    return chosen


def handle_analyse(active_profile):
    # 1. INPUT: collect and confirm the product (None = user cancelled)
    product = io_manager.collect_product(active_profile)
    if product is None:
        io_manager.show_message("Cancelled. Nothing was sent to the AI.")
        return active_profile

    # 2. AI: interpret ingredients and claim
    io_manager.show_message("\nAnalysing label with AI, please wait...")
    ai_result = ai_manager.analyse_product(product, active_profile)
    if not ai_result["ok"]:
        io_manager.show_message("Analysis could not be completed. " + error_text(ai_result["error_code"]))
        return active_profile
    ai_analysis = ai_result["ai_analysis"]

    # 3. LOGIC: apply business rules -> flags
    flags = logic_manager.evaluate_product(product, active_profile, ai_analysis)

    # 4. DATA: build the full record (with profile snapshot) and save it
    record = data_manager.build_analysis(product, active_profile, ai_analysis, flags)
    saved = data_manager.save_analysis(record, DATA_DIR)

    # 5. OUTPUT: show result and honest save status
    io_manager.show_analysis(record)
    io_manager.show_message("(AI provider used: " + ai_result["provider"] + ")")
    if saved["ok"]:
        io_manager.show_message("Analysis saved.")
    else:
        io_manager.show_message("Result displayed, but it was NOT saved. " + error_text(saved["error_code"]))
    return active_profile


def handle_history(active_profile):
    # History only READS saved records: no AI call, no new flags, no re-saving.
    loaded = data_manager.load_history(DATA_DIR)
    if not loaded["ok"]:
        io_manager.show_message("Saved history could not be loaded. " + error_text(loaded["error_code"]))
        return active_profile
    records = data_manager.query_history(loaded["data"], active_profile["profile_name"])
    selected = io_manager.show_history(records, active_profile)
    if selected is not None:
        io_manager.show_analysis(selected)
    return active_profile


def handle_update_profile(active_profile):
    updated = io_manager.update_profile(active_profile)
    if updated is None:
        io_manager.show_message("Update cancelled.")
        return active_profile
    result = data_manager.save_profile(updated, DATA_DIR, create=False)
    if result["ok"]:
        io_manager.show_message("Profile saved. New analyses will use: "
                                + io_manager.describe_target(updated))
        return updated                     # only switch to new settings after a successful save
    io_manager.show_message("Profile was not updated. " + error_text(result["error_code"]))
    return active_profile


# Menu choice -> handler function
MENU_ACTIONS = {
    "1": handle_create_profile,
    "2": handle_select_profile,
    "3": handle_analyse,
    "4": handle_history,
    "5": handle_update_profile,
}
NEEDS_PROFILE = ("3", "4", "5")


def main():
    setup_logging()

    # Load saved data on startup and report any damaged files
    for loaded, name in ((data_manager.load_profiles(DATA_DIR), "profiles"),
                         (data_manager.load_history(DATA_DIR), "history")):
        if not loaded["ok"]:
            io_manager.show_message("Warning (" + name + "): " + error_text(loaded["error_code"]))

    active_profile = None
    while True:
        choice = io_manager.show_main_menu(active_profile)
        if choice == "0":
            io_manager.show_message("Goodbye.")
            break
        if choice in NEEDS_PROFILE and active_profile is None:
            io_manager.show_message("Please create or select a profile first.")
            continue
        active_profile = MENU_ACTIONS[choice](active_profile)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        io_manager.show_message("\nGoodbye.")
