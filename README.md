# NutriLenz — AI Food Label Interpreter (CLI)

INF1103 LAB-P12 Group 1 · Repository: https://github.com/megansmiranda/INF1103-Grp1-Project

NutriLenz helps university students and young adults in Singapore understand packaged
food labels. You enter a product's nutrition values, ingredient list and marketing claim.
The AI explains unfamiliar ingredients and checks whether the claim matches the label.
Then fixed business rules tell you whether the product fits your goal:
**Reduce Sugar**, **High Protein** or **Lower Sodium**.

---

## 1. How it works (4-layer architecture)

```
 User ──► io_manager ──► ai_manager ──► logic_manager ──► data_manager
          (input)        (AI layer)     (business rules)   (JSON storage)
             ▲                                                  │
             └──────────── io_manager shows the result ◄────────┘
                       main.py calls each step in order
```

| File | Layer | What it does |
|---|---|---|
| `io_manager.py` | Input/Output | Menus, validated input (re-prompts on bad data), shows records and lists. **The only file with `print()`/`input()`.** |
| `ai_manager.py` | AI processing | Builds the prompt, calls **Gemini** (backup: **Groq**), parses JSON, validates the schema, retries once, logs failures. No business rules. |
| `logic_manager.py` | Logic | Compares the nutrient with the user's target and decides the final flags. |
| `data_manager.py` | Data | Saves/loads `profiles.json` and `analyses.json`, filters history, never overwrites damaged files. |
| `main.py` | Entry point | Connects the four managers. No rules, printing or file code of its own. |
| `sample_data.py` | Test data | Hardcoded profiles, products and AI responses, so each manager can be tested on its own. |
| `test_logic.py` | Tests | **Required** API-free logic tests (hardcoded AI responses). |
| `test_ai_manager.py` | Tests | Offline tests for parsing/validation/retry, plus a `live` mode that calls the real API. |
| `test_data.py` | Tests | Save/load/snapshot/corrupt-file tests in a temporary folder. |

### One analysis, step by step
1. **I/O** collects the product and asks for confirmation (`collect_product`).
2. **AI** receives the product and goal and returns 6 validated fields (`analyse_product`).
3. **Logic** turns those fields and the numbers into flags (`evaluate_product`).
4. **Data** builds a record with a *snapshot* of the profile and saves it (`build_analysis`, `save_analysis`).
5. **I/O** displays the result and whether it was saved (`show_analysis`).

Viewing history only **reads** saved records. It never calls the AI again.

---

## 2. Data formats (the shared contract)

**Profile** (from `io_manager.collect_profile()`)
```python
{"profile_name": "Jane", "primary_goal": "REDUCE_SUGAR",      # or HIGH_PROTEIN / LOWER_SODIUM
 "target_value": 10.0, "target_unit": "g_per_serving",        # mg_per_serving for sodium
 "avoid_ingredients": ["peanuts"]}
```

**Product** (from `io_manager.collect_product()`). A missing value is `None`, which is **not** zero.
```python
{"product_name": "Example Cereal", "brand": None, "category": "Cereal",
 "nutrition": {"sugar_g": 14.0, "protein_g": 6.0, "sodium_mg": 180.0},
 "ingredient_text": "Oats, apple juice concentrate, brown rice syrup",
 "marketing_claim": "Low Sugar"}                               # None if no claim
```

**AI result** (from `ai_manager.analyse_product()`)
```python
{"ok": True, "provider": "gemini", "error_code": None,
 "ai_analysis": {
    "relevant_ingredients": ["brown rice syrup"],
    "goal_alignment": "POOR_ALIGNMENT",   # ALIGNED | MIXED | POOR_ALIGNMENT | INSUFFICIENT_INFORMATION
    "claim_status": "QUESTIONABLE",       # CONSISTENT | QUESTIONABLE | INSUFFICIENT_INFORMATION | NO_CLAIM
    "evidence": ["The label lists brown rice syrup."],
    "explanation": "...",
    "confidence": "HIGH"}}                # HIGH | MEDIUM | LOW
# On failure: {"ok": False, "ai_analysis": None, "error_code": "API_UNAVAILABLE", "provider": None}
```

**Saved record** = product + `profile_snapshot` + `ai_analysis` + `flags` + `analysed_at`.

---

## 3. Business rules (logic_manager.py)

