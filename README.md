# dexiotites

Reusable artifacts from the *LLM learnings* project: instructions and portable skills to install
into coding projects, plus mirrors of the personal Claude workflow skills built along the way.

| Path | Contents |
|---|---|
| `install.py` | Installs or updates the commenting standard in a project with one command. See [Install or update](#install-or-update-one-command). |
| `instructions/COMMENTING.md` | Commenting standard for AI coding agents: purpose-first comments, sourced rationale, comment-only retrofits. Ends with exemplar codebases and references. |
| `instructions/AGENTS-commenting-section.md` | Short section the installer places in a project's `AGENTS.md` so every agent session loads the core rules. |
| `instructions/lint/` | Doc-linter configs that enforce the mechanical part of the standard (Kotlin, Rust, Python, Lua). See [Doc linters](#doc-linters-tier-1). |
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
1. `COMMENTING.md`: the full rules and examples, installed as `docs/COMMENTING.md`.
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

### Install or update (one command)

`install.py` sets up everything below in a project, and the same command updates it later.
From a clone of this repo:

```bash
python3 ~/programming/dexiotites.git/install.py                 # the project in the current directory
python3 ~/programming/dexiotites.git/install.py ~/projects/a ~/projects/b    # or several at once
```

With no clone at hand, this fetches one into a temporary folder and runs it:

```bash
curl -fsSL https://raw.githubusercontent.com/daemacles/dexiotites/main/install.py | python3 -
```

Then review `git status` and commit. Nothing else is needed: everything is installed as plain
files inside the project, so fresh clones, CI and cloud agent sessions get it with no extra
step. Requires Python 3.9+ and git.

| Installed in the project | Purpose |
|---|---|
| `docs/COMMENTING.md` | The full standard. |
| `.agents/skills/annotate-code/` | The retrofit skill and its checker (Antigravity reads it here). |
| `.claude/skills/annotate-code` | Symlink to the folder above, for Claude Code. |
| `AGENTS.md` | The always-loaded core rules, between `<!-- dexiotites:begin … -->` and `<!-- dexiotites:end -->`. Your own heading line (for example `## 6. Code Comments …`) is kept. |
| `CLAUDE.md` | Gets an `@AGENTS.md` line if it lacks one. |
| Doc-linter config | For each language found; see [Doc linters](#doc-linters-tier-1). |
| `.dexiotites.json` | Manifest: the dexiotites commit installed, options, and a hash of each copied file. Commit it. |

**Options**

| Option | Effect |
|---|---|
| `--check` | Writes nothing. Exit code 0 if the project is current, 1 if it is out of date or has conflicts. |
| `--skill NAME` | Also install another skill from `skills/` (for example `--skill distill-spec`). Remembered for later runs. |
| `--no-lint` / `--lint` | Leave out (and remove) the doc-linter configs, or turn them back on. Remembered. |
| `--force` | Replace conflicting files. Local edits in them are lost. |

**Conflicts.** The installer only replaces content it can prove came from dexiotites: files
unchanged since the last install, files identical to any version this repo has shipped (so
older hand-made installs upgrade cleanly), and the marked block in `AGENTS.md`. If anything
else is in the way (a copy edited in the project, or an unrelated file with the same name), it
lists the conflicts, **writes nothing**, and exits with code 1. Decide what the local edit was
for: move it out of the managed file, or make the change in this repo so every project gets
it. Use `--force` only to discard the local edits. Agents: on exit code 1, stop and show the
user the conflict list; do not add `--force` on your own.

**Do not edit the installed copies in a project.** Change the master in this repo, then rerun
the installer in each project. `--check` in a project tells you whether it is behind.

**As a git submodule (optional, not recommended).** The installer also runs from a submodule:
`git submodule add https://github.com/daemacles/dexiotites .dexiotites && python3 .dexiotites/install.py`,
and later `git submodule update --remote .dexiotites && python3 .dexiotites/install.py`. The
installed files are still plain copies, so clones that never fetch the submodule keep working.
The submodule adds this repo's own agent files, tests and personal skills to the project
tree, where Claude Code can pick them up and where project-wide searches and linters see them,
so prefer the plain command above.

For personal projects on your own machine, Antigravity can also load `annotate-code` and
`distill-spec` globally: copy or symlink each skill folder into `~/.gemini/config/skills/`.

### Retrofitting existing code

1. Commit or stash any work in progress. The checker compares files against `HEAD` and refuses
   to start if target files are untracked or have uncommitted code changes.
2. Run the skill on a small scope first, one file or one package (see below).
3. Review the diff. Read the summary for anything marked `RATIONALE-UNKNOWN` (questions only you
   can answer) and for suspected bugs, which the skill reports but never fixes.
4. Build the project, then commit.

### Doc linters (Tier 1)

Each linter enforces only documentation rules, so adopting it doesn't bring in a style policy.
`docs/COMMENTING.md` §8 lists the finish-gate commands agents run. In a **new project** the gate
must be clean. In a project that **already has code**, findings in existing files don't block
work: agents fix findings in the files they change (Kotlin projects can record today's findings
in a baseline instead).

The installer adds the config for each language it finds in the project. It never edits a
linter config it did not create; where one already exists it prints what to merge by hand.

| Language | Installed automatically | Left to you | Finish gate |
|---|---|---|---|
| Rust | The tables from `instructions/lint/rust-cargo-lints.toml`, appended to the root `Cargo.toml` in a marked block. | A `Cargo.toml` that already has `[lints]` tables, or is a workspace root (see the config's header). | `cargo clippy --all-targets -- -D warnings` and `RUSTDOCFLAGS="-D warnings" cargo doc --no-deps` |
| Python | `instructions/lint/ruff-docstrings.toml` as `ruff.toml`. | Any existing ruff config: merge the tables by hand (in `pyproject.toml`, prefix them with `tool.ruff.`). | `ruff check --select D .` |
| Lua | `instructions/lint/luarc-docs.json` as `.luarc.json`. | An existing `.luarc.json`: merge the two `diagnostics.*` objects into it. | `lua-language-server --check=. --checklevel=Warning --configpath=.luarc.json` |
| Kotlin | `instructions/lint/detekt-comments.yml` as `config/detekt/detekt-comments.yml`. | The Gradle plugin block below. | `./gradlew detekt` |

Clippy checks presence and `# Errors`/`# Panics`/`# Safety`/`SAFETY:`; rustdoc checks `[links]`.
The Lua gate exits with code 1 when anything is reported (tested with lua-language-server 3.19.2).

**Kotlin build file (detekt 2.0).** The 2.0 line is required for Kotlin 2.2+ / Gradle 9 / AGP 9;
at the time of writing it is an alpha, so the version is pinned. Add this by hand:

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
| `annotate-code` | Comment-only retrofit of existing code (Kotlin, Rust, Python, Lua) to `COMMENTING.md`, verified by `scripts/comment_diff_check.py` and the project's doc linter. | The project's `COMMENTING.md`; git, with target files committed (the checker compares against `HEAD`); Python 3.9+. The project's build command and doc linter (detekt, `cargo clippy`/`cargo doc`, ruff, or lua-language-server; see [Doc linters](#doc-linters-tier-1)) when the project has them. |
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
- **Repo to projects:** a project's copies come from `install.py` and are never edited in the
  project. After changing `instructions/` or `skills/annotate-code/` here, rerun the installer
  in each project that uses them; `python3 install.py --check <project> ...` reports which are
  behind. So a change to a skill travels: Claude account, then this repo (`sync-skills-repo`),
  then projects (`install.py`).
