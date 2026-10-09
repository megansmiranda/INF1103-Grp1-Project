# --- Profiles (what io_manager.collect_profile() returns) -------------------
SAMPLE_PROFILES = {
    "jane": {
        "profile_name": "Jane",
        "primary_goal": "REDUCE_SUGAR",
        "target_value": 10.0,
        "target_unit": "g_per_serving",
        "avoid_ingredients": [],
    },
    "sam": {
        "profile_name": "Sam",
        "primary_goal": "HIGH_PROTEIN",
        "target_value": 15.0,
        "target_unit": "g_per_serving",
        "avoid_ingredients": ["peanuts"],
    },
    "ari": {
        "profile_name": "Ari",
        "primary_goal": "LOWER_SODIUM",
        "target_value": 400.0,
        "target_unit": "mg_per_serving",
        "avoid_ingredients": ["msg"],
    },
}

# --- Products (what io_manager.collect_product() returns) -------------------
SAMPLE_PRODUCTS = {
    # Sugar 14 g with a "Low Sugar" claim -> expect QUESTIONABLE claim
    "cereal": {
        "product_name": "Example Cereal",
        "brand": None,
        "category": "Cereal",
        "nutrition": {"sugar_g": 14.0, "protein_g": 6.0, "sodium_mg": 180.0},
        "ingredient_text": "Oats, apple juice concentrate, brown rice syrup, cocoa, maltodextrin",
        "marketing_claim": "Naturally sweetened - no refined sugar",
    },
    # Protein 20 g, claim fits -> expect ALIGNED / CONSISTENT for Sam
    "protein_bar": {
        "product_name": "PowerUp Protein Bar",
        "brand": "PowerUp",
        "category": "Snack bar",
        "nutrition": {"sugar_g": 3.0, "protein_g": 20.0, "sodium_mg": 150.0},
        "ingredient_text": "Whey protein isolate, milk protein, almonds, peanuts, "
                           "soluble corn fibre, cocoa butter, sucralose",
        "marketing_claim": "High Protein",
    },
    # No claim at all -> AI must answer NO_CLAIM
    "noodles": {
        "product_name": "Instant Chicken Noodles",
        "brand": None,
        "category": "Instant noodles",
        "nutrition": {"sugar_g": 2.0, "protein_g": 8.0, "sodium_mg": 1450.0},
        "ingredient_text": "Wheat flour, palm oil, salt, monosodium glutamate, "
                           "disodium inosinate, chicken extract powder",
        "marketing_claim": None,
    },
    # Sugar is missing (None) -> Logic should give MANUAL_REVIEW, never treat as 0
    "missing_sugar": {
        "product_name": "Mystery Granola",
        "brand": None,
        "category": None,
        "nutrition": {"sugar_g": None, "protein_g": 5.0, "sodium_mg": 90.0},
        "ingredient_text": "Oats, honey, golden syrup, raisins",
        "marketing_claim": "Low Sugar",
    },
}

# --- Hardcoded AI answers (what ai_analysis looks like AFTER validation) ---------
# Used by test_logic.py so Logic can be tested with NO internet / NO API key.
SAMPLE_AI_RESPONSES = {
    "questionable_high": {
        "relevant_ingredients": ["apple juice concentrate", "brown rice syrup"],
        "goal_alignment": "POOR_ALIGNMENT",
        "claim_status": "QUESTIONABLE",
        "evidence": ["The label lists brown rice syrup and apple juice concentrate."],
        "explanation": "These are added sugars, so the 'no refined sugar' claim may mislead.",
        "confidence": "HIGH",
    },
    "questionable_low": {
        "relevant_ingredients": ["brown rice syrup"],
        "goal_alignment": "MIXED",
        "claim_status": "QUESTIONABLE",
        "evidence": ["The label lists brown rice syrup."],
        "explanation": "The claim may not be fully supported, but information is limited.",
        "confidence": "LOW",
    },
    "aligned_no_claim": {
        "relevant_ingredients": ["whey protein isolate"],
        "goal_alignment": "ALIGNED",
        "claim_status": "NO_CLAIM",
        "evidence": ["Whey protein isolate is the first ingredient."],
        "explanation": "Protein sources lead the ingredient list, which suits a high-protein goal.",
        "confidence": "HIGH",
    },
    "aligned_consistent": {
        "relevant_ingredients": ["whey protein isolate", "milk protein"],
        "goal_alignment": "ALIGNED",
        "claim_status": "CONSISTENT",
        "evidence": ["Whey protein isolate and milk protein are listed first."],
        "explanation": "The High Protein claim is supported by the protein-rich ingredients.",
        "confidence": "HIGH",
    },
    "mixed_consistent": {
        "relevant_ingredients": ["salt"],
        "goal_alignment": "MIXED",
        "claim_status": "CONSISTENT",
        "evidence": ["Salt appears in the ingredients."],
        "explanation": "Some ingredients fit the goal and some do not.",
        "confidence": "HIGH",
    },
}

# --- Raw AI text examples (what the API sends back BEFORE parsing) ----------
# Used by test_ai_manager.py to test parse_ai_response / validate_ai_response offline.
RAW_VALID = """{"relevant_ingredients": ["brown rice syrup"], "goal_alignment": "POOR_ALIGNMENT",
"claim_status": "QUESTIONABLE", "evidence": ["Brown rice syrup is listed."],
"explanation": "Brown rice syrup is a sugar.", "confidence": "HIGH"}"""
RAW_FENCED = "```json\n" + RAW_VALID + "\n```"
RAW_NOT_JSON = "Sure! Here is my analysis: the cereal looks sugary."
RAW_LIST = "[1, 2, 3]"