| Flag | When |
|---|---|
| `GOAL_MISMATCH` | Sugar/sodium **above** the maximum, or protein **below** the minimum. Equal counts as meeting the target. The AI cannot cancel this. |
| `CLAIM_REVIEW` | **Multi-condition rule:** a claim was given **AND** the AI says `QUESTIONABLE` **AND** confidence is `MEDIUM`/`HIGH`. |
| `MANUAL_REVIEW` | Confidence is `LOW`, **or** the goal nutrient is missing, **or** the AI says `INSUFFICIENT_INFORMATION`. |
| `GOOD_MATCH` | Target met **AND** no review flag **AND** the AI says `ALIGNED` **AND** the claim is `CONSISTENT`/`NO_CLAIM`. |

Several flags can appear together (e.g. `GOAL_MISMATCH` + `CLAIM_REVIEW`). An empty list
means nothing is wrong, but the product did not earn a positive match either.

| Example | Flags |
|---|---|
| Sugar 14 g, max 10, claim QUESTIONABLE/HIGH | `GOAL_MISMATCH`, `CLAIM_REVIEW` |
| Same, but confidence LOW | `GOAL_MISMATCH`, `MANUAL_REVIEW` |
| Sugar not on label | `MANUAL_REVIEW` (never treated as 0) |
| Protein 20 g, min 15, ALIGNED, CONSISTENT, HIGH | `GOOD_MATCH` |

---

## 4. Setup and running

### Requirements
Python 3.10+. **No packages to install** because only the standard library is used.

### API keys
```bash
cp .env.example .env        # Windows: copy .env.example .env
```
Put your keys in `.env`. Gemini (`gemini-3.5-flash-lite`) is tried first. If it fails,
the program switches to Groq (`openai/gpt-oss-20b`). **Never commit `.env`**; it is already listed in `.gitignore`.

### Run locally
```bash
python main.py
```
Data is saved in `data/` (`profiles.json`, `analyses.json`, and `nutrilenz.log` for API errors).

### Run the tests
```bash
python test_logic.py              # required logic tests, no API needed
python test_data.py               # storage tests, uses a temp folder
python test_ai_manager.py         # AI parsing/validation/retry tests, no API needed
python test_ai_manager.py live    # sends sample products to the REAL API
python test_ai_manager.py live groq   # same, but tests the Groq backup only
```

### Run in Docker
```bash
docker build -t nutrilenz .
docker run --rm nutrilenz python test_logic.py
docker volume create nutrilenz-data
docker run --rm -it --env-file .env -v nutrilenz-data:/app/data nutrilenz
```
The named volume keeps your profiles and history between runs.

---

## 5. How the school requirements are met

| Requirement | Where |
|---|---|
| 4 managers | `io_manager.py`, `ai_manager.py`, `logic_manager.py`, `data_manager.py` |
| 100% procedural (no `class`) | All files use functions only |
| All `print()` in I/O | Only `io_manager.py` prints; other files return data or log to a file |
| Validate input, re-prompt | `read_number`, `read_choice`, `read_required_text` |
| Record + list/summary views | `show_analysis`, `show_history`, `select_profile` |
| Every record through AI | `main.handle_analyse` always calls `ai_manager.analyse_product` |
| Structured JSON + schema validation | `validate_ai_response` checks exactly 6 keys and allowed values |
| Retry on bad output, never crash | Up to 2 attempts per provider, then Groq backup, then a failure envelope |
| Business rules incl. multi-condition | `needs_claim_review` (claim AND QUESTIONABLE AND MEDIUM/HIGH) |
| Save/load JSON, query, handle bad files | `data_manager.py` (`query_history`, `CORRUPT_DATA` handling) |
| Same output across runs | AI temperature = 0; rules are deterministic; history is replayed from JSON |
| Logic test script without API | `test_logic.py` |
| Docker | `Dockerfile`, `.dockerignore` |

---

## 6. Error codes

| Code | From | Meaning |
|---|---|---|
| `CONFIGURATION_ERROR` | AI | No API key, or wrong model name |
| `AUTHENTICATION_ERROR` | AI | API key rejected |
| `API_CONNECTION_ERROR` | AI | No internet or timeout |
| `API_UNAVAILABLE` | AI | Rate limit or server error |
| `INVALID_RESPONSE` | AI | AI answer was not valid JSON/schema after retries |
| `CORRUPT_DATA` / `READ_ERROR` / `WRITE_ERROR` | Data | File broken, unreadable or not writable |
| `DUPLICATE_PROFILE` / `PROFILE_NOT_FOUND` | Data | Profile name conflict |
