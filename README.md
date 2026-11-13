# NutriLenz - Phase 2 AI food label checker

[![CI-CD](https://github.com/megansmiranda/INF1103-Grp1-Project/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/megansmiranda/INF1103-Grp1-Project/actions/workflows/ci.yml)

INF1103 LAB-P12 Group 1. NutriLenz is an object-oriented Flask web app for interpreting
packaged food labels against personal nutrition goals and dietary preferences. Enter
label details or upload photos, review the extracted values, and receive goal checks,
rule-based flags, a score and AI explanations. Accounts, products and analysis history
are stored in MySQL 8.4.

See [docs/DESIGN.md](docs/DESIGN.md) for the UML and design discussion. The schema is
[nutrilenz/data/schema.sql](nutrilenz/data/schema.sql).

## Features

- Accounts with salted PBKDF2 password hashes, login/logout, profile editing and deletion.
- One to five simultaneous goals from eight nutrients: sugar, protein, sodium,
  calories, fat, saturated fat, carbohydrate and fibre.
- Optional vegetarian, no-dairy vegetarian or vegan diet, halal-friendly and allergen
  checks, plus a separate custom ingredient avoid list.
- Typed label analysis with unusual-number and repeat-analysis confirmation.
- Up to five JPG, PNG or WEBP photos per upload, each at most 8 MiB. Background jobs
  extract details concurrently; users review/edit them before submitting analysis jobs.
- Goal results, all five flags below, a 0-100 score, AI explanations, tips and
  AI-generated product suggestions for Singapore.
- History search, flag filtering, details and deletion. Dashboard counts, average
  score and counts for the four original flags; no separate DIETARY_REVIEW summary.
- Recommendations from selected focuses/categories, deterministic catalogue ranking,
  and cached AI advice.
- Flask GUI, MySQL persistence, background threading and GitHub Actions publishing.

Dietary results are ingredient keyword checks. NO_MATCH does not establish safety,
allergen absence, dietary suitability or halal certification. AI product suggestions
are generated advice, not a verified product database or certification.

## Run with Docker

Install Docker with Compose support and start its engine. From the repository root:

```bash
cp .env.example .env
docker compose up --build
```

PowerShell can use `Copy-Item .env.example .env`. Open **http://localhost:5000**.
Compose starts the Flask app and MySQL 8.4, waits for the database healthcheck, and
persists MySQL data in a named volume. Tables are created and demo data is seeded
when the store is empty.

| Demo username | Password | Goals | Custom avoid list |
|---|---|---|---|
| `jane` | `jane12345` | Sugar <= 10 g; calories <= 200 kcal | maltodextrin |
| `sam` | `sam12345` | Protein >= 15 g; sodium <= 400 mg | peanuts |

The template has empty AI keys. Login, demo history and tests work without AI
credentials. Add your own Gemini and/or Groq key to `.env` for analysis, photo
extraction and uncached recommendations, then restart/recreate the app. Gemini is
tried first, with Groq as fallback when configured. Model names in the template are
the code defaults; availability depends on the provider/account.

Stop with Ctrl+C, then `docker compose down`. The database survives this command;
`docker compose down -v` deletes this stack's database volume. Changing passwords
in `.env` does not change credentials in an already-initialised MySQL volume.

### Run Python directly

Use Python 3.12:

```bash
pip install -r requirements.txt
NUTRILENZ_STORAGE=memory python main.py
```

PowerShell:

```powershell
$env:NUTRILENZ_STORAGE="memory"
python main.py
```

`main.py` is the single minimal bootstrap for `NutriLenzApp`. Memory storage loses
changes on exit. For persistence outside Compose, provision MySQL and set
`NUTRILENZ_STORAGE=mysql` and the `DB_*` connection settings.

## Four managers and supporting classes

| Responsibility | Manager | Main supporting classes |
|---|---|---|
| IO: Flask pages, forms and presentation | `WebIOManager` | `PageController`, `AccountPages`, `AnalysisPages`, `HistoryPages`, `RecommendationPages`, `FormParser`, `LoginSession`, `CsrfGuard`, `DietaryPresenter` |
| AI: prompts, providers, parsing and validation | `AIManager` | `AIProvider`, `GeminiProvider`, `GroqProvider`, `HttpClient`, `AITask`, `LabelAnalysisTask`, `LabelExtractionTask`, `RecommendationTask`, `JsonReplyParser`, `SchemaChecker` |
| Logic: goals, flags, scoring and ranking | `LogicManager` | `Rule` and its five subclasses, `DietaryChecker`, `Evaluation`, `EvaluationContext`, `Goal`, `LimitGoal`, `MinimumGoal` |
| Data: accounts, products, analyses and persistence | `DataManager` | `DataStore`, `MySQLDataStore`, `InMemoryDataStore`, `UserRepository`, `ProductRepository`, `AnalysisRepository`, `RecordMapper`, `PasswordHasher`, `DemoDataSeeder` |

`NutriLenzApp` composes the managers using `AppConfig`. `AnalysisService` checks
dietary ingredients, calls AI, applies logic and saves the analysis. If saving
fails, it returns the completed analysis with `saved=False` and an error code.
`RecommendationService` ranks the catalogue and requests AI advice.

`JobManager` owns a `ThreadPoolExecutor` (three workers by default). `Job` and
`Batch` track work; `JobObserver`/`JobLogger` observe updates. Browser pages poll
progress. Jobs, batches and the recommendation cache live in process memory and
are lost on restart. Completed jobs older than 3,600 seconds are pruned when new
jobs are submitted.

## Environment settings

Copy [.env.example](.env.example) and replace credential placeholders locally.
`AppConfig` loads `.env` without overwriting existing process environment variables.
Never commit `.env`; Git ignores it and `.dockerignore` excludes it from the image.

| Setting | Code default / purpose |
|---|---|
| `GEMINI_API_KEY` | Empty; enables Gemini when set |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `GROQ_API_KEY` | Empty; enables Groq when set |
| `GROQ_MODEL` | `openai/gpt-oss-20b` |
| `GROQ_VISION_MODEL` | `meta-llama/llama-4-scout-17b-16e-instruct` |
| `AI_TIMEOUT_SECONDS` | `30` per HTTP request |
| `FLASK_SECRET_KEY` | Random if unset/empty; set a long random value to retain valid login cookies across restarts |
| `NUTRILENZ_STORAGE` | `mysql`; use `memory` for temporary storage |
| `DB_HOST` | `localhost`; Compose overrides with `db` |
| `DB_PORT` | `3306` |
| `DB_USER` | `nutrilenz` |
| `DB_PASSWORD` | Empty in code; template supplies a local placeholder for both Compose services |
| `DB_NAME` | `nutrilenz` |
| `DB_ROOT_PASSWORD` | Compose-only setting; template supplies a local placeholder |
| `SEED_DEMO_DATA` | `true`; `1`, `true` and `yes` enable seeding (case ignored) |
| `WORKER_THREADS` | `3`, minimum `1` |
| `HOST` | `127.0.0.1` directly; Dockerfile sets `0.0.0.0` |
| `PORT` | `5000`; Compose publishes container port 5000 on host port 5000 |
| `LOG_FILE` | `nutrilenz.log` directly; Dockerfile sets `/app/logs/nutrilenz.log` |
| `NUTRILENZ_TEST_MYSQL` | Test-only: `1` enables destructive MySQL contract tests |
| `TEST_DB_NAME` | Test-only: `nutrilenz_test`; must differ from the application's `DB_NAME` |

Compose fixes the app's storage to MySQL and host/port/user/name to
`db`/`3306`/`nutrilenz`/`nutrilenz`. Leave optional `HOST`, `PORT` and `LOG_FILE`
overrides commented for the standard Docker commands.

## Business rules and flags

These rules describe the current [logic](nutrilenz/logic) and [domain](nutrilenz/domain) code.

### Goals and input

- A profile has 1-5 goals, no repeated nutrient and positive finite targets. Web
  forms cap targets at 10,000. MAX goals are met at or below the target; MIN goals
  at or above it. Equality counts as met. Missing label values give MISSING;
  blank is not zero.
- Web presets minimise sugar, sodium, calories, fat, saturated fat and carbohydrate;
  they maximise protein and fibre. Web nutrition values must be finite and between
  0 and 10,000 inclusive, with at least one supplied value.
- Usernames are 3-40 letters, digits, dots, dashes or underscores. Registration
  requires matching passwords of at least eight characters. Login ignores username case.
- The custom avoid list accepts up to 20 comma-separated entries, each at most
  60 characters. Profiles remove blank and case-insensitive duplicate entries.
  Matching uses case-insensitive **substrings** of the ingredient text.

### Flags

Rules run in this order. Several concern flags can coexist; GOOD_MATCH requires
that no earlier rule added a flag.

| Order | Flag | Exact trigger |
|---|---|---|
| 1 | `GOAL_MISMATCH` | At least one goal result is MISMATCH. |
| 2 | `CLAIM_REVIEW` | A marketing claim is present, AI claim_status is QUESTIONABLE, and AI confidence is MEDIUM or HIGH. |
| 3 | `MANUAL_REVIEW` | At least one goal is MISSING, or AI confidence is LOW, or AI goal_alignment or claim_status is INSUFFICIENT_INFORMATION. |
| 4 | `DIETARY_REVIEW` | The dietary report has at least one POSSIBLE_CONCERN from matched ingredient keywords. |
| 5 | `GOOD_MATCH` | All goals are MET, no earlier flag exists, AI goal_alignment is ALIGNED, and AI claim_status is CONSISTENT or NO_CLAIM. |

GOOD_MATCH concerns the selected goals, not overall health. Absence of
DIETARY_REVIEW does not assure dietary suitability.

### Score and warnings

For each goal, with label value `v` and target `t`, closeness is:

- MAX: `1` if `v <= t`; otherwise `max(0, 1 - (v - t) / t)`.
- MIN: `min(1, v / t)`.
- Missing value: `0.5`.

The score is `100 * mean(closeness) - 25 * matched_custom_avoid_entries`, clamped
to 0-100 and rounded to one decimal place. AI explanations and dietary concern
flags do **not** change the score.

Values strictly above these per-serving limits trigger confirmation warnings,
not flags or automatic rejection:

| Sugar | Protein | Sodium | Calories | Fat | Saturated fat | Carbohydrate | Fibre |
|---|---|---|---|---|---|---|---|
| 100 g | 100 g | 5,000 mg | 2,000 kcal | 100 g | 50 g | 200 g | 50 g |

The typed-label page also asks for confirmation when that user has previously
analysed the same product name. Confirming creates a new analysis record.

### Dietary checks and recommendations

Users may select one diet (vegetarian, no-dairy vegetarian or vegan), plus
halal-friendly and any of six allergen checks: nuts, dairy, gluten, egg, soy and
shellfish. Vegetarian checks meat, animal fats, fish, shellfish and hidden animal
ingredients; no-dairy vegetarian adds dairy; vegan adds dairy, egg and other animal
ingredients. Halal-friendly checks pork-related terms, gelatine and alcohol.

`DietaryChecker` matches case-insensitive whole words/phrases with optional plural
suffixes and the dairy exceptions in `DietaryKeywords`. Missing/blank ingredients
give NOT_CHECKED; supplied text gives POSSIBLE_CONCERN when a keyword matches,
otherwise NO_MATCH. Reports save matched words and spans with rules version
`image-rules-v1`. History retains saved goals, scores and dietary results; legacy
rows without dietary results are not recalculated. Legacy profiles containing
multiple diets load the strictest saved diet.

Catalogue recommendations filter by selected categories and require values for
selected nutrient focuses. They exclude dietary concerns and custom avoid-list
matches; unknown ingredients remain eligible. Eligible products are sorted by
mean relative focus rating, then goal score, and the top five form the shortlist.
Best-match focus (or no nutrient focus) includes score/100 in that rating. AI picks
may only refer to shortlisted product IDs; separate AI-generated product suggestions
can refer to products outside the catalogue.

The in-process cache holds at most 100 entries and keys by user ID, profile snapshot,
focus/category options and catalogue product IDs. Identical cached requests reuse
advice without another AI call.

### AI retry and failure handling

Every new label analysis calls AI before applying the rules. `AIManager` tries
configured providers in order, with at most two attempts per provider. Invalid
output is retried with validation feedback. CONFIGURATION_ERROR,
AUTHENTICATION_ERROR and NO_IMAGE_PROVIDER skip further retries on that provider.
API_UNAVAILABLE waits one second before a remaining retry. If all attempts fail,
the last AI error code is raised. Photo tasks only use image-capable providers.

## Error codes

Messages below are copied from [ErrorMessages](nutrilenz/errors/error_messages.py),
with the background-job fallback noted separately. Codes are distinct from flags.

| Code | User-facing message |
|---|---|
| `CONFIGURATION_ERROR` | AI is not set up correctly (check the API keys and model names in .env). |
| `AUTHENTICATION_ERROR` | The AI service rejected the API key. |
| `API_CONNECTION_ERROR` | Could not reach the AI service. Check your internet connection. |
| `API_UNAVAILABLE` | The AI service is busy or unavailable. Please try again later. |
| `INVALID_RESPONSE` | The AI did not give a usable answer after the allowed attempts. |
| `NO_IMAGE_PROVIDER` | No AI service that can read images is set up. |
| `UNREADABLE_IMAGE` | The AI could not read a nutrition label in that photo. Try a clearer photo or type it in. |
| `DB_UNAVAILABLE` | The database cannot be reached right now. Please try again shortly. |
| `CORRUPT_DATA` | Some saved data is damaged and could not be loaded. |
| `DUPLICATE_USER` | That username is already taken. |
| `USER_NOT_FOUND` | That account no longer exists. |
| `RECORD_NOT_FOUND` | That record could not be found. |
| `BAD_LOGIN` | Wrong username or password. |
| `INVALID_INPUT` | Some details are not valid. Please check the form. |
| `JOB_NOT_FOUND` | That task could not be found. It may have expired. |
| `UNEXPECTED_ERROR` | Background Job fallback for an unexpected exception; generic message: Something went wrong (UNEXPECTED_ERROR). |

ValidationError also carries field-specific messages. Unknown codes use
`Something went wrong (<code>).` Missing pages/jobs can return HTTP 404 rather
than a coded exception. The app error handler uses HTTP 503 for DB_UNAVAILABLE
and HTTP 400 for other NutriLenzError exceptions; login failures use HTTP 401.

## Tests

```bash
docker compose run --rm app python -m pytest
```

Or install requirements and run `python -m pytest`. Tests cover domain objects,
rules, dietary matching/history, fake AI responses, storage, services, background
jobs, Flask pages and architecture constraints. The shared fixture removes inherited
AI keys and rejects live AI HTTP requests. Providers use fake HTTP replies; no real
API key is needed.

The default suite skips MySQL contract cases. CI runs them with
`NUTRILENZ_TEST_MYSQL=1`, `TEST_DB_NAME=nutrilenz_test` and `DB_*` settings pointing
to disposable MySQL 8.4. These tests delete rows and alter tables in that test
database; never point them at the application's database. Test credentials must
permit creating tables and altering the test schema.

## CI/CD

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every push and PR:

1. Build the Docker image and run the full pytest suite inside it.
2. Run tests/test_data.py against both in-memory storage and a MySQL 8.4 service.
3. Copy .env.example, build/start Compose, check /login on port 5000, and verify
   the seeded jane account can log in. Tear down the stack afterward.
4. On a **push to main only**, after all three checks pass, publish image tags
   latest and the commit SHA to ghcr.io/megansmiranda/inf1103-grp1-project.

Publishing uses GITHUB_TOKEN; application AI keys are not required by CI. There
are no Phase 1 test-script references or no-class restrictions. Architecture tests
require the four managers to be classes and prohibit module-level functions
inside nutrilenz/.
