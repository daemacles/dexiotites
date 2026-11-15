# Maintenance & Authoring Checklist (`dexiotites`)

This checklist guards against semantic and cross-agent regressions that lower-tier models
commonly miss. Mechanical invariants (embedded-file byte parity, `#!` executable bits, valid
`SKILL.md` frontmatter, `README.md` skill-table coverage, trailing newlines, and clean skill
folders with no `__pycache__`) are enforced automatically by `tests/test_repo_hygiene.py`.

**Required gate on every edit:**
1. Read and check every section below that matches what you touched.
2. Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` and fix any failure
   before committing or finishing.

---

## 1. Editing or adding a `SKILL.md`

- **Plain-language activation (`description:`):** State *what* the skill does and *when* to use
  it in third person without assuming slash commands (`/foo`) are the only trigger.
  *(Prevents silent non-activation in description-routed agents like Antigravity.)*
- **Step 0 vs. Step N dependency audit:** List every MCP connector, CLI binary, and external
  skill called anywhere in Steps 1..N. Verify each one is checked in Step 0 / Preconditions
  (for example, **both** Google Drive and Google Docs if both are called) and listed in
  `README.md`'s external-requirements column.
- **Advertisement parity:** Every flag/argument in the Arguments table and every section heading
  in the Template must have concrete rules in the body.
  *(Prevents hollow options like advertising an evaluation harness with an undefined appendix.)*
- **Explicit interactive pauses:** Whenever a step asks the user questions that a later step acts
  on, write **"stop and wait for the user's reply"** at the end of that step.
  *(Prevents lower-tier models from assuming defaults and completing both steps in a single turn.)*
- **Zero-context subagent isolation:** Whenever a step spawns a "fresh" or "cold-read" subagent,
  explicitly forbid reading workspace files, git history, and transcripts inside the subagent
  prompt.
  *(Coding-agent subagents in Antigravity and Claude Code inherit file/search tools by default.)*
- **Workspace vs. Claude Project storage:** In portable skills (`annotate-code`, `distill-spec`,
  and future repo-usable skills), pair every mention of "Project knowledge" or "attached files"
  with its git-workspace equivalent (`docs/`, `specs/`, `AGENTS.md`).
- **Coupled state across skills:** If Skill A updates data that Skill B embeds as a fallback
  snapshot (e.g., `prompt-guide-update` Section 1 vs. `prompt-lint`'s fallback checklist), add a
  reminder at Skill A's verification/reply step naming Skill B's file.

## 2. Editing standards or examples (`instructions/`)

- **Rule ↔ example cross-check:** Re-read every worked example in the file against every rule you
  added or changed in the same edit.
  *(Prevents contradictions such as mandating `@property` in rules while using `@param` in the example.)*
- **Anti-boilerplate & inheritance clauses:** Whenever requiring multi-part doc comments (side
  effects, errors, calling contract), state *"omit when pure, infallible, and unrestricted"* so
  literal models do not emit `"Side effects: none"` noise, and specify behavior for `override` /
  trait implementations and unit test files.

## 3. Editing setup snippets (`README.md`)

- **Idempotency:** Every shell block must be safe to run twice in an already-populated repo.
  Never use bare `> CLAUDE.md` or `> AGENTS.md` without checking `[ ! -f ... ]`, and always insert
  a blank line (`[ -s FILE ] && printf '\n' >> FILE`) before `>>` appending Markdown headings.

## 4. Editing parsers, lexers, or verification scripts

- **Mandatory regression tests in `tests/`:** Cover all four failure classes before trusting a
  code/comment scanner:
  1. Wrapping single-line calls or constructors across lines (around `(`, `)`, `,`) to attach
     per-parameter comments.
  2. Interpolated strings containing nested quotes and `//` URLs (`"${f("https://...")}"`).
  3. Language-specific raw strings (`"""`, `$$"..."`, `r#""#`, `br#""#`, `cr#""#`) and char escapes
     (`'\\'`, `'\''`, `'\u0027'`).
  4. Exit codes and agent instructions when a target file is untracked (`NEW`) or an unsupported
     language (`SKIP`).

## 5. Evolving this file

- **Graduate to code first:** If a new miss can be checked mechanically in Python, add an
  assertion to `tests/test_repo_hygiene.py` instead of lengthening this file.
- **Format for new bullets:** Place under the matching trigger heading as
  `- **Short name:** concrete check to perform. *(One-line failure mode it prevents.)*`
  Keep total length under ~100 lines so smaller models read every line.
