# dexiotites

Reusable artifacts from the *LLM learnings* project: instructions and portable skills to install
into coding projects, plus mirrors of the personal Claude workflow skills built along the way.

| Path | Contents |
|---|---|
| `instructions/COMMENTING.md` | Commenting standard for AI coding agents: purpose-first comments, sourced rationale, comment-only retrofits. Ends with exemplar codebases and references. |
| `instructions/AGENTS-commenting-section.md` | Short block to append to a project's `AGENTS.md` so every agent session loads the core rules. |
| `instructions/lint/` | Doc-linter configs that enforce the mechanical part of the standard (Kotlin, Rust, Python, Lua). See [(c) Doc linters](#c-doc-linters-tier-1). |
| `skills/` | One folder per skill (see [Skills](#skills)). |
| `MAINTENANCE.md` | Authoring and review checklist for updating skills, instructions, and verifiers (especially with smaller models). |
| `tests/` | Unit and repository-hygiene tests (run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`). |
| `docs/` | Reserved for specs and design notes. |

**Prompting guide:** the living guide to working with LLMs is a Google Doc,
[Prompting Guide: Working with Claude](https://docs.google.com/document/d/1RlEDKMVg3FysnslHnX-OeYwoRcQ_tGh_FbuuCB_UjD8/edit)
(also holds the paste-ready `<prompt_coaching>` standing instructions tab; snapshot a copy into
`instructions/` if you want local offline agents to read it directly). The `prompt-lint` and
`prompt-guide-update` skills read and update it.

---

## Commenting standard

The standard has four parts, from most to least judgment:
1. `COMMENTING.md`: the full rules and examples, copied into the project.
2. A short section in `AGENTS.md`: always loaded, so new code gets commented as it is written.
3. The `annotate-code` skill: retrofits comments into existing code, changing comments only.
4. A doc linter (Tier 1): mechanically checks that public declarations are documented and
   that documented parameters match the code. Supported languages: Kotlin, Rust, Python, Lua.

How each agent finds them:
- **Antigravity** reads `AGENTS.md` and discovers skills in `.agents/skills/<name>/` (workspace)
  or `~/.gemini/config/skills/<name>/` (global, every workspace).
- **Claude Code** reads `CLAUDE.md`, not `AGENTS.md`. A `@AGENTS.md` line at the top of
  `CLAUDE.md` imports it. Claude Code skills live in `.claude/skills/`; symlinking to
  `.agents/skills/` lets one copy serve both agents.

### (a) Setting up a project (safe for new or existing repos)

From the target project's root (`$DEX` is your clone of this repo):

```bash
DEX=~/programming/dexiotites.git

mkdir -p docs .agents/skills .claude/skills
cp "$DEX/instructions/COMMENTING.md" docs/
if ! grep -qs '^## Code Comments' AGENTS.md; then
  [ -s AGENTS.md ] && printf '\n' >> AGENTS.md
  cat "$DEX/instructions/AGENTS-commenting-section.md" >> AGENTS.md
fi
if [ -L CLAUDE.md ]; then
  :   # already a symlink (usually to AGENTS.md); writing through it would edit its target
elif [ ! -e CLAUDE.md ]; then
  echo '@AGENTS.md' > CLAUDE.md
elif ! grep -q '^@AGENTS.md' CLAUDE.md; then
  printf '@AGENTS.md\n\n%s\n' "$(cat CLAUDE.md)" > CLAUDE.md
fi
cp -r "$DEX/skills/annotate-code" .agents/skills/
ln -sfn ../../.agents/skills/annotate-code .claude/skills/annotate-code
```

Then add the doc linter for each language the project uses ((c) below), and commit (check that
the appended heading in `AGENTS.md` fits any existing section numbering). From then on, agents
comment new code as they write it. For personal projects on your own machine, Antigravity can
instead load `annotate-code` and `distill-spec` globally: copy or symlink each skill folder into
`~/.gemini/config/skills/` rather than into every repo.

### (b) Retrofitting existing code

1. Commit or stash any work in progress. The checker compares files against `HEAD` and refuses
   to start if target files are untracked or have uncommitted code changes.
2. Run the skill on a small scope first, one file or one package (see below).
3. Review the diff. Read the summary for anything marked `RATIONALE-UNKNOWN` (questions only you
   can answer) and for suspected bugs, which the skill reports but never fixes.
4. Build the project, then commit.

### (c) Doc linters (Tier 1)

Add one block per language the project uses. Each linter enforces only documentation rules, so
adopting it doesn't bring in a style policy. `docs/COMMENTING.md` §8 lists the finish-gate
commands agents run. In a **new project** the gate must be clean. In a project that **already
has code**, findings in existing files don't block work: agents fix findings in the files they
change (Kotlin projects can record today's findings in a baseline instead).

**Kotlin (detekt 2.0).** The 2.0 line is required for Kotlin 2.2+ / Gradle 9 / AGP 9; at the time
of writing it is an alpha, so the version is pinned.

```bash
mkdir -p config/detekt && cp "$DEX/instructions/lint/detekt-comments.yml" config/detekt/
```

```kotlin
// In each module's build.gradle.kts that has Kotlin sources (the app module on Android):
plugins {
    id("dev.detekt") version "2.0.0-alpha.6"
}

detekt {
    buildUponDefaultConfig = true
    config.setFrom(rootProject.file("config/detekt/detekt-comments.yml"))
    // Existing projects: run `./gradlew detektBaseline` once, then uncomment.
    // baseline = file("detekt-baseline.xml")
}
```

Gate: `./gradlew detekt`.

**Rust.** Append the `[lints]` tables to `Cargo.toml` (workspaces: see the file's header):

```bash
if ! grep -q '^\[lints\.' Cargo.toml; then
  printf '\n' >> Cargo.toml
  cat "$DEX/instructions/lint/rust-cargo-lints.toml" >> Cargo.toml
fi
```

Gate: `cargo clippy --all-targets -- -D warnings && RUSTDOCFLAGS="-D warnings" cargo doc --no-deps`
(clippy checks presence and `# Errors`/`# Panics`/`# Safety`/`SAFETY:`; rustdoc checks `[links]`).

**Python (ruff).** With no ruff config yet:

```bash
[ -e ruff.toml ] || [ -e .ruff.toml ] || grep -qs '^\[tool\.ruff' pyproject.toml \
  || cp "$DEX/instructions/lint/ruff-docstrings.toml" ruff.toml
```

With an existing config, merge the tables by hand (in `pyproject.toml`, prefix them with
`tool.ruff.`). Gate: `ruff check --select D .`

**Lua (lua-language-server).** With no `.luarc.json` yet:

```bash
[ -e .luarc.json ] || cp "$DEX/instructions/lint/luarc-docs.json" .luarc.json
```

With an existing `.luarc.json`, merge the two `diagnostics.*` objects into it. Gate:
`lua-language-server --check=. --checklevel=Warning --configpath=.luarc.json` (exit code 1 when
anything is reported). Tested with lua-language-server 3.19.2.

### Running annotate-code

| Where | How |
|---|---|
| Claude Code (project install) | `/annotate-code path/to/File.kt`, or ask: "annotate `src/tracking/` per COMMENTING.md". |
| Antigravity (project or global install) | Ask in plain language ("annotate `src/tracking/` per COMMENTING.md"). The agent activates the skill from its description. |
| Claude desktop app (account skill) | Connect the project folder, then `/annotate-code <path>` or ask. The account version writes its embedded checker to a temporary file. |
| By hand | `python3 .agents/skills/annotate-code/scripts/comment_diff_check.py --strict <files>` from the project root. With `--strict`, exit code 0 guarantees every named file is a supported type (`.kt`, `.kts`, `.rs`, `.py`, `.lua`), has a `HEAD` baseline, and changed comments only. Without `--strict`, unsupported (`SKIP`) and untracked (`NEW`) files are reported without failing whole-repo `git diff` scans. |

---

## Skills

### Portable / project skills

Reusable across coding repositories and agent harnesses (Antigravity, Claude Code, Claude Desktop):

| Skill | What it does | External requirements |
|---|---|---|
| `annotate-code` | Comment-only retrofit of existing code (Kotlin, Rust, Python, Lua) to `COMMENTING.md`, verified by `scripts/comment_diff_check.py` and the project's doc linter. | The project's `COMMENTING.md`; git, with target files committed (the checker compares against `HEAD`); Python 3.9+. The project's build command and doc linter (detekt, `cargo clippy`/`cargo doc`, ruff, or lua-language-server; see [(c)](#c-doc-linters-tier-1)) when the project has them. |
| `distill-spec` | Distills a finished working conversation into a standalone RFC-2119 functional spec (with cold-read subagent check and optional evaluation harness). | Subagent tool for the cold-read test (optional; falls back to asking you to paste the spec into a fresh chat). Past-chats tool or session transcript to re-read summarized turns (optional; unreachable turns are marked as gaps). |

### Personal workflow & maintenance skills

Tailored to Jim's Claude Desktop setup, Google Doc prompting guide, and this repository:

| Skill | What it does | External requirements |
|---|---|---|
| `prompt-lint` | Checks a draft prompt against the prompting guide's checklist, routes model tier + effort, and returns a tightened version. | Google Drive connector (optional; falls back to embedded checklist). |
| `prompt-guide-update` | Folds new prompt feedback from recent chats into the prompting guide Google Doc and syncs the coaching block. | Google Drive & Google Docs connectors; `google-workspace` skill (`docs_index.py`). |
| `sync-skills-repo` | Syncs the Claude account versions of these skills into this repo using a recorded merge base to detect repo-side edits, extracts embedded helper scripts, commits, and pushes. | Access to `~/.claude/skills/synced/` and push access to `daemacles/dexiotites`. |

### Keeping the copies current

- **Account vs. repo ownership:** `instructions/` and `tests/` are mastered directly in this git
  repo. For `skills/`, the account copies in the Claude app are the primary source, synced here
  by `sync-skills-repo`. `skills/.sync-base.json` records which account version each repo copy
  was last synced from (its merge base), so the sync can tell "only the account changed" (copy)
  from "the repo was edited" (stop and offer a merge). After a merge, the skill stays flagged
  until the account copy is updated to match.
- **Embedded files:** a skill can carry a helper file inside its `SKILL.md` as a fenced block
  preceded by `<!-- embedded-file: <path> -->`. `sync-skills-repo` extracts each block to
  `skills/<name>/<path>` (preserving `+x` on `#!` scripts). `annotate-code` embeds
  `comment_diff_check.py` and `sync-skills-repo` embeds `sync_classify.py`; **always edit each
  script and its embedded block together**, and verify with `python3 -m unittest discover -s tests`.
- **New skills:** add each new account skill here by running `sync-skills-repo`.
