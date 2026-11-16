from ..domain.scored_product import ScoredProduct
from ..domain.profile import Profile
from .ai_request import AIRequest
from .ai_task import AITask
from .comparison_advice import ComparisonAdvice
from .prompt_text import SHARED_RULES, DIETARY_RULES, GOAL_RULES


class ComparisonTask(AITask):
    """Explain a side-by-side ranking that Logic has already decided.
    The AI cannot change the order; it only says why item 1 fits best."""

    MAX_WORDS = 25

    RULES = """You help a shopper in Singapore choose between similar packaged foods on a shelf.

Rules:
""" + SHARED_RULES + DIETARY_RULES + GOAL_RULES + """- The products are already ranked by Python. Item 1 is the best fit for the user's goals.
  Never change this order or suggest a different winner.
- A product with has_concern true (a possible dietary concern or an avoid-list match) always
  ranks below every product without one, even if its app_score is higher. If item 1 has a
  lower app_score than another item, say item 1 ranks first because the others have a
  possible dietary concern or an avoided ingredient. Never call those others the best fit.
- Base everything on the supplied numbers, ingredients and dietary_results only.
- summary: max 40 words. Say why item 1 fits the goals best, naming it.
  If several items have the same app_score, say they are close.
- notes: exactly one entry per item. strength and drawback are max 25 words each.
  If an item has no clear drawback, say what the shopper should still check on the label.
- Write for a shopper in plain words. Never show codes such as POSSIBLE_CONCERN or field names.

Return exactly these keys:
{
  "summary": "short text",
  "notes": [{"item": number, "strength": "short text", "drawback": "short text"}]
}"""

    def __init__(self, profile: Profile, ranked: list[ScoredProduct]):
        super().__init__()
        if len(ranked) < 2:
            raise ValueError("A comparison needs at least two products")
        self._profile = profile
        self._ranked = list(ranked)

    @property
    def name(self) -> str:
        return "comparison"

    def build_request(self) -> AIRequest:
        items = []
        for rank, scored in enumerate(self._ranked, start=1):
            product = scored.product
            avoid_matches = product.ingredients_found(list(self._profile.avoid_ingredients))
            items.append({
                "item": rank,
                "name": product.display_name(),
                "category": product.category,
                "per_serving": {n.key: v for n, v in product.nutrition.supplied().items()},
                "ingredients": product.ingredient_text,
                "marketing_claim": product.marketing_claim,
                "app_score": scored.score,
                "has_concern": bool(scored.dietary_report.has_concern or avoid_matches),
                "goal_results": self._goal_facts(self._profile, product),
                "avoid_list_matches": avoid_matches,
                "dietary_results": self._dietary_facts(scored.dietary_report),
            })
        payload = {"goals": self._goal_phrase(self._profile),
                   "avoid_ingredients": list(self._profile.avoid_ingredients),
                   "dietary_checks": self._dietary_preferences(self._profile),
                   "products": items}
        return AIRequest(self.RULES, self._as_data(payload))

    def parse(self, data: dict) -> ComparisonAdvice:
        check = self._checker
        check.exact_keys(data, ("summary", "notes"))
        summary = self._short(check.text(data, "summary"), "summary", 40)
        winner = self._ranked[0].product.name
        if winner.casefold() not in summary.casefold():
            raise ValueError(f"summary must name item 1 ({winner}) as the best fit")
        if not isinstance(data["notes"], list):
            raise ValueError("notes must be a list")
        strengths: dict[int, str] = {}
        drawbacks: dict[int, str] = {}
        for note in data["notes"]:
            if not isinstance(note, dict):
                raise ValueError("each note must be an object")
            check.exact_keys(note, ("item", "strength", "drawback"))
            item = note["item"]
            if isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= len(self._ranked):
                raise ValueError(f"item must be a number from 1 to {len(self._ranked)}")
            if item in strengths:
                raise ValueError("each item may only have one note")
            strengths[item] = self._short(check.text(note, "strength"), "strength", self.MAX_WORDS)
            drawbacks[item] = self._short(check.text(note, "drawback"), "drawback", self.MAX_WORDS)
        if len(strengths) != len(self._ranked):
            raise ValueError("notes must cover every item exactly once")
        self._check_dietary_wording([summary, *strengths.values(), *drawbacks.values()])
        return ComparisonAdvice(summary, strengths, drawbacks)

    @staticmethod
    def _short(text: str, field: str, max_words: int) -> str:
        if len(text.split()) > max_words + 5:          # small allowance before rejecting
            raise ValueError(f"{field} must be at most {max_words} words")
        return text
