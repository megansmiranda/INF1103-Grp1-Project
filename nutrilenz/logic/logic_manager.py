from ..domain.ai_analysis import AIAnalysis
from ..domain.flag import Flag
from ..domain.goal_result import GoalResult
from ..domain.dietary_report import DietaryReport
from ..domain.nutrients import Nutrient
from ..domain.amount import Amount
from ..domain.product import Product
from ..domain.recommendation_options import RecommendationOptions
from ..domain.scored_product import ScoredProduct
from ..domain.profile import Profile
from .claim_review_rule import ClaimReviewRule
from .evaluation_context import EvaluationContext
from .goal_mismatch_rule import GoalMismatchRule
from .good_match_rule import GoodMatchRule
from .manual_review_rule import ManualReviewRule
from .dietary_review_rule import DietaryReviewRule
from .rule import Rule
from .dietary_checker import DietaryChecker
from .evaluation import Evaluation


class LogicManager:
    """Applies business rules to AI-checked products: flags, a 0-100 score and ranking.
    It never calls the AI or the database."""

    # Values above these (per serving) get a "check the label" warning before the AI call.
    DEFAULT_WARNING_LIMITS = {
        Nutrient.SUGAR: 100.0, Nutrient.PROTEIN: 100.0, Nutrient.SODIUM: 5000.0,
        Nutrient.CALORIES: 2000.0, Nutrient.FAT: 100.0, Nutrient.SATURATED_FAT: 50.0,
        Nutrient.CARBOHYDRATE: 200.0, Nutrient.FIBRE: 50.0,
    }
    AVOIDED_INGREDIENT_PENALTY = 25.0
    MISSING_GOAL_CLOSENESS = 0.5          # unknown is neither good nor bad

    def __init__(self, rules: list[Rule] | None = None,
                 warning_limits: dict[Nutrient, float] | None = None):
        # The default rule list is created here and owned by the manager
        self._rules = list(rules) if rules is not None else [
            GoalMismatchRule(), ClaimReviewRule(), ManualReviewRule(),
            DietaryReviewRule(), GoodMatchRule()]
        self._dietary = DietaryChecker()
        limits = self.DEFAULT_WARNING_LIMITS if warning_limits is None else warning_limits
        for nutrient, limit in limits.items():
            if not Amount.is_number(limit) or limit <= 0:
                raise ValueError(nutrient.label + " warning limit must be a positive number")
        self._warning_limits = dict(limits)

    def evaluate_goals(self, product: Product, profile: Profile) -> list[GoalResult]:
        return [GoalResult.for_goal(goal, product) for goal in profile.goals]

    def check_dietary(self, product: Product, profile: Profile) -> DietaryReport:
        return self._dietary.evaluate(product.ingredient_text, profile.dietary_checks)

    def evaluate(self, product: Product, profile: Profile, ai: AIAnalysis,
                 dietary_report: DietaryReport | None = None) -> Evaluation:
        goal_results = self.evaluate_goals(product, profile)
        report = dietary_report if dietary_report is not None else self.check_dietary(product, profile)
        score = self.score(product, profile)
        context = EvaluationContext(product, ai, goal_results, report)
        flags: list[Flag] = []
        for rule in self._rules:
            if rule.applies(context, list(flags)):
                flags.append(rule.flag)
        return Evaluation(flags, goal_results, score, report)

    def score(self, product: Product, profile: Profile, ai: AIAnalysis | None = None) -> float:
        """0-100 from nutrition goals and the existing avoid penalty only.

        The optional AI argument is retained for callers; explanations do not affect scores.
        """
        closeness = []
        for goal in profile.goals:
            value = product.nutrition.get(goal.nutrient)
            closeness.append(self.MISSING_GOAL_CLOSENESS if value is None else goal.closeness(value))
        score = 100.0 * sum(closeness) / len(closeness)
        score -= self.AVOIDED_INGREDIENT_PENALTY * len(
            product.ingredients_found(list(profile.avoid_ingredients)))
        return round(min(100.0, max(0.0, score)), 1)

    def check_unusual_numbers(self, product: Product) -> list[str]:
        """Warnings for values that look like a typo (e.g. mg typed as g). Not flags."""
        warnings = []
        for nutrient, value in product.nutrition.supplied().items():
            limit = self._warning_limits.get(nutrient)
            if limit is not None and value > limit:
                warnings.append(
                    f"{nutrient.label} ({value:g} {nutrient.unit}) is above {limit:g} "
                    f"{nutrient.unit} for one serving. Check the unit and that it is per "
                    "serving, not per 100 g.")
        return warnings

    def rank(self, products: list[Product], profile: Profile, options: RecommendationOptions,
             limit: int = 5) -> list[ScoredProduct]:
        return self.recommendation_candidates(products, profile, options, limit)[0]

    def recommendation_candidates(self, products: list[Product], profile: Profile,
                                  options: RecommendationOptions, limit: int = 5
                                  ) -> tuple[list[ScoredProduct], list[ScoredProduct]]:
        """Filter dietary concerns before ranking, returning picks and explained exclusions.

        Unknown ingredients stay eligible. Category, avoid-list and nutrient-focus
        filters still apply. No template or AI decides catalogue eligibility.
        """
        focuses = options.nutrient_focuses()
        scored, excluded = [], []
        for product in products:
            if not options.matches_category(product):
                continue
            if any(product.nutrition.get(focus.nutrient) is None for focus in focuses):
                continue                    # can't rank by a nutrient that is not on the label
            report = self.check_dietary(product, profile)
            item = ScoredProduct(product, self.score(product, profile),
                                 self.evaluate_goals(product, profile), report)
            if report.has_concern:
                excluded.append(item)
                continue
            if product.ingredients_found(list(profile.avoid_ingredients)):
                continue
            scored.append(item)
        ratings = {id(item): self._focus_rating(item, scored, options) for item in scored}
        scored.sort(key=lambda item: (ratings[id(item)], item.score), reverse=True)
        return scored[:limit], excluded

    @staticmethod
    def _focus_rating(item: ScoredProduct, everyone: list[ScoredProduct],
                      options: RecommendationOptions) -> float:
        """Average of one 0-1 rating per chosen focus (1 = best among the candidates)."""
        parts = []
        for focus in options.nutrient_focuses():
            values = [other.product.nutrition.get(focus.nutrient) for other in everyone]
            low, high = min(values), max(values)
            value = item.product.nutrition.get(focus.nutrient)
            if high == low:
                parts.append(1.0)
            elif focus.order == "LOW":
                parts.append((high - value) / (high - low))
            else:
                parts.append((value - low) / (high - low))
        if options.includes_best_match() or not parts:
            parts.append(item.score / 100.0)
        return sum(parts) / len(parts)
