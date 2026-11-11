import math
import re

from ..ai.label_image import LabelImage
from ..domain.goal_factory import GoalFactory
from ..domain.dietary_check_factory import DietaryCheckFactory
from ..domain.nutrients import Nutrient
from ..domain.nutrition_facts import NutritionFacts
from ..domain.product import Product
from ..domain.recommendation_focus import RecommendationFocus
from ..domain.recommendation_options import RecommendationOptions
from ..domain.profile import Profile
from ..errors.validation_error import ValidationError


class FormParser:
    """Reads and validates submitted forms. Collects every problem at once so the
    user can fix them all in one go. Raises ValidationError with one message per field."""

    USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")
    MIN_PASSWORD = 8
    MAX_AMOUNT = 10_000.0                  # hard limit per serving for any nutrient
    MAX_TEXT = {"product_name": 120, "brand": 80, "category": 60,
                "marketing_claim": 255, "ingredient_text": 2000}
    MAX_PHOTOS = 5

    # --- accounts ---
    def credentials(self, form, new_account: bool) -> tuple[str, str]:
        errors = {}
        username = form.get("username", "").strip()
        password = form.get("password", "")
        if not self.USERNAME_PATTERN.match(username):
            errors["username"] = "Username must be 3-40 letters, numbers, dots, dashes or underscores."
        if new_account:
            if len(password) < self.MIN_PASSWORD:
                errors["password"] = f"Password must be at least {self.MIN_PASSWORD} characters."
            elif password != form.get("confirm_password", ""):
                errors["confirm_password"] = "Passwords do not match."
        elif not password:
            errors["password"] = "Enter your password."
        if errors:
            raise ValidationError(errors)
        return username, password

    def goals(self, form) -> tuple[list[dict], list[str]]:
        """Ticked presets with their targets, plus the avoid list."""
        errors = {}
        specs = []
        for preset, (nutrient, direction) in GoalFactory.PRESETS.items():
            if form.get("goal_" + preset) != "on":
                continue
            target = self._number(form.get("target_" + preset, ""))
            if target is None or target <= 0 or target > self.MAX_AMOUNT:
                errors["target_" + preset] = (nutrient.label + " target must be a number above 0 "
                                              f"and at most {self.MAX_AMOUNT:g}.")
                continue
            specs.append({"nutrient": nutrient.key, "direction": direction, "target": target})
        if not specs and not errors:
            errors["goals"] = "Choose at least one goal."
        elif len(specs) > Profile.MAX_GOALS:
            errors["goals"] = f"Choose at most {Profile.MAX_GOALS} goals."
        avoid = [word.strip() for word in form.get("avoid_ingredients", "").split(",")]
        avoid = [word for word in avoid if word]
        if any(len(word) > 60 for word in avoid) or len(avoid) > 20:
            errors["avoid_ingredients"] = "Up to 20 ingredients, each under 60 characters."
        if errors:
            raise ValidationError(errors)
        return specs, avoid

    def dietary_checks(self, form) -> list[str]:
        keys = form.getlist("dietary_checks")
        try:
            diets = form.getlist("diet")
            if any(key not in (*DietaryCheckFactory.DIETS, "none") for key in diets):
                raise ValueError("Choose a listed diet.")
            # Count submitted values, not just unique keys: reject tampered radios,
            # including No diet combined with another diet or repeated diet fields.
            if len(diets) + sum(key in DietaryCheckFactory.DIETS for key in keys) > 1:
                raise ValueError("Choose only one diet.")
            keys = [key for key in diets if key != "none"] + keys
            return [c.key for c in DietaryCheckFactory.from_keys(keys)]
        except ValueError as problem:
            raise ValidationError({"dietary_checks": str(problem)}) from problem

    # --- products ---
    def product(self, form, prefix: str = "") -> Product:
        errors = {}
        text = {}
        for field, limit in self.MAX_TEXT.items():
            value = form.get(prefix + field, "").strip()
            if len(value) > limit:
                errors[prefix + field] = f"Keep this under {limit} characters."
            text[field] = value or None
        if not text["product_name"]:
            errors[prefix + "product_name"] = "Product name is required."

        values = {}
        for nutrient in Nutrient:
            raw = form.get(prefix + "n_" + nutrient.key, "").strip()
            if raw == "":
                values[nutrient] = None          # blank = not on the label
                continue
            number = self._number(raw)
            if number is None or number < 0 or number > self.MAX_AMOUNT:
                errors[prefix + "n_" + nutrient.key] = (
                    f"{nutrient.label} must be a number from 0 to {self.MAX_AMOUNT:g}, or blank.")
            else:
                values[nutrient] = number
        if all(value is None for value in values.values()) and not any(
                key.startswith(prefix + "n_") for key in errors):
            errors[prefix + "nutrition"] = "Enter at least one nutrition value."
        if errors:
            raise ValidationError(errors)
        return Product(text["product_name"], NutritionFacts(values), text["ingredient_text"] or "",
                       text["brand"], text["category"], text["marketing_claim"])

    def photos(self, files) -> list[LabelImage]:
        uploads = [f for f in files if f and f.filename]
        if not uploads:
            raise ValidationError({"photos": "Choose at least one photo."})
        if len(uploads) > self.MAX_PHOTOS:
            raise ValidationError({"photos": f"Upload at most {self.MAX_PHOTOS} photos at a time."})
        images = []
        for upload in uploads:
            try:
                images.append(LabelImage(upload.read(), upload.mimetype, upload.filename))
            except ValueError as problem:
                raise ValidationError({"photos": upload.filename + ": " + str(problem)}) from problem
        return images

    def recommendation_options(self, form, categories: list[str]) -> RecommendationOptions:
        """Several focuses and categories can be ticked. No category ticked means any."""
        focus_names = form.getlist("focus")
        chosen_categories = form.getlist("category")
        errors = {}
        if not focus_names:
            errors["focus"] = "Pick at least one focus."
        elif any(name not in RecommendationFocus.__members__ for name in focus_names):
            errors["focus"] = "Pick from the listed options."
        if any(name not in categories for name in chosen_categories):
            errors["category"] = "Pick from the listed categories."
        if errors:
            raise ValidationError(errors)
        return RecommendationOptions([RecommendationFocus[name] for name in focus_names],
                                     chosen_categories)

    @staticmethod
    def _number(raw: str) -> float | None:
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None
