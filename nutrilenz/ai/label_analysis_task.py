from ..domain.ai_analysis import AIAnalysis
from ..domain.dietary_report import DietaryReport
from ..domain.product import Product
from ..domain.profile import Profile
from .ai_request import AIRequest
from .ai_task import AITask
from .prompt_text import SHARED_RULES, DIETARY_RULES, SINGAPORE_PRODUCT_RULES, PRODUCT_SUGGESTION_SCHEMA


class LabelAnalysisTask(AITask):
    """Interpret one product label for the user's goals. Every analysis record uses this."""

    GOAL_ALIGNMENT = ("ALIGNED", "MIXED", "POOR_ALIGNMENT", "INSUFFICIENT_INFORMATION")
    CLAIM_STATUS = ("CONSISTENT", "QUESTIONABLE", "INSUFFICIENT_INFORMATION", "NO_CLAIM")
    CONFIDENCE = ("HIGH", "MEDIUM", "LOW")

    RULES = """You are a food-label interpreter for a nutrition app used in Singapore.
You interpret one packaged-food label for a user who may have SEVERAL goals.

Rules:
""" + SHARED_RULES + DIETARY_RULES + """
- Use ONLY the label data supplied. Do not invent ingredients or amounts.
- A null nutrition value means "not on the label" (it is NOT zero). Nutrients that are
  null are unknown.
- Explain unfamiliar ingredient names (e.g. brown rice syrup, maltodextrin, sodium
  caseinate, monosodium glutamate) and why they matter for the goals.
- If any avoid_ingredients (or obvious synonyms) appear, list them in
  relevant_ingredients and mention them in the explanation.
- goal_alignment covers ALL goals together: ALIGNED only if the label supports every goal,
  MIXED if it supports some but not others, POOR_ALIGNMENT if it works against them,
  INSUFFICIENT_INFORMATION if the label lacks what is needed to judge.
- If marketing_claim is null, claim_status MUST be "NO_CLAIM".
- If a claim is given, judge whether the label supports the impression it creates:
  CONSISTENT, QUESTIONABLE, or INSUFFICIENT_INFORMATION. This is not a legal ruling.
  If a claim has several parts, QUESTIONABLE if any part is contradicted; otherwise
  INSUFFICIENT_INFORMATION if any part cannot be checked.
- Whenever you answer INSUFFICIENT_INFORMATION, the explanation MUST name the missing information.
- Do NOT compare against personal target numbers and do NOT output flags or verdicts.
- suggestions: 1 to 3 short, practical tips for this user's goals, such as what kind of
  product to choose instead or what to check on the label.
""" + SINGAPORE_PRODUCT_RULES + """
- Use confidence "LOW" when the label gives you little to go on.

Return exactly these 8 keys:
{
  "relevant_ingredients": [ingredient names from the label, or []],
  "goal_alignment": "ALIGNED" | "MIXED" | "POOR_ALIGNMENT" | "INSUFFICIENT_INFORMATION",
  "claim_status": "CONSISTENT" | "QUESTIONABLE" | "INSUFFICIENT_INFORMATION" | "NO_CLAIM",
  "evidence": [at least one short string quoting the supplied label data],
  "explanation": "2-4 plain-English sentences written for this user's goals",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "suggestions": [1 to 3 short tips],
  "suggested_products": """ + PRODUCT_SUGGESTION_SCHEMA + """
}"""

    def __init__(self, product: Product, profile: Profile, dietary_report: DietaryReport | None = None):
        super().__init__()
        self._product = product
        self._profile = profile
        self._dietary_report = dietary_report or DietaryReport()

    @property
    def name(self) -> str:
        return "label_analysis"

    def build_request(self) -> AIRequest:
        product = self._product.to_dict()
        product.pop("product_id")
        payload = {"goals": self._goal_phrase(self._profile),
                   "avoid_ingredients": list(self._profile.avoid_ingredients),
                   "dietary_checks": self._dietary_preferences(self._profile),
                   "dietary_results": self._dietary_facts(self._dietary_report),
                   "product": product}
        return AIRequest(self.RULES, self._as_data(payload))

    def parse(self, data: dict) -> AIAnalysis:
        check = self._checker
        check.exact_keys(data, AIAnalysis.FIELDS)
        ingredients = check.string_list(data, "relevant_ingredients")
        evidence = check.string_list(data, "evidence", allow_empty=False)
        alignment = check.choice(data, "goal_alignment", self.GOAL_ALIGNMENT)
        claim = check.choice(data, "claim_status", self.CLAIM_STATUS)
        confidence = check.choice(data, "confidence", self.CONFIDENCE)
        explanation = check.text(data, "explanation")
        suggestions = check.string_list(data, "suggestions", allow_empty=False)
        if len(suggestions) > 3:
            raise ValueError("suggestions must have at most 3 tips")
        products = check.product_suggestions(data, "suggested_products")
        self._check_dietary_wording([explanation, *suggestions, *(p.reason for p in products)])
        if any(p.name.casefold() == self._product.name.casefold() for p in products):
            raise ValueError("suggested_products must not include the analysed product")
        # NO_CLAIM if and only if no claim was supplied
        if not self._product.has_claim and claim != "NO_CLAIM":
            raise ValueError("No claim was supplied, so claim_status must be NO_CLAIM")
        if self._product.has_claim and claim == "NO_CLAIM":
            raise ValueError("A claim was supplied, so claim_status cannot be NO_CLAIM")
        return AIAnalysis(ingredients, alignment, claim, evidence, explanation, confidence,
                          suggestions, products)
