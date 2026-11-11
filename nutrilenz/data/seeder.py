import json
import logging
from datetime import datetime
from pathlib import Path

from ..domain.ai_analysis import AIAnalysis
from ..domain.analysis import Analysis
from ..domain.product import Product
from ..logic.logic_manager import LogicManager
from .data_manager import DataManager

logger = logging.getLogger("nutrilenz.data")


class DemoDataSeeder:
    """Fills an empty database with demo accounts, a product catalogue and saved analyses.
    The AI answers in the file came from real Gemini runs; flags and scores are
    worked out again by the Logic Manager so they always follow the current rules."""

    DEFAULT_FILE = Path(__file__).resolve().parent / "demo_data.json"

    def __init__(self, data: DataManager, logic: LogicManager, path: Path | None = None):
        self._data = data
        self._logic = logic
        self._path = path or self.DEFAULT_FILE

    def seed_if_empty(self) -> bool:
        """Returns True if demo data was added."""
        if not self._data.is_empty():
            return False
        try:
            content = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            logger.error("Demo data file could not be read: %r", error)
            return False

        products = {}
        for row in content["products"]:
            product = self._data.save_product(Product.from_dict(row))
            products[product.name] = product

        for account in content["users"]:
            user = self._data.register(account["username"], account["password"],
                                       account["goals"], account["avoid_ingredients"])
            for saved in account.get("analyses", []):
                product = products[saved["product_name"]]
                ai = AIAnalysis.from_dict(saved["ai_analysis"])
                evaluation = self._logic.evaluate(product, user.profile, ai)
                self._data.save_analysis(Analysis(
                    user_id=user.user_id, product=product,
                    profile_snapshot=user.profile.snapshot(), ai_analysis=ai,
                    flags=list(evaluation.flags), goal_results=list(evaluation.goal_results),
                    score=evaluation.score, provider=saved["provider"],
                    analysed_at=datetime.fromisoformat(saved["analysed_at"])))
        logger.info("Demo data added")
        return True
