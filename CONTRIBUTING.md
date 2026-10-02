# How we work together

## First-time setup
1. Clone the repo to a folder **outside OneDrive** (e.g. `C:\dev`). OneDrive syncing can corrupt the `.git` folder.
   ```
   git clone https://github.com/megansmiranda/INF1103-Grp1-Project
   ```
2. Copy `.env.example` to `.env` and put in your own API keys. `.env` is ignored by git, so never force-add it.
3. Check everything works: `python main.py`

## Branches
- `main` must always run. Nobody pushes to `main` directly; changes come in through pull requests.
- Each person works on their own layer branch (`ai_manager`, `data_manager`, `io_manager`, `logic_manager`, `integration`)
  or on a short task branch named after the layer, e.g. `logic/zero-target-fix`.

## Daily routine
```
git switch <your-branch>
git pull                    # get your own latest work
git merge origin/main       # bring in everyone else's merged work (after: git fetch)
# ... edit, test ...
git add <the files you changed>
git commit -m "ai: retry once on invalid JSON"
git push
```
Then open a pull request into `main` on GitHub.

## Pull requests
- At least **1 approval** before merging. The owner of a file should review changes to it.
- The **CI checks must be green** (the three test scripts plus the Docker build).
- Keep PRs small: one feature or fix each.

## Rules between layers
- The dicts passed between managers (`{"ok": ..., "error_code": ...}`, the AI analysis fields, etc.) are a shared contract.
  If you change one, tell the group first and update `sample_data.py` plus the affected tests in the same PR.
- `main.py` and `sample_data.py` are shared by everyone, so keep edits there small and merge them quickly.

## Commit messages
Start with the layer: `ai: ...`, `data: ...`, `io: ...`, `logic: ...`, `main: ...`, `ci: ...`

## Never commit
`.env`, API keys, `data/`, `__pycache__/`. If a key is ever pushed, create a new key right away. Deleting the commit is not enough.
