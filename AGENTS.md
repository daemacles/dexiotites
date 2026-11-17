# Repository Rules (`dexiotites`)

This repository holds reusable instructions (`instructions/`) and agent skills (`skills/`).

## Mandatory Pre-Flight & Verification Gate

- **Before editing `skills/`, `instructions/`, or `README.md`:** read **`MAINTENANCE.md`** and apply
  every check in the section(s) matching what you are changing.
- **Before finishing any edit in this repo:** run
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` and fix any failure.
- **When you uncover a new class of miss:** encode it in `tests/test_repo_hygiene.py` if checkable
  in Python, or add a concise trigger bullet to `MAINTENANCE.md` (§5).

## Source-of-Truth & Editing Rules

1. **`instructions/`, `install.py`, `tests/`, and `MAINTENANCE.md` are mastered in this git
   repository.** Edit them directly here. Projects get their copies from `install.py`; after
   changing `instructions/` or `skills/annotate-code/`, tell the user which projects to rerun it in.
2. **`skills/` mirrors Claude account skills via `skills/sync-skills-repo/SKILL.md`.**
   - If you edit anything under `skills/` in git, commit cleanly and remember that the Claude
     account copy should also be updated (otherwise the next `sync-skills-repo` run will pause
     and ask to merge).
3. **Embedded helper files must stay byte-for-byte identical.**
   - `skills/annotate-code/scripts/comment_diff_check.py`, `skills/annotate-code/scripts/comment_load.py`
     and `skills/sync-skills-repo/scripts/sync_classify.py` are generated from the
     `<!-- embedded-file: scripts/... -->` block at the bottom of their skill's `SKILL.md`.
   - Never edit one without updating the other, keep the executable bit (`chmod +x`) on `#!`
     scripts, and do not leave `__pycache__` directories inside `skills/`.
4. **`skills/.sync-base.json` is written only by `sync_classify.py --record`.** It records the
   account version each repo copy was last synced from; never edit it by hand.

## Code Comments (Purpose-First Documentation)
Full standard with examples: **`instructions/COMMENTING.md`**. Read it before writing or editing Python/script code in this repo. Core rules:
- **Reader:** an experienced engineer who should not have to read function bodies to understand purpose. No explanations of language features; no analogies to other languages.
- **Required:** a header on every file; a doc comment on every non-trivial type and function (purpose, parameters with units/ranges, return value, plus side effects, failure behavior, and calling contract where present/non-obvious). Omit `"None"` boilerplate on pure helpers.
- **Never invent rationale:** cite the source, derive it from the code, or write `RATIONALE-UNKNOWN: <question>`.
- **Keep comments true:** any code change updates the comments describing it in the same edit.
- **Doc linter gate:** `ruff check --select D .` must pass (the test suite runs it when ruff is installed).
