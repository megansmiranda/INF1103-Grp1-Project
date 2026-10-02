"""
io_manager.py - INPUT / OUTPUT LAYER  (owner: I/O Person A + Person B)

This is the ONLY file in the project allowed to use print() and input().
Its jobs:
  1. Ask the user for data and VALIDATE it (reject + re-prompt on bad input).
  2. Return clean Python dictionaries to main.py.
  3. Display menus, single records (show_analysis) and list/summary views
     (select_profile, show_history).

It never calls the AI, never decides flags and never reads/writes files.
"""

import math
import textwrap

# ---------------------------------------------------------------------------
# Shared lookup tables (used only for asking questions and displaying text)
# ---------------------------------------------------------------------------

# Menu number -> goal code stored in the profile
GOAL_CHOICES = {"1": "REDUCE_SUGAR", "2": "HIGH_PROTEIN", "3": "LOWER_SODIUM"}

# Goal code -> how to talk about it on screen
GOAL_INFO = {
    "REDUCE_SUGAR": {"label": "Reduce Sugar", "nutrient": "sugar",
                     "direction": "maximum", "unit": "g", "unit_code": "g_per_serving"},
    "HIGH_PROTEIN": {"label": "High Protein", "nutrient": "protein",
                     "direction": "minimum", "unit": "g", "unit_code": "g_per_serving"},
    "LOWER_SODIUM": {"label": "Lower Sodium", "nutrient": "sodium",
                     "direction": "maximum", "unit": "mg", "unit_code": "mg_per_serving"},
}

# Flag code -> friendly sentence shown to the user
FLAG_DESCRIPTIONS = {
    "GOAL_MISMATCH": "The product does not meet your selected target.",
    "CLAIM_REVIEW": "The marketing claim needs a closer look (see evidence).",
    "MANUAL_REVIEW": "Please check the label yourself; the analysis needs review.",
    "GOOD_MATCH": "Matches your selected goal based on the supplied information.",
}

LINE = "=" * 60


# ===========================================================================
# PERSON A - A1/A2: reusable input helpers
# ===========================================================================

def read_required_text(prompt):
    """Keep asking until the user types something that is not blank.
    Returns the text with outer spaces removed."""
    while True:
        text = input(prompt).strip()
        if text:
            return text
        print("  This field cannot be empty. Please try again.")


def read_optional_text(prompt):
    """Ask for optional text. Blank input returns None (meaning 'not given')."""
    text = input(prompt).strip()
    return text if text else None


def read_choice(prompt, allowed_choices):
    """Keep asking until the answer is one of allowed_choices (a list of strings)."""
    while True:
        choice = input(prompt).strip()
        if choice in allowed_choices:
            return choice
        print("  Invalid choice. Please enter one of: " + ", ".join(allowed_choices))


def read_yes_no(prompt):
    """Ask a Y/N question. Returns True for Y, False for N."""
    answer = read_choice(prompt, ["Y", "N", "y", "n"])
    return answer.upper() == "Y"


def read_number(prompt, allow_missing=False, allow_zero=False):
    """Ask for a number and validate it.

    allow_missing=True -> blank input returns None (value not on label)
    allow_zero=True    -> 0 is accepted (e.g. 0 g sugar is a real value)
    Rejects: letters, negative numbers, 'nan', 'inf'.
    Returns a float, or None only when allow_missing is True.
    """
    while True:
        raw = input(prompt).strip()

        # 1. Blank input
        if raw == "":
            if allow_missing:
                return None
            print("  A number is required.")
            continue

        # 2. Must convert to a number
        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a number only (e.g. 10 or 10.5), without units.")
            continue

        # 3. float() accepts 'nan' and 'inf' - we do not want those
        if not math.isfinite(value):
            print("  Please enter a normal number.")
            continue

        # 4. Range checks
        if value < 0:
            print("  The number cannot be negative.")
            continue
        if value == 0 and not allow_zero:
            print("  The number must be greater than 0.")
            continue

        return value


def read_ingredient_list(prompt):
    """Read comma-separated words into a clean list. Blank input returns []."""
    raw = input(prompt)
    items = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            items.append(part)
    return items
