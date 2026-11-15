# dexiotites

Reusable artifacts from the *LLM learnings* project: instructions and portable skills to install
into coding projects, plus mirrors of the personal Claude workflow skills built along the way.

| Path | Contents |
|---|---|
| `instructions/COMMENTING.md` | Commenting standard for AI coding agents: purpose-first comments, sourced rationale, comment-only retrofits. Ends with exemplar codebases and references. |
| `instructions/AGENTS-commenting-section.md` | Short block to append to a project's `AGENTS.md` so every agent session loads the core rules. |
| `skills/` | One folder per skill (see [Skills](#skills)). |
| `tests/` | Unit tests for embedded helper scripts (run `python3 -m unittest discover -s tests`). |
| `docs/` | Reserved for specs and design notes. |

**Prompting guide:** the living guide to working with LLMs is a Google Doc,
[Prompting Guide: Working with Claude](https://docs.google.com/document/d/1RlEDKMVg3FysnslHnX-OeYwoRcQ_tGh_FbuuCB_UjD8/edit)
(also holds the paste-ready `<prompt_coaching>` standing instructions tab; snapshot a copy into
`instructions/` if you want local offline agents to read it directly). The `prompt-lint` and
`prompt-guide-update` skills read and update it.

---

## Commenting standard

The standard has three parts:
1. `COMMENTING.md`: the full rules and examples, copied into the project.
2. A short section in `AGENTS.md`: always loaded, so new code gets commented as it is written.
3. The `annotate-code` skill: retrofits comments into existing code, changing comments only.

How each agent finds them:
- **Antigravity** reads `AGENTS.md` and discovers skills in `.agents/skills/` (or via
  `.agents/skills.json` / global `~/.gemini/config/skills.json`).
- **Claude Code** reads `CLAUDE.md`, not `AGENTS.md`. A `@AGENTS.md` line at the top of
  `CLAUDE.md` imports it. Claude Code skills live in `.claude/skills/`; symlinking to
  `.agents/skills/` lets one copy serve both agents.

### (a) Setting up a project (safe for new or existing repos)

From the target project's root (`$DEX` is your clone of this repo):

```bash
DEX=~/programming/dexiotites.git

mkdir -p docs .agents/skills .claude/skills
cp "$DEX/instructions/COMMENTING.md" docs/
[ -s AGENTS.md ] && printf '\n' >> AGENTS.md
cat "$DEX/instructions/AGENTS-commenting-section.md" >> AGENTS.md
if [ ! -f CLAUDE.md ]; then
  echo '@AGENTS.md' > CLAUDE.md
elif ! grep -q '@AGENTS.md' CLAUDE.md; then
  printf '@AGENTS.md\n\n%s\n' "$(cat CLAUDE.md)" > CLAUDE.md
fi
cp -r "$DEX/skills/annotate-code" .agents/skills/
ln -sfn ../../.agents/skills/annotate-code .claude/skills/annotate-code
```

Commit these files (check that the appended heading in `AGENTS.md` fits any existing section
numbering). From then on, agents comment new code as they write it. For personal projects on
your own machine, Antigravity can also load `annotate-code` and `distill-spec` globally via
`~/.gemini/config/skills.json` without copying `skills/annotate-code` into each repo.

### (b) Retrofitting existing code

1. Commit or stash any work in progress. The checker compares files against `HEAD` and refuses
   to start if target files are untracked or have uncommitted code changes.
2. Run the skill on a small scope first, one file or one package (see below).
3. Review the diff. Read the summary for anything marked `RATIONALE-UNKNOWN` (questions only you
   can answer) and for suspected bugs, which the skill reports but never fixes.
4. Build the project, then commit.

### Running annotate-code

| Where | How |
|---|---|
| Claude Code (project install) | `/annotate-code path/to/File.kt`, or ask: "annotate `src/tracking/` per COMMENTING.md". |
| Antigravity (project or global install) | Ask in plain language ("annotate `src/tracking/` per COMMENTING.md"). The agent activates the skill from its description. |
| Claude desktop app (account skill) | Connect the project folder, then `/annotate-code <path>` or ask. The account version writes its embedded checker to a temporary file. |
| By hand | `python3 .agents/skills/annotate-code/scripts/comment_diff_check.py --strict <files>` from the project root. With `--strict`, exit code 0 guarantees every named file is a supported type (`.kt`, `.kts`, `.rs`, `.py`), has a `HEAD` baseline, and changed comments only. Without `--strict`, unsupported (`SKIP`) and untracked (`NEW`) files are reported without failing whole-repo `git diff` scans. |

---

## Skills

### Portable / project skills

Reusable across coding repositories and agent harnesses (Antigravity, Claude Code, Claude Desktop):

| Skill | What it does |
|---|---|
| `annotate-code` | Comment-only retrofit of existing code to `COMMENTING.md`, verified by `scripts/comment_diff_check.py`. |
| `distill-spec` | Distills a finished working conversation into a standalone RFC-2119 functional spec (with cold-read subagent check and optional evaluation harness). |

### Personal workflow & maintenance skills

Tailored to Jim's Claude Desktop setup, Google Doc prompting guide, and this repository:

| Skill | What it does | External requirements |
|---|---|---|
| `prompt-lint` | Checks a draft prompt against the prompting guide's checklist, routes model tier + effort, and returns a tightened version. | Google Drive connector (optional; falls back to embedded checklist). |
| `prompt-guide-update` | Folds new prompt feedback from recent chats into the prompting guide Google Doc and syncs the coaching block. | Google Drive & Google Docs connectors; `google-workspace` skill (`docs_index.py`). |
| `sync-skills-repo` | Syncs the Claude account versions of these skills into this repo with git conflict detection, extracts embedded helper scripts, commits, and pushes. | Access to `~/.claude/skills/synced/` and push access to `daemacles/dexiotites`. |

### Keeping the copies current

- **Account vs. repo ownership:** `instructions/` and `tests/` are mastered directly in this git
  repo. For `skills/`, the account copies in the Claude app are the primary source, synced here
  by `sync-skills-repo` (which stops and offers a merge if `skills/<name>` has git commits newer
  than the last sync commit).
- **Embedded files:** a skill can carry a helper file inside its `SKILL.md` as a fenced block
  preceded by `<!-- embedded-file: <path> -->`. `sync-skills-repo` extracts each block to
  `skills/<name>/<path>` (preserving `+x` on `#!` scripts). For `annotate-code`, **always edit
  the checker in `skills/annotate-code/SKILL.md` and `scripts/comment_diff_check.py` together**,
  and verify with `python3 -m unittest discover -s tests`.
- **New skills:** add each new account skill here by running `sync-skills-repo`.
