from ..domain.recommendation_options import RecommendationOptions
from ..domain.scored_product import ScoredProduct
from ..domain.profile import Profile
from .ai_request import AIRequest
from .recommendation_advice import RecommendationAdvice
from .ai_task import AITask
from .prompt_text import SHARED_RULES, DIETARY_RULES, SINGAPORE_PRODUCT_RULES, PRODUCT_SUGGESTION_SCHEMA


class RecommendationTask(AITask):
    """Explain a shortlist that Logic has already ranked from saved products.
    The AI may only pick from the products it is given, so it cannot invent any."""

    RULES = """You help a user in Singapore choose packaged foods.

Rules:
""" + SHARED_RULES + DIETARY_RULES + """
- picks may ONLY use products from the candidates list, by their product_id.
- Candidates are already filtered and ranked by Python. They have no matched avoid-list
  ingredients or possible dietary concerns. Some have unknown ingredients: do not
  claim these passed dietary checks. Pick the ones that match the focus best.
- For each pick give one short reason (max 25 words) based on the supplied numbers.
- tips: 1 to 3 short general tips for the user's goals and the chosen focus options.
- If candidates is empty, return an empty picks list.
""" + SINGAPORE_PRODUCT_RULES + """
  Match ALL the chosen focus options and one of the chosen categories (unless "Any").
  Do not repeat any candidate.

Return exactly these keys:
{
  "picks": [{"product_id": number, "reason": "short text"}],
  "tips": [1 to 3 short tips],
  "suggested_products": """ + PRODUCT_SUGGESTION_SCHEMA + """
}"""

    def __init__(self, profile: Profile, options: RecommendationOptions,
                 candidates: list[ScoredProduct]):
        super().__init__()
        self._profile = profile
        self._options = options
        self._candidates = list(candidates)

    @property
    def name(self) -> str:
        return "recommendation"

    def build_request(self) -> AIRequest:
        candidates = []
        for scored in self._candidates:
            product = scored.product
            candidates.append({
                "product_id": product.product_id,
                "name": product.display_name(),
                "category": product.category,
                "per_serving": {n.key: v for n, v in product.nutrition.supplied().items()},
                "ingredients": product.ingredient_text,
                "app_score": scored.score,
                "dietary_results": self._dietary_facts(scored.dietary_report),
            })
        payload = {"goals": self._goal_phrase(self._profile),
                   "avoid_ingredients": list(self._profile.avoid_ingredients),
                   "dietary_checks": self._dietary_preferences(self._profile),
                   "focus": [focus.label for focus in self._options.focuses],
                   "categories": list(self._options.categories) or ["Any"],
                   "candidates": candidates}
        return AIRequest(self.RULES, self._as_data(payload))

    def parse(self, data: dict) -> RecommendationAdvice:
        check = self._checker
        check.exact_keys(data, ("picks", "tips", "suggested_products"))
        tips = check.string_list(data, "tips", allow_empty=False)[:3]
        products = check.product_suggestions(data, "suggested_products")
        candidate_names = {scored.product.name.casefold() for scored in self._candidates}
        if any(p.name.casefold() in candidate_names for p in products):
            raise ValueError("suggested_products must not repeat a candidate")
        if not isinstance(data["picks"], list):
            raise ValueError("picks must be a list")
        allowed = {scored.product.product_id for scored in self._candidates}
        reasons: dict[int, str] = {}
        for pick in data["picks"]:
            if not isinstance(pick, dict):
                raise ValueError("each pick must be an object")
            check.exact_keys(pick, ("product_id", "reason"))
            product_id = pick["product_id"]
            if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id not in allowed:
                raise ValueError("picks may only use product_id values from candidates")
            if product_id in reasons:
                raise ValueError("each product may only be picked once")
            reasons[product_id] = check.text(pick, "reason")
        if allowed and not reasons:
            raise ValueError("pick at least one candidate")
        self._check_dietary_wording([*tips, *reasons.values(), *(p.reason for p in products)])
        return RecommendationAdvice(reasons, tips, products)
