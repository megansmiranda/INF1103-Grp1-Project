import logging
import os
from pathlib import Path

logger = logging.getLogger("nutrilenz.config")


class EnvFileLoader:
    """Reads KEY=VALUE lines from a .env file into the environment.
    Values already set (e.g. by Docker) win. Keys are never written in code."""

    def __init__(self, path: Path):
        self._path = path

    def load(self) -> None:
        if not self._path.exists():
            return
        try:
            # utf-8-sig strips the hidden BOM some Windows editors add
            text = self._path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as error:
            logger.error("Could not read %s: %s", self._path.name, type(error).__name__)
            return
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
