# dexiotites

Reusable artifacts from the *LLM learnings* project: instructions and portable skills to install
into coding projects, plus mirrors of the personal Claude workflow skills built along the way.

| Path | Contents |
|---|---|
| `install.py` | Installs or updates the commenting standard in a project with one command. See [Install or update](#install-or-update-one-command). |
| `instructions/COMMENTING.md` | Commenting standard for AI coding agents: purpose-first comments, sourced rationale, comment-only retrofits. Ends with exemplar codebases and references. |
| `instructions/rules/` | Rule files the installer copies into a project's `.agents/rules/`: the pointer to `PROJECT_INSTRUCTIONS.md`, and the opt-in personal defaults. |
| `instructions/AGENTS-commenting-section.md` | Short section the installer places in a project's `AGENTS.md` so every agent session loads the core rules. |
| `instructions/lint/` | Doc-linter configs that enforce the mechanical part of the standard (Kotlin, Rust, Python, Lua). See [Doc linters](#doc-linters-tier-1). |
| `skills/` | One folder per skill (see [Skills](#skills)). |
| `MAINTENANCE.md` | Authoring and review checklist for updating skills, instructions, and verifiers (especially with smaller models). |
| `tests/` | Unit and repository-hygiene tests (run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`). |
| `docs/` | Reserved for specs and design notes. |

Adding a language or an agent harness: see [Extending to a new language or harness](#extending-to-a-new-language-or-harness).
Released under the [MIT License](LICENSE).

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
python3 /path/to/dexiotites/install.py                             # the project in the current directory
python3 /path/to/dexiotites/install.py ~/projects/a ~/projects/b   # or several at once
```

With no clone at hand, this fetches one into a temporary folder and runs it:

```bash
curl -fsSL https://raw.githubusercontent.com/daemacles/dexiotites/main/install.py | python3 -
```

Nothing else is needed. Everything is installed as plain files inside the project and
committed, so fresh clones, CI and cloud agent sessions get it with no extra step. Requires
Python 3.9+ and git.

**The commit.** The installer commits the paths in the table below to the current branch, with
the message `dexiotites installed to remote @ 83665a` (or `updated`; the hash is the first six
characters of the dexiotites commit installed). The commit holds the installer's changes and
nothing else:
- Files you have modified, staged or left untracked are not included and stay as they were.
- Where it edits a file of yours (`AGENTS.md`, `CLAUDE.md`, `Cargo.toml`), it commits its edit
  applied to the last committed version of that file. Uncommitted work of your own in the same
  file stays uncommitted.
- A `Cargo.toml` that has never been committed is edited but not committed; the installer
  says so.

Pass `--dont-add` to install without committing. A later plain run commits what is in place.

| Installed in the project | Purpose |
|---|---|
| `docs/COMMENTING.md` | The full standard. |
| `.agents/skills/annotate-code/` | The retrofit skill and its checker (Antigravity reads it here). |
| `.claude/skills/annotate-code` | Symlink to the folder above, for Claude Code. |
| `AGENTS.md` | The always-loaded core rules, between `<!-- dexiotites:begin … -->` and `<!-- dexiotites:end -->`. Your own heading line (for example `## 6. Code Comments …`) is kept. |
| `PROJECT_INSTRUCTIONS.md` | Starts empty. Put this project's own instructions for agents here. The installer creates it once and never changes it again. |
| `.agents/rules/project-instructions.md` | Tells agents to read the file above. Antigravity loads every file in `.agents/rules/` by itself. |
| `CLAUDE.md` | Gets import lines for `AGENTS.md` and `PROJECT_INSTRUCTIONS.md` if it lacks them, so Claude Code loads both. |
| Doc-linter config | For each language found; see [Doc linters](#doc-linters-tier-1). |
| `.dexiotites.json` | Manifest: the dexiotites commit installed, options, and a hash of each copied file. Commit it. |

**Options**

| Option | Effect |
|---|---|
| `--check` | Writes nothing. Exit code 0 if the project is current and committed, 1 if it is out of date, has conflicts, or has installed files that are not committed. |
| `--dont-add` | Install or update the files, but do not `git add` or commit them. |
| `--skill NAME` | Also install another skill from `skills/` (for example `--skill distill-spec`). Remembered for later runs. |
| `--with-jim` | Also install the maintainer's personal defaults for working with an agent (`instructions/rules/jim-defaults.md`): teach terms of art, show a plan first, coach the prompt. Remembered. Leave it off unless you are Jim or want the same. |
| `--no-lint` / `--lint` | Leave out (and remove) the doc-linter configs, or turn them back on. Remembered. |
| `--force` | Replace conflicting files. Local edits in them are lost. |

**Conflicts.** The installer only replaces content it can prove came from dexiotites: files
unchanged since the last install, files identical to any version this repo has shipped (so
older hand-made installs upgrade cleanly), and the marked block in `AGENTS.md`. If anything
else is in the way (a copy edited in the project, or an unrelated file with the same name), it
lists the conflicts, **writes nothing**, and exits with code 1. `--force` replaces the
conflicting files, and whatever was edited into them is lost, so first copy out anything worth
keeping. Agents: on exit code 1, stop and show the user the conflict list; do not add `--force`
on your own.

Exit code 2 means the files were installed but git refused the commit (no identity configured,
or a commit hook failed). Fix the cause and rerun; nothing is installed twice.

**Do not edit the installed copies in a project.** Rules for one project only go in that
project's `PROJECT_INSTRUCTIONS.md`. Rules for every project go in the masters in
this repo; then rerun the installer in each project. `--check` in a project tells you whether
it is behind.

**After a first install in a project that already has code,** expect the doc-linter gate to
fail on the existing files. That is the linter doing its job, not a broken install: clear it
file by file with the `annotate-code` skill ([Retrofitting existing code](#retrofitting-existing-code)).

**As a git submodule (optional, not recommended).** The installer also runs from a submodule:
`git submodule add https://github.com/daemacles/dexiotites .dexiotites && python3 .dexiotites/install.py`,
and later `git submodule update --remote .dexiotites && python3 .dexiotites/install.py`. The
installer does not commit the submodule itself (`.gitmodules` and the `.dexiotites` entry); do
that yourself. The installed files are still plain copies, so clones that never fetch the submodule keep working.
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
| Rust | The tables from `instructions/lint/rust-cargo-lints.toml`, appended to the root `Cargo.toml` in a marked block. | A `Cargo.toml` that already has `[lints]` tables, or is a workspace root (see the config's header). | `cargo clippy --all-targets -- -D missing_docs` and `RUSTDOCFLAGS="-D warnings" cargo doc --no-deps` |
| Python | `instructions/lint/ruff-docstrings.toml` as `ruff.toml`. | Any existing ruff config: merge the tables by hand (in `pyproject.toml`, prefix them with `tool.ruff.`). | `ruff check --select D .` |
| Lua | `instructions/lint/luarc-docs.json` as `.luarc.json`. | An existing `.luarc.json`: merge the two `diagnostics.*` objects into it. | `lua-language-server --check=. --checklevel=Warning --configpath=.luarc.json` |
| Kotlin | `instructions/lint/detekt-comments.yml` as `config/detekt/detekt-comments.yml`. | The Gradle plugin block below. | `./gradlew detekt` |

Clippy checks presence and `# Errors`/`# Panics`/`# Safety`/`SAFETY:`; rustdoc checks `[links]`.
The Rust gate denies only the documentation lints, so clippy's style warnings never block it.
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

## Extending to a new language or harness

Both kinds of extension work the same way: add the new thing in a short list of known places,
then let the test suite name whatever was left out. The list is the same whether an agent or a
person makes the edits. What differs is who has to bring the knowledge the repo cannot hold,
so the two workflows are described separately below.

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` after each row.

### What a new language touches

| # | Where | What to add | What checks it |
|---|---|---|---|
| 1 | `instructions/COMMENTING.md` §6 | A subsection for the language: doc-comment syntax, how parameters, return values and failures are written, the file-header form, known pitfalls. | Review only. This is the judgment part. |
| 2 | `skills/annotate-code/scripts/comment_diff_check.py` | A function that strips comments from the language's source, wired into `code_only` under the new file suffix. Write the tests first: `MAINTENANCE.md` §4 lists the lexer failure classes to cover. | `tests/test_comment_diff_check.py` |
| 3 | `skills/annotate-code/SKILL.md` | Replace the fenced block under `<!-- embedded-file: scripts/comment_diff_check.py -->` with the script's new contents, and add the suffix where the skill lists supported types. | Hygiene tests: byte parity, and `test_checker_languages_are_documented_everywhere` (add the new suffix set to its `supported`) |
| 4 | `instructions/lint/` | A doc-linter config that enforces documentation rules only, with a header saying what it matches in the guide. | `tests/test_lint_configs.py` |
| 5 | `tests/fixtures/lint/<language>/good` and `bad` | A compliant and a non-compliant sample project, plus a test in `tests/test_lint_configs.py` that runs the gate on both. The bad one should break each rule the config enforces. | The test itself; `tests/mutation_audit.py` |
| 6 | `instructions/COMMENTING.md` §8 | A table row: tool, config name, finish-gate command. The tests run this exact command. | `test_finish_gate_commands_agree_everywhere` (add the language to its list) |
| 7 | `install.py` | One `LintConfig` entry in `LINT_CONFIGS`: suffixes, config name, where it is installed, and which file names mean a project already has its own config. | `tests/test_install.py` (copy `test_python_and_kotlin_configs`) |
| 8 | `README.md` | The language and suffix wherever supported ones are listed, and a row in the [Doc linters](#doc-linters-tier-1) table. | Hygiene tests |

- A language with no usable doc linter can stop after row 3: the guide and the retrofit skill
  work without Tier 1.
- A linter configured inside a file the project owns (as Rust's is, in `Cargo.toml`) cannot be a
  `LintConfig` entry. It needs a planner that maintains a marked block; copy `plan_cargo_lints`.
- Rows 2 and 3 change a skill. The maintainer's Claude account holds the primary copy of each
  skill, so after a contribution lands, `sync-skills-repo` reports that skill as `repo-ahead` and
  the maintainer merges it into the account. Contributors only edit the repo.

### What a new harness touches

A harness is the program that runs the agent (Claude Code, Antigravity, and so on). The
installer puts the real content in `AGENTS.md` and `.agents/skills/<name>/`. A harness that
reads both by itself needs no code at all. For any other, first establish four facts **from the
harness's current documentation** (these change often, and a model's recollection of them is
frequently out of date):

1. Which file does it load into every session, and does it read `AGENTS.md` itself?
2. If not, can its always-loaded file import another file, and with what syntax?
3. Where does it discover skills (folders containing a `SKILL.md`)? Does it read `.agents/skills/`?
4. Does it follow symlinks in that folder?

| Where | What to add | What checks it |
|---|---|---|
| `install.py` | One `Harness` entry in `HARNESSES`: the always-loaded file, the import format (leave it empty and the file becomes a symlink to `AGENTS.md`), and the skills folder (each skill is symlinked into it). | `tests/test_install.py` (copy `test_one_harness_entry_supports_a_new_harness`) |
| `README.md` | The harness under "How each agent finds them", the files it adds to the installed-files table, and a row in [Running annotate-code](#running-annotate-code). | Hygiene test (every `HARNESSES` name appears) |
| `skills/*/SKILL.md` | Nothing, usually. Re-read `MAINTENANCE.md` §1 with the new harness in mind: skills must activate from their description alone, and must not assume tools only one harness has. | Review only |

If the harness has no skills mechanism or does not follow symlinks, skip the skills folder. The
`AGENTS.md` section names the skill's path, so an agent can still read
`.agents/skills/annotate-code/SKILL.md` as an ordinary file and follow it.

### (a) Having an agent do the work

The repo already steers an agent: `AGENTS.md` sends it to `MAINTENANCE.md` and the test gate, and
the tables above are its checklist. Your part is the knowledge it cannot get from the repo, and
the review of what no test can judge. Paste one of these, filled in:

```text
Add <language> support to dexiotites. Follow README.md, "Extending to a new language or
harness", row by row, on a new branch.
- Doc-comment convention to follow: <link to the language's official documentation guide>
- Doc linter: <tool and version>. It must be limited to documentation rules; stop and tell
  me if it cannot be.
- What counts as public API in this language: <for example: exported identifiers>
- Traps for the comment-only checker: <nested comments? raw strings? line breaks that end
  statements? operators that look like comment markers?>
- Exemplar project for the guide's table: <a well-commented open-source project>
Run the tests after each row and finish with `python3 tests/mutation_audit.py`.
```

```text
Add support for the <harness> agent harness to dexiotites. Follow README.md, "Extending to a
new language or harness".
Facts, from <documentation link>, checked on <date>:
- Always-loaded file: <name>. Reads AGENTS.md itself: <yes/no>
- Import syntax in that file: <syntax, or "none">
- Skills folder: <path>. Reads .agents/skills/ itself: <yes/no>
- Follows symlinks there: <yes/no/unknown>
If any fact is "unknown", stop and tell me what to test by hand before writing code.
```

Then review, in this order:
1. The new §6 subsection against the convention you linked: is it the language's real practice?
2. The bad fixture: does it break every rule the config enforces, and does the gate report each one?
3. `python3 tests/mutation_audit.py`: no survivors.
4. `python3 install.py --check <a real project in that language or harness>`: the plan it prints
   is what you expect, and nothing of the project's own would be replaced.

### (b) Doing the work by hand

Same tables, same order. The practical differences:

- **Start from the fixtures** (row 5 before row 4): write the good and bad sample projects, then
  tune the linter config until the gate passes one and fails the other. It is the fastest way
  to learn what the linter can enforce.
- **Edit the checker as a normal Python file**, with its tests open, then paste the finished
  file over the embedded block in `SKILL.md`. The hygiene test fails until the two match byte
  for byte.
- **Python you add follows this repo's own standard** (`instructions/COMMENTING.md`); the gate is
  `ruff check --select D .`, and the test suite runs it when ruff is installed.
- **Finish with** `python3 tests/mutation_audit.py`, and add a mutation for each new rule you
  made the tests enforce, so a later edit cannot quietly undo it.

---

## Skills

### Portable / project skills

Reusable across coding repositories and agent harnesses (Antigravity, Claude Code, Claude Desktop):

| Skill | What it does | External requirements |
|---|---|---|
| `annotate-code` | Comment-only retrofit of existing code (Kotlin, Rust, Python, Lua) to `COMMENTING.md`, verified by `scripts/comment_diff_check.py` and the project's doc linter, then checked against the guide's voice rules with `scripts/comment_load.py` and a read-through. | The project's `COMMENTING.md`; git, with target files committed (the checker compares against `HEAD`); Python 3.9+. The project's build command and doc linter (detekt, `cargo clippy`/`cargo doc`, ruff, or lua-language-server; see [Doc linters](#doc-linters-tier-1)) when the project has them. |
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
- **Contributions to a skill:** edit the copy in this repo. The next `sync-skills-repo` run
  reports it as `repo-ahead`, and the maintainer merges it into the account copy.
- **Repo to projects:** a project's copies come from `install.py` and are never edited in the
  project. After changing `instructions/` or `skills/annotate-code/` here, rerun the installer
  in each project that uses them; `python3 install.py --check <project> ...` reports which are
  behind. So a change to a skill travels: Claude account, then this repo (`sync-skills-repo`),
  then projects (`install.py`).

---

## License

[MIT](LICENSE). Files the installer copies into a project (the guide, the skill and its
checker, the linter configs) are covered by the same license; `.dexiotites.json` in the project
records the repository they came from.
