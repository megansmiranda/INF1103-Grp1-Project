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


# ===========================================================================
# PERSON A - A5: menu and messages
# ===========================================================================

def show_main_menu(active_profile):
    """Display the main menu once and return the user's choice as a string."""
    name = active_profile["profile_name"] if active_profile else "None"
    print("\n" + LINE)
    print(" NutriLenz - AI Food Label Interpreter")
    print(" Active profile: " + name)
    print(LINE)
    print(" 1. Create a profile")
    print(" 2. Select a saved profile")
    print(" 3. Analyse a product")
    print(" 4. View previous analyses")
    print(" 5. Update active profile")
    print(" 0. Exit")
    return read_choice("Choose: ", ["0", "1", "2", "3", "4", "5"])


def show_message(message):
    """Print any message given by main.py (the only way other files 'talk')."""
    print(message)


# ===========================================================================
# PERSON B - B1/B2: product entry and confirmation
# ===========================================================================

def _fmt(value, unit):
    """Show a nutrition value, or 'Not provided' when it is None.
    (We check 'is None' so that 0 is still shown as 0.)"""
    if value is None:
        return "Not provided"
    return "{:g} {}".format(value, unit)


def collect_product(profile):
    """Ask for one product label. Returns a product dictionary,
    or None if the user says N at the confirmation step."""
    print("\n--- ANALYSE A PRODUCT ---")
    #print("Profile: {} | {}".format(profile["profile_name"], describe_target(profile)))
    print("Enter nutrition values PER SERVING. Press Enter if a value is not on the label.")

    product_name = read_required_text("Product name: ")
    brand = read_optional_text("Brand (optional): ")
    category = read_optional_text("Category (optional): ")
    sugar = read_number("Sugar per serving (g; Enter if missing): ", allow_missing=True, allow_zero=True)
    protein = read_number("Protein per serving (g; Enter if missing): ", allow_missing=True, allow_zero=True)
    sodium = read_number("Sodium per serving (mg; Enter if missing): ", allow_missing=True, allow_zero=True)
    ingredients = read_required_text("Ingredients (copy from label): ")
    claim = read_optional_text("Marketing claim (optional, e.g. 'Low Sugar'): ")

    product = {
        "product_name": product_name,
        "brand": brand,
        "category": category,
        "nutrition": {"sugar_g": sugar, "protein_g": protein, "sodium_mg": sodium},
        "ingredient_text": ingredients,
        "marketing_claim": claim,
    }

    if confirm_product(product, profile):
        return product
    return None


def confirm_product(product, profile):
    """Show a summary of what was typed and ask Y/N. Returns True or False."""
    n = product["nutrition"]
    print("\n--- PLEASE CONFIRM ---")
    print("Product : " + product["product_name"])
#    print("Profile : {} | {}".format(profile["profile_name"], describe_target(profile)))
    print("Sugar: {} | Protein: {} | Sodium: {}".format(
        _fmt(n["sugar_g"], "g"), _fmt(n["protein_g"], "g"), _fmt(n["sodium_mg"], "mg")))
    print("Claim   : " + (product["marketing_claim"] or "None"))
    return read_yes_no("Analyse this product? (Y/N): ")


# ===========================================================================
# PERSON B - B3: display ONE analysis record
# ===========================================================================

def show_analysis(record):
    """RECORD VIEW: display a completed (new or saved) analysis.
    Uses record['profile_snapshot'] so old records show the OLD target."""
    snap = record["profile_snapshot"]
    info = GOAL_INFO[snap["primary_goal"]]
    ai = record["ai_analysis"]
    n = record["nutrition"]

    print("\n" + LINE)
    print(" NUTRILENZ ANALYSIS | " + record["product_name"])
    print(LINE)
    if record.get("analysed_at"):
        print("Analysed on  : " + record["analysed_at"])
    print("Profile used : {} | {}".format(snap["profile_name"], info["label"]))
#    print("Target used  : " + describe_target(snap))
    print("Nutrition    : Sugar {} | Protein {} | Sodium {} (per serving)".format(
        _fmt(n["sugar_g"], "g"), _fmt(n["protein_g"], "g"), _fmt(n["sodium_mg"], "mg")))
    print("Claim        : " + (record["marketing_claim"] or "None"))

    # Flags decided by logic_manager - we only display them
    print("\nFLAGS:")
    if record["flags"]:
        for flag in record["flags"]:
            print("  [{}] {}".format(flag, FLAG_DESCRIPTIONS.get(flag, "")))
    else:
        print("  No positive match issued; see the interpretation below.")

    # AI interpretation fields
    print("\nAI INTERPRETATION:")
    print("  Goal alignment : " + ai["goal_alignment"])
    print("  Claim status   : " + ai["claim_status"])
    print("  Confidence     : " + ai["confidence"])
    relevant = ", ".join(ai["relevant_ingredients"]) or "None identified"
    print("  Relevant ingredients: " + relevant)
    print("  Evidence:")
    if ai["evidence"]:
        for item in ai["evidence"]:
            print(textwrap.fill(item, width=70, initial_indent="    - ",
                                subsequent_indent="      "))
    else:
        print("    - None supplied")
    print("  Explanation:")
    print(textwrap.fill(ai["explanation"], width=70, initial_indent="    ",
                        subsequent_indent="    "))
    print(LINE)