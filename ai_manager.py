"""
ai_manager.py - AI PROCESSING LAYER  (owner: AI Manager)

Every product analysis passes through here. This file:
  1. Builds a prompt from the product + profile          (build_ai_payload, build_prompt)
  2. Calls the AI API (Gemini first, Groq as backup)     (call_gemini, call_groq)
  3. Parses the reply as JSON                            (parse_ai_response)
  4. Validates the JSON schema and allowed values        (validate_ai_response)
  5. Retries on bad output, and fails gracefully         (analyse_product)

Rules we follow (from the school spec):
  - ZERO domain logic here: no target comparisons, no flags. Logic Manager does that.
  - No printing or keyboard input: problems are LOGGED and returned as an error envelope.
  - No classes: only functions.

Only the Python standard library is used (urllib), so nothing needs pip install.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

# Errors are written to the log file set up by main.py (never printed).
logger = logging.getLogger("nutrilenz.ai")

# ---------------------------------------------------------------------------
# The contract: the six fields the AI must return, and their allowed values
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = ("relevant_ingredients", "goal_alignment", "claim_status",
                   "evidence", "explanation", "confidence")
ALLOWED_GOAL_ALIGNMENT = ("ALIGNED", "MIXED", "POOR_ALIGNMENT", "INSUFFICIENT_INFORMATION")
ALLOWED_CLAIM_STATUS = ("CONSISTENT", "QUESTIONABLE", "INSUFFICIENT_INFORMATION", "NO_CLAIM")
ALLOWED_CONFIDENCE = ("HIGH", "MEDIUM", "LOW")

MAX_ATTEMPTS_PER_PROVIDER = 2   # 1 try + 1 retry, then move to the backup provider
TIMEOUT_SECONDS = 30            # never let the CLI hang forever

# Errors where retrying the SAME provider will not help (wrong key / wrong model)
NON_RETRYABLE_ERRORS = ("CONFIGURATION_ERROR", "AUTHENTICATION_ERROR")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


# ===========================================================================
# Configuration: read API keys from the .env file / environment variables
# ===========================================================================

def load_env_file(path=None):
    """Read KEY=VALUE lines from .env into os.environ.
    Values already set in the environment (e.g. by Docker --env-file) win.
    Keys are NEVER written in the code itself."""
    env_path = Path(path) if path else Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()   # safe at import: it only reads a file, it never prompts


def get_providers():
    """Return the list of AI providers that have an API key, in order of preference.
    Each provider is a small dictionary holding its name, key, model and call function."""
    providers = []
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        providers.append({
            "name": "gemini",
            "api_key": gemini_key,
            "model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            "call": call_gemini,
        })
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        providers.append({
            "name": "groq",
            "api_key": groq_key,
            "model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b"),
            "call": call_groq,
        })
    return providers
