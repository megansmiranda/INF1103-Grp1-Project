import os
import secrets
from pathlib import Path

from .env_file_loader import EnvFileLoader


class AppConfig:
    """All settings in one place, read from environment variables."""

    def __init__(self, env: dict[str, str]):
        self._env = dict(env)

    @classmethod
    def from_environment(cls, env_file: Path | None = None) -> "AppConfig":
        root = Path(__file__).resolve().parent.parent
        EnvFileLoader(env_file or root / ".env").load()
        return cls(dict(os.environ))

    def _get(self, key: str, default: str = "") -> str:
        return self._env.get(key, default).strip()

    def _get_int(self, key: str, default: int) -> int:
        try:
            return int(self._get(key, str(default)))
        except ValueError:
            return default

    # --- AI ---
    @property
    def gemini_api_key(self) -> str:
        return self._get("GEMINI_API_KEY")

    @property
    def gemini_model(self) -> str:
        return self._get("GEMINI_MODEL", "gemini-3.5-flash-lite")

    @property
    def groq_api_key(self) -> str:
        return self._get("GROQ_API_KEY")

    @property
    def groq_model(self) -> str:
        return self._get("GROQ_MODEL", "openai/gpt-oss-20b")

    @property
    def groq_vision_model(self) -> str:
        return self._get("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

    @property
    def ai_timeout_seconds(self) -> int:
        return self._get_int("AI_TIMEOUT_SECONDS", 30)

    # --- Database ---
    @property
    def storage(self) -> str:
        """'mysql' (normal) or 'memory' (no database, data is lost on exit)."""
        return self._get("NUTRILENZ_STORAGE", "mysql").lower()

    @property
    def db_host(self) -> str:
        return self._get("DB_HOST", "localhost")

    @property
    def db_port(self) -> int:
        return self._get_int("DB_PORT", 3306)

    @property
    def db_user(self) -> str:
        return self._get("DB_USER", "nutrilenz")

    @property
    def db_password(self) -> str:
        return self._get("DB_PASSWORD")

    @property
    def db_name(self) -> str:
        return self._get("DB_NAME", "nutrilenz")

    @property
    def seed_demo_data(self) -> bool:
        return self._get("SEED_DEMO_DATA", "true").lower() in ("1", "true", "yes")

    # --- Web / jobs ---
    @property
    def secret_key(self) -> str:
        """Signs login cookies. A random one is used if not set (logins reset on restart)."""
        return self._get("FLASK_SECRET_KEY") or secrets.token_hex(32)

    @property
    def host(self) -> str:
        return self._get("HOST", "127.0.0.1")

    @property
    def port(self) -> int:
        return self._get_int("PORT", 5000)

    @property
    def worker_threads(self) -> int:
        return max(1, self._get_int("WORKER_THREADS", 3))

    @property
    def log_path(self) -> Path:
        return Path(self._get("LOG_FILE", "nutrilenz.log"))
