from ..domain.nutrients import Nutrient
from .ai_request import AIRequest
from .label_image import LabelImage
from .label_reading import LabelReading
from .ai_task import AITask
from .prompt_text import SHARED_RULES


class LabelExtractionTask(AITask):
    """Read the nutrition panel and ingredients from a photo."""

    FIELDS = ("readable", "product_name", "brand", "category", "nutrition",
              "ingredient_text", "marketing_claim", "notes")

    RULES = """You read packaged-food labels from photos for a nutrition app.

Rules:
""" + SHARED_RULES + """
- Copy values exactly as printed. Do not guess or invent anything.
- nutrition values must be PER SERVING. If only per-100 g values are printed and the
  serving size is printed, convert them; otherwise use null and say so in notes.
- Use these units: grams for sugar/protein/fat/saturated fat/carbohydrate/fibre,
  milligrams for sodium, kcal for calories (convert kJ to kcal by dividing by 4.184).
- Use null for anything that is not visible. null means unknown, not zero.
- marketing_claim: a front-of-pack style claim if one is visible (e.g. "Low Sugar"), else null.
- If the photo is not a food label or is unreadable, set readable to false.

Return exactly these keys:
{
  "readable": true | false,
  "product_name": text or null,
  "brand": text or null,
  "category": text or null,
  "nutrition": {""" + ", ".join('"' + k + '": number or null' for k in Nutrient.keys()) + """},
  "ingredient_text": text or null,
  "marketing_claim": text or null,
  "notes": short text about anything unclear, or null
}"""

    def __init__(self, image: LabelImage):
        super().__init__()
        self._image = image

    @property
    def name(self) -> str:
        return "label_extraction"

    @property
    def needs_image(self) -> bool:
        return True

    def build_request(self) -> AIRequest:
        content = self._as_data({"task": "Read the attached label photo.",
                                 "filename": self._image.filename})
        return AIRequest(self.RULES, content, self._image)

    def parse(self, data: dict) -> LabelReading:
        check = self._checker
        check.exact_keys(data, self.FIELDS)
        readable = check.boolean(data, "readable")
        nutrition = data["nutrition"]
        if not isinstance(nutrition, dict):
            raise ValueError("nutrition must be an object")
        check.exact_keys(nutrition, tuple(Nutrient.keys()))
        fields = {
            "product_name": check.text(data, "product_name", allow_null=True),
            "brand": check.text(data, "brand", allow_null=True),
            "category": check.text(data, "category", allow_null=True),
            "nutrition": {key: check.amount_or_null(nutrition[key], key) for key in Nutrient.keys()},
            "ingredient_text": check.text(data, "ingredient_text", allow_null=True),
            "marketing_claim": check.text(data, "marketing_claim", allow_null=True),
        }
        return LabelReading(readable, fields, check.text(data, "notes", allow_null=True))
