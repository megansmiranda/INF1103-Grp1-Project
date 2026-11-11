from ..domain.dietary_report import DietaryReport


class DietaryPresenter:
    """Plain text fragments; Jinja escapes both ordinary and highlighted text."""

    @staticmethod
    def ingredient_segments(report: DietaryReport) -> list[tuple[str, bool]]:
        text = report.ingredient_text
        spans = sorted({span for result in report.results for span in result.matched_spans
                        if 0 <= span[0] < span[1] <= len(text)})
        merged = []
        for start, end in spans:
            if merged and start < merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        parts, position = [], 0
        for start, end in merged:
            parts.extend(((text[position:start], False), (text[start:end], True)))
            position = end
        parts.append((text[position:], False))
        return parts
