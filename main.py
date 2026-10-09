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

# Team-agreed "unusually high" warning limits per serving, checked by Logic before the
# AI call. Keys: "sugar_g" and "protein_g" in grams, "sodium_mg" in milligrams.
# Empty = validation only (io_manager already rejects values above its hard maximums).
UNUSUAL_NUMBER_LIMITS = {}

# Turn error codes from the managers into friendly messages for the user
ERROR_MESSAGES = {
    "CORRUPT_DATA": "A saved data file is damaged. It was NOT changed. Please check the data folder.",
    "READ_ERROR": "A saved data file could not be read.",
    "WRITE_ERROR": "The data could not be saved to disk.",
    "DUPLICATE_PROFILE": "A profile with that name already exists. Please choose another name.",
    "PROFILE_NOT_FOUND": "That profile no longer exists in the saved file.",
    "INVALID_RECORD": "The analysis record was incomplete and was not saved.",
    "CONFIGURATION_ERROR": "AI is not set up correctly (check the API keys and model names in .env).",
    "AUTHENTICATION_ERROR": "The AI service rejected the API key.",
    "API_CONNECTION_ERROR": "Could not reach the AI service. Check your internet connection.",
    "API_UNAVAILABLE": "The AI service is busy or unavailable. Please try again later.",
    "INVALID_RESPONSE": "The AI did not give a usable answer after the allowed attempts.",
}


def error_text(error_code):
    return ERROR_MESSAGES.get(error_code, "Something went wrong (" + str(error_code) + ").")


