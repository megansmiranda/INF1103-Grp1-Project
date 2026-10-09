"""
demo_ai_manager.py - CLI DEMO of the AI Manager using the hardcoded sample data

Shows that ai_manager can run on its own (no io_manager / logic_manager needed):
pick a sample product + profile, it is sent to the REAL AI (Gemini, Groq as backup),
and the validated AI output is printed in a readable form.

Run:  python demo_ai_manager.py          (needs a .env with at least one API key)
"""

import ai_manager
from sample_data import SAMPLE_PRODUCTS, SAMPLE_PROFILES

# Use the shared display function once the I/O branch is merged
try:
    from io_manager import show_message
except ImportError:
    show_message = print

# Each demo pairs one sample product with the profile it is meant to test
DEMOS = [
    ("cereal", "jane", "Claim 'no refined sugar' but contains syrups -> expect QUESTIONABLE"),
    ("protein_bar", "sam", "High Protein claim with whey first -> expect CONSISTENT"),
    ("noodles", "ari", "No marketing claim -> AI must answer NO_CLAIM"),
    ("missing_sugar", "jane", "Sugar value missing -> AI still judges the ingredients"),
]


def show_input(product, profile):
    """Print what is being sent to the AI."""
    nutrition = product["nutrition"]
    show_message("\n" + "=" * 60)
    show_message(" INPUT")
    show_message("=" * 60)
    show_message(" Profile     : {} (goal: {})".format(profile["profile_name"], profile["primary_goal"]))
    show_message(" Product     : " + product["product_name"])
    show_message(" Nutrition   : sugar {} g, protein {} g, sodium {} mg".format(
        nutrition["sugar_g"], nutrition["protein_g"], nutrition["sodium_mg"]))
    show_message(" Ingredients : " + product["ingredient_text"])
    show_message(" Claim       : " + str(product["marketing_claim"] or "(none)"))


def show_result(result):
    """Print the AI Manager's result envelope in a readable form."""
    show_message("\n" + "=" * 60)
    show_message(" AI OUTPUT")
    show_message("=" * 60)
    if not result["ok"]:
        show_message(" FAILED - error code: " + str(result["error_code"]))
        return
    analysis = result["ai_analysis"]
    show_message(" Provider used        : " + result["provider"])
    show_message(" Goal alignment       : " + analysis["goal_alignment"])
    show_message(" Claim status         : " + analysis["claim_status"])
    show_message(" Confidence           : " + analysis["confidence"])
    show_message(" Relevant ingredients : " + ", ".join(analysis["relevant_ingredients"]))
    show_message(" Evidence:")
    for line in analysis["evidence"]:
        show_message("   - " + line)
    show_message(" Explanation:")
    show_message("   " + analysis["explanation"])


def run_demo(product_key, profile_key):
    product, profile = SAMPLE_PRODUCTS[product_key], SAMPLE_PROFILES[profile_key]
    show_input(product, profile)
    show_message("\nAnalysing with AI, please wait...")
    show_result(ai_manager.analyse_product(product, profile))


def main():
    while True:
        show_message("\n=== NutriLenz AI Manager demo (sample data) ===")
        for number, (product_key, profile_key, note) in enumerate(DEMOS, start=1):
            show_message(" {}. {} for {}".format(number, SAMPLE_PRODUCTS[product_key]["product_name"],
                                                 SAMPLE_PROFILES[profile_key]["profile_name"]))
            show_message("    " + note)
        show_message(" A. Run all")
        show_message(" 0. Exit")
        choice = input("Choose: ").strip().upper()

        if choice == "0":
            break
        if choice == "A":
            for product_key, profile_key, _ in DEMOS:
                run_demo(product_key, profile_key)
        elif choice.isdigit() and 1 <= int(choice) <= len(DEMOS):
            product_key, profile_key, _ = DEMOS[int(choice) - 1]
            run_demo(product_key, profile_key)
        else:
            show_message("Invalid choice.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        show_message("\nGoodbye.")
