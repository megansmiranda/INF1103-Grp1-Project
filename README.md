# NutriLenz — AI Food Label Interpreter (Part 2, OOP web app)

[![CI-CD](https://github.com/megansmiranda/INF1103-Grp1-Project/actions/workflows/ci.yml/badge.svg)](https://github.com/megansmiranda/INF1103-Grp1-Project/actions/workflows/ci.yml)

INF1103 LAB-P12 Group 1 · Repository: https://github.com/megansmiranda/INF1103-Grp1-Project

NutriLenz helps young adults in Singapore understand packaged food labels. Sign up, choose
one or more goals (e.g. *reduce sugar* **and** *low calories*), then type in a label or upload
photos of it. The AI explains the ingredients and checks the marketing claim, the business rules
flag anything to look at, and the result is saved to your history. Recommendations rank saved
products against your goals and the AI suggests real products to try in Singapore.

Design notes for the report (UML, OOP concepts, SOLID, patterns, exception matrix):
**[docs/DESIGN.md](docs/DESIGN.md)**

---

## 1. Run it

### With Docker (recommended: app + MySQL)
```bash
cp .env.example .env          # then put your GEMINI_API_KEY (and/or GROQ_API_KEY) in .env
docker compose up --build
```
Open **http://localhost:5000**. On first start the database is filled with demo data.

| Demo account | Password | Goals | Avoids |
|---|---|---|---|
| `jane` | `jane12345` | Sugar ≤ 10 g, Calories ≤ 200 kcal | maltodextrin |
| `sam` | `sam12345` | Protein ≥ 15 g, Sodium ≤ 400 mg | peanuts |

Stop with `Ctrl+C`, then `docker compose down` (add `-v` to also delete the database).

### Without Docker (no database needed)
```bash
pip install -r requirements.txt
NUTRILENZ_STORAGE=memory python main.py      # PowerShell: $env:NUTRILENZ_STORAGE="memory"; python main.py
```
`memory` storage keeps data only while the app runs. Use `mysql` with your own MySQL server
and the `DB_*` settings in `.env.example` to keep data.

## 2. Run the tests (no API key, no database needed)
```bash
docker compose run --rm app python -m pytest          # inside the container
python -m pytest                                      # or locally
```
150 tests cover the domain classes, business rules, AI parsing/validation/retry/fallback (using fake
API replies), both storage back ends, the services, background jobs, the web pages and the
architecture rules. The 11 MySQL contract tests run when `NUTRILENZ_TEST_MYSQL=1` is set
(CI does this with a MySQL service).

## 3. Features

| Feature | Where |
|---|---|
| Sign up / log in (salted PBKDF2 password hashes), edit goals, delete account | My goals |
| **Multiple goals** from 8 nutrients (sugar, protein, sodium, calories, fat, saturated fat, carbs, fibre) | Sign up / My goals |
| Analyse a typed-in label (with "unusual number" and "already analysed" checks) | Analyse |
| **Upload up to 5 label photos** – the AI reads them **in parallel**, you check the values, then they are analysed in parallel | Analyse |
| Result: per-goal check, flags, 0–100 score, AI explanation, tips and **real Singapore products to try** | Analysis page |
| History with search and flag filter, view and delete | History |
| Dashboard summary (counts per flag, average score) | Dashboard |
| **Recommendations from fixed options** (focus + category, no free text) with a cache so repeats cost no API call | Recommendations |

## 4. Architecture

```
Browser ─► WebIOManager (Flask pages, FormParser) ─► JobManager (thread pool)
                                                        │
                       AnalysisService / RecommendationService
                        │                │                │
                    AIManager       LogicManager      DataManager ─► MySQLDataStore / InMemoryDataStore
              (Gemini → Groq)     (Rule classes)     (accounts, products, analyses)
```

| Package | Manager | Job |
|---|---|---|
| `nutrilenz/web` | **IO Manager** (`WebIOManager`) | Pages, form validation, showing results. Only part that talks to the user. |
| `nutrilenz/ai` | **AI Manager** (`AIManager`) | Every record goes through it. Builds prompts, calls Gemini (backup Groq), parses and validates JSON. |
| `nutrilenz/logic` | **Logic Manager** (`LogicManager`) | Flags (GOAL_MISMATCH, CLAIM_REVIEW, MANUAL_REVIEW, GOOD_MATCH), score, ranking, warnings. |
| `nutrilenz/data` | **Data Manager** (`DataManager`) | MySQL (or in-memory) storage, login, history queries, demo data. |
| `nutrilenz/domain` | – | Product, Goal, Profile, User, Analysis, Recommendation. |
| `nutrilenz/services` | – | The AI → Logic → Data pipeline and background jobs. |

## 5. Settings (`.env`)
See `.env.example`. API keys are never committed and are not in the Docker image.

## 6. CI/CD
`.github/workflows/ci.yml` runs on every push and pull request:
1. builds the Docker image and runs all tests inside it,
2. runs the data tests against a real **MySQL** service,
3. starts the whole stack with `docker compose` and checks the website loads,
4. **CD:** on `main`, after all checks pass, publishes the image to GitHub Container Registry
   (`ghcr.io/megansmiranda/inf1103-grp1-project:latest`).
