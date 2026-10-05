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