def setup_logging():
    """Send warnings/errors (e.g. API failures) to data/nutrilenz.log, not the screen.
    Returns False if the log file cannot be created; the app still runs without it."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=str(DATA_DIR / "nutrilenz.log"), level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        return True
    except OSError:
        logging.disable(logging.CRITICAL)      # never let log messages spill onto the screen
        return False


# ===========================================================================
# One small function per menu option. Each returns the (possibly new) active profile.
# ===========================================================================

def handle_create_profile(active_profile):
    loaded = data_manager.load_profiles(DATA_DIR)
    if not loaded["ok"]:
        io_manager.show_message("Saved profiles could not be loaded. "
                                + error_text(loaded["error_code"]))
        return active_profile
    profile = io_manager.collect_profile(loaded["data"])
    if profile is None:                    # user typed quit: nothing is saved
        return active_profile
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


def count_previous_analyses(product_name, profile_name):
    """How many saved analyses of this product the profile already has.
    Names match ignoring capital letters and outer spaces. Returns None if
    the history file cannot be read."""
    loaded = data_manager.load_history(DATA_DIR)
    if not loaded["ok"]:
        return None
    wanted = product_name.strip().casefold()
    return sum(1 for record in data_manager.query_history(loaded["data"], profile_name)
               if record["product_name"].strip().casefold() == wanted)


def save_with_retry(record):
    """Save a finished analysis. If saving fails, offer to retry WITHOUT another AI call."""
    while True:
        saved = data_manager.save_analysis(record, DATA_DIR)
        if saved["ok"]:
            io_manager.show_message("Analysis saved.")
            return
        io_manager.show_message("Analysis completed, but it could not be saved. "
                                + error_text(saved["error_code"]))
        if not io_manager.read_yes_no("Retry saving this result? (Y/Yes or N/No): "):
            io_manager.show_message("The result was NOT saved.")
            return


def handle_analyse(active_profile):
    # 1. INPUT: product name first, so repeats are caught before typing the whole label
    product_name = io_manager.collect_product_name(active_profile)
    previous = count_previous_analyses(product_name, active_profile["profile_name"])
    if previous is None:
        io_manager.show_message("Note: saved history could not be checked for repeats.")
    elif previous > 0 and not io_manager.confirm_repeat_analysis(product_name, previous):
        io_manager.show_message("Analysis cancelled. No new analysis was created.")
        return active_profile

    product = io_manager.collect_product(active_profile, product_name)
    if product is None:
        io_manager.show_message("Cancelled. Nothing was sent to the AI.")
        return active_profile

    # 2. LOGIC: check the numbers BEFORE spending an AI call on them
    try:
        warnings = logic_manager.check_unusual_numbers(product, UNUSUAL_NUMBER_LIMITS)
    except ValueError as problem:
        io_manager.show_message("The product details are invalid: " + str(problem))
        return active_profile
    if warnings:
        for warning in warnings:
            io_manager.show_message("Warning: " + warning)
        if not io_manager.read_yes_no("Analyse with these values anyway? (Y/Yes or N/No): "):
            io_manager.show_message("Cancelled. Nothing was sent to the AI.")
            return active_profile

    # 3. AI: interpret ingredients and claim
    io_manager.show_message("\nAnalysing label with AI, please wait...")
    ai_result = ai_manager.analyse_product(product, active_profile)
    if not ai_result["ok"]:
        io_manager.show_message("Analysis could not be completed. " + error_text(ai_result["error_code"])
                                + "\nNo new analysis was saved.")
        return active_profile

    # 4. LOGIC: apply business rules -> flags
    try:
        flags = logic_manager.evaluate_product(product, active_profile, ai_result["ai_analysis"])
    except ValueError as problem:
        io_manager.show_message("The analysis could not be evaluated: " + str(problem))
        return active_profile

    # 5. DATA + OUTPUT: build the record (with profile snapshot), show it, then save it
    record = data_manager.build_analysis(product, active_profile, ai_result["ai_analysis"], flags)
    io_manager.show_analysis(record)
    io_manager.show_message("(AI service used: " + ai_result["provider"] + ")")
    save_with_retry(record)
    return active_profile


def handle_history(active_profile):
    # History only READS saved records: no AI call, no new flags, no re-saving.
    loaded = data_manager.load_history(DATA_DIR)
    if not loaded["ok"]:
        io_manager.show_message("Saved history could not be loaded. " + error_text(loaded["error_code"]))
        return active_profile
    records = data_manager.query_history(loaded["data"], active_profile["profile_name"])
    action, record = io_manager.show_history(records, active_profile)
    if action == "view":
        io_manager.show_analysis(record)
    elif action == "delete":
        delete_saved_analysis(record)
    return active_profile


def delete_saved_analysis(record):
    """The user has already confirmed in io_manager. Data does the file change."""
    # TODO: call data_manager.delete_analysis directly once the Data branch adds it
    delete_analysis = getattr(data_manager, "delete_analysis", None)
    if delete_analysis is None:
        io_manager.show_message("Deleting saved analyses is not available yet. Nothing was deleted.")
        return
    result = delete_analysis(record, DATA_DIR)
    if result["ok"]:
        io_manager.show_message("Analysis deleted. Your other analyses were kept.")
    else:
        io_manager.show_message("The analysis was NOT deleted. " + error_text(result["error_code"]))


def handle_update_profile(active_profile):
    updated = io_manager.update_profile(active_profile)
    if updated is None:
        io_manager.show_message("Update cancelled.")
        return active_profile
    result = data_manager.save_profile(updated, DATA_DIR, create=False)
    if result["ok"]:
        io_manager.show_message("Profile updated.")
        return updated                     # only switch to new settings after a successful save
    io_manager.show_message("Profile was not updated. " + error_text(result["error_code"]))
    return active_profile


def handle_delete_profile(active_profile):
    if active_profile is None:
        io_manager.show_message("Please create or select a profile first.")
        return active_profile

    history = data_manager.load_history(DATA_DIR)
    if not history["ok"]:
        io_manager.show_message("Saved history could not be loaded. " + error_text(history["error_code"]))
        return active_profile
    count = len(data_manager.query_history(history["data"], active_profile["profile_name"]))

    if not io_manager.confirm_delete_profile(active_profile, count):
        io_manager.show_message("Deletion cancelled.")
        return active_profile

    result = data_manager.delete_profile(active_profile["profile_name"], DATA_DIR)
    if not result["ok"]:
        io_manager.show_message("The profile was NOT deleted. " + error_text(result["error_code"]))
        return active_profile

    io_manager.show_message("Profile deleted: " + active_profile["profile_name"])
    io_manager.show_message("No active profile. Please create or select one.")
    return None


# Menu choice -> handler function
MENU_ACTIONS = {
    "1": handle_create_profile,
    "2": handle_select_profile,
    "3": handle_analyse,
    "4": handle_history,
    "5": handle_update_profile,
    "6": handle_delete_profile,
}
NEEDS_PROFILE = ("3", "4", "5", "6")


def main():
    if not setup_logging():
        io_manager.show_message("Warning: the log file could not be created. "
                                "NutriLenz will run, but errors will not be logged.")

    # Load saved data on startup and report any damaged files
    for loaded, name in ((data_manager.load_profiles(DATA_DIR), "profiles"),
                         (data_manager.load_history(DATA_DIR), "history")):
        if not loaded["ok"]:
            io_manager.show_message("Warning (" + name + "): " + error_text(loaded["error_code"]))

    active_profile = None
    while True:
        choice = io_manager.show_main_menu(active_profile)
        if choice == "0":
            if io_manager.read_yes_no("Are you sure you want to leave NutriLenz? (Y/Yes or N/No): "):
                io_manager.show_message("Thank you for using NutriLenz. Goodbye!")
                break
            io_manager.show_message("Exit cancelled.")
            continue
        if choice in NEEDS_PROFILE and active_profile is None:
            io_manager.show_message("Please create or select a profile first.")
            continue
        active_profile = MENU_ACTIONS[choice](active_profile)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        io_manager.show_message("\nGoodbye.")