from ..domain.analysis import Analysis


class AnalysisOutcome:
    """A finished analysis and whether it was saved."""

    def __init__(self, analysis: Analysis, saved: bool, error_code: str | None = None):
        self._analysis = analysis
        self._saved = saved
        self._error_code = error_code

    @property
    def analysis(self) -> Analysis:
        return self._analysis

    @property
    def saved(self) -> bool:
        return self._saved

    @property
    def error_code(self) -> str | None:
        return self._error_code
