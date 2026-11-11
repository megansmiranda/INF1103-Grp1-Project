from datetime import datetime
import logging

from ..domain.ai_analysis import AIAnalysis
from ..domain.analysis import Analysis
from ..domain.flag import Flag
from ..domain.goal_result import GoalResult
from ..domain.dietary_check_factory import DietaryCheckFactory
from ..domain.dietary_report import DietaryReport
from ..domain.product import Product
from ..domain.user import User

logger = logging.getLogger("nutrilenz.data")


class RecordMapper:
    """Converts domain objects to plain dicts for storage and back again.
    Both stores use it, so they save and load records the same way."""

    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def user_to_row(self, user: User) -> dict:
        return {"user_id": user.user_id, "username": user.username,
                "password_hash": user.password_hash_for_storage(),
                "goals": [goal.to_dict() for goal in user.profile.goals],
                "avoid_ingredients": list(user.profile.avoid_ingredients),
                "dietary_checks": [check.key for check in user.profile.dietary_checks]}

    def user_from_row(self, row: dict) -> User:
        saved = row.get("dietary_checks") or []
        checks = DietaryCheckFactory.normalise_saved_keys(saved)
        if checks != saved:
            logger.warning("User %s has multiple saved diets; loaded the strictest diet", row["user_id"])
        return User(row["username"], row["password_hash"], row["goals"],
                    row["avoid_ingredients"], row["user_id"], checks)

    def product_to_row(self, product: Product) -> dict:
        return product.to_dict()

    def product_from_row(self, row: dict) -> Product:
        return Product.from_dict(row)

    def analysis_to_row(self, analysis: Analysis) -> dict:
        if analysis.product.product_id is None:
            raise ValueError("Save the product before the analysis")
        return {
            "analysis_id": analysis.analysis_id,
            "user_id": analysis.user_id,
            "product_id": analysis.product.product_id,
            "profile_snapshot": analysis.profile_snapshot,
            "ai_analysis": analysis.ai_analysis.to_dict(),
            "goal_results": [result.to_dict() for result in analysis.goal_results],
            "dietary_results": analysis.dietary_report.to_dict(),
            "flags": analysis.flag_names(),
            "score": analysis.score,
            "provider": analysis.provider,
            "analysed_at": analysis.analysed_at.strftime(self.TIME_FORMAT),
        }

    def analysis_from_row(self, row: dict, product: Product) -> Analysis:
        report = DietaryReport.from_dict(row.get("dietary_results"), product.ingredient_text)
        flags = [Flag(name) for name in row["flags"]]
        # Earlier snapshots can contain concerns without their review flag. Repair
        # that inconsistency using saved statuses only, never today's profile/rules.
        if report.has_concern:
            flags = [flag for flag in flags if flag is not Flag.GOOD_MATCH]
            if Flag.DIETARY_REVIEW not in flags:
                flags.append(Flag.DIETARY_REVIEW)
        analysed_at = row["analysed_at"]
        if isinstance(analysed_at, str):
            analysed_at = datetime.strptime(analysed_at, self.TIME_FORMAT)
        return Analysis(user_id=row["user_id"], product=product,
                        profile_snapshot=row["profile_snapshot"],
                        ai_analysis=AIAnalysis.from_dict(row["ai_analysis"]),
                        flags=flags,
                        goal_results=[GoalResult.from_dict(r) for r in row["goal_results"]],
                        score=float(row["score"]), provider=row["provider"],
                        analysed_at=analysed_at, analysis_id=row["analysis_id"],
                        dietary_report=report)
