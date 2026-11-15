# Repository Rules (`dexiotites`)

This repository holds reusable instructions (`instructions/`) and agent skills (`skills/`).

## Source-of-Truth & Editing Rules

1. **`instructions/` and `tests/` are mastered in this git repository.** Edit them directly here.
2. **`skills/` mirrors Claude account skills via `skills/sync-skills-repo/SKILL.md`.**
   - If you edit anything under `skills/` in git, commit cleanly and remember that the Claude
     account copy should also be updated (otherwise the next `sync-skills-repo` run will pause
     and ask to merge).
3. **Embedded helper files must stay byte-for-byte identical.**
   - `skills/annotate-code/scripts/comment_diff_check.py` is generated from the
     `<!-- embedded-file: scripts/comment_diff_check.py -->` block at the bottom of
     `skills/annotate-code/SKILL.md`.
   - Never edit one without updating the other, keep the executable bit (`chmod +x`) on `#!`
     scripts, and run `python3 -m unittest discover -s tests -v` before finishing.
   - Do not leave `__pycache__` directories inside `skills/` (so `cp -r skills/<name>` stays clean).

## Code Comments (Purpose-First Documentation)
Full standard with examples: **`instructions/COMMENTING.md`**. Read it before writing or editing Python/script code in this repo. Core rules:
- **Reader:** an experienced engineer who should not have to read function bodies to understand purpose. No explanations of language features; no analogies to other languages.
- **Required:** a header on every file; a doc comment on every non-trivial type and function (purpose, parameters with units/ranges, return value, plus side effects, failure behavior, and calling contract where present/non-obvious). Omit `"None"` boilerplate on pure helpers.
- **Never invent rationale:** cite the source, derive it from the code, or write `RATIONALE-UNKNOWN: <question>`.
- **Keep comments true:** any code change updates the comments describing it in the same edit.
