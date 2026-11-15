---
name: "distill-spec"
description: "Distills a finished working conversation (plus its artifacts, project files and any chats the user names) into a standalone functional spec that a fresh LLM can implement from and a human can read and edit. Use only when the user runs /distill-spec or explicitly asks to turn this conversation into a spec, brief or requirements document. Do not use for writing a spec from scratch with no conversation behind it."
---

# distill-spec

## Why this skill exists

Most of a working conversation is **grounding**: the user and Claude converging on shared understanding (common ground) about what the artifact must be. That understanding ends up scattered across dozens of turns, buried in corrections, reversals and casual asides. This skill compresses it into a **functional spec**: a document that states *what* the result must achieve and *why*, so a fresh implementer can reproduce a result the user would accept without repeating the grounding.

The governing principle is the **default-delta test**: a statement earns its place in the spec only if a capable reader starting cold would plausibly do something different without it. Everything a competent practitioner would do by default is noise that dilutes the requirements that matter. The hard part is that you, the distiller, are the worst judge of what is inferable, because you have seen the whole conversation (the *curse of knowledge*). That is why step 6, the cold-read test, exists.

## Readers

- **Implementer.** A capable Claude-class model in a fresh chat with no history and no access to the source conversation. Assume it can search the web and use tools normal for the domain, unless the conversation says otherwise. Write the spec for this reader.
- **Editor.** The user, who will read, edit and reuse the spec. Keep it skimmable: overview first, IDs on everything, no transcript narration.

## Arguments

Plain words work as well as tokens: `/distill-spec harness` and "distill this, and include the benchmark harness" mean the same thing.

| Argument | Effect |
|---|---|
| `harness` (or "benchmark", "evaluation harness") | Include the evaluation layer: scoring rules, machine-readable results schema, transcript requirements. Off by default. |
| `no-cold-read` | Skip step 6. Say in the delivery message that it was skipped. |
| `update [spec name]` | Revise an existing spec instead of writing a new one. The name is optional if the spec is attached. See "Updating an existing spec". |
| Names of chats or files | Add them to the sources in step 1. |

## Procedure

Work through these steps in order. Keep a task list if the tool exists. Steps 2–4 are working material; the user sees their results in the spec's appendix, not as separate messages.

### 1. Gather the sources

Read everything the spec must account for:

1. **This conversation, all of it.** If early turns have been summarized out of your context, re-read them (for example with the past-chats tool's read on the current chat, or the session transcript file on disk). Where something is truly unreachable, record `[gap: not in context]` in the ledger. Never reconstruct it from memory.
2. **The artifacts.** Read the final version of every file, artifact or document produced or attached in the conversation.
3. **Project knowledge / repo docs.** In a Claude Project, list its knowledge files and read those relevant to the artifact. In a coding repository, check `AGENTS.md` / `CLAUDE.md` and relevant files in `docs/` or `specs/`.
4. **Named chats and files** from the arguments.

Note what you could not read. It becomes an interview question.

### 2. Build the decision ledger

Go through the sources in order and extract every item that bears on the result. Be exhaustive here; filtering comes later. Each entry gets:

- **ID** (L1, L2, …) and a **source**: turn number, file or chat.
- **Kind**:
  - goal or purpose;
  - constraint;
  - measured fact;
  - decision;
  - preference;
  - acceptance criterion;
  - process rule;
  - nongoal;
  - rejected alternative, with the reason it was rejected;
  - rationale;
  - delegated determination ("research X yourself");
  - open issue.
- **The statement**, with units and reference frame exactly as given.

Watch for the items that are easiest to lose:

- facts mentioned in passing early on;
- corrections ("actually…", "no, I meant…");
- numbers and their units;
- anything the user pushed back on. Pushback is the strongest signal that the user's wish differs from the default.

### 3. Tag provenance and resolve supersession

Tag every ledger entry with exactly one provenance:

| Tag | Meaning | Treatment |
|---|---|---|
| `USER` | The user stated or chose it. | Requirement candidate. |
| `ACCEPTED` | Claude proposed it and the user explicitly approved it ("go with B", "yes, do that"). | Requirement candidate. File the choice, not the options that were not picked. |
| `TACIT` | Claude proposed or did it, and the user did not object. | **Not a requirement yet.** It goes to the interview if it would become a MUST. Otherwise drop it, or move it to Latitude. |
| `MEASURED` | A fact about the world the user supplied or measured. | Goes in Given facts, verbatim. |
| `OPEN` | Unresolved, or the sources conflict. | Goes in Open issues. |

The `TACIT` tag guards against the worst failure of this skill: **laundering Claude's priors into the user's requirements.** A suggestion the user merely tolerated is not their decision.

Apply these rules:

- **Supersession.** The latest statement wins. Mark earlier ones superseded. If a superseded idea is likely to be proposed again, keep it as a rejected alternative with its reason.
- **Conflicts.** When two current statements disagree, mark the item `OPEN`. Never write a blended version that satisfies neither.
- **Artifact evidence.** The final artifact shows what the user accepted. It is not a source of requirements on its own. A property found only in the artifact is `TACIT` until the user confirms it. Otherwise you write the existing solution into the requirements, which anchors the implementer and defeats the purpose of a functional spec.

### 4. Apply the default-delta filter

For each current ledger entry, decide whether it stays.

**Keep it if any of these holds:**

- A capable cold reader would plausibly do otherwise, or get it wrong.
- It is a measured quantity or a given fact about the environment, kit or materials. Readers cannot infer facts.
- It is a safety, health, legal or compatibility constraint, even if it seems obvious.
- The user stated it emphatically, corrected Claude about it, or pushed back on it.
- It is something the implementer must *not* use or do, or a resource that is unavailable. The reader cannot know what is missing.

**Drop it if any of these holds:**

- It is what competent practice in the domain does by default.
- It is a free choice where any reasonable option would satisfy the user.
- It is an implementation detail that merely *happened* in this conversation. Before dropping, check: is it a real constraint (the user's tools, existing parts, a fixed interface)? If so, keep it as a constraint.

**Two moves that are neither keep nor drop:**

- **Grant latitude.** If the reader might stall on a free choice, or ask about it, list it under Latitude ("your choice; justify it"). This is cheaper than specifying it.
- **Convert many whats into one why.** If several kept items share a reason, state the reason once as rationale. Rationale lets the implementer handle the cases you did not list, and decide conflicts the way the user would.

**When unsure:** keep facts and constraints; drop style and implementation detail. The cold-read test in step 6 will catch what you dropped wrongly.

### 5. Draft the spec

Write the spec using the template below. Follow these writing rules; each one prevents a known failure:

- **One requirement per bullet,** each with an ID (`AREA-n`), using MUST / SHOULD / MAY in their RFC 2119 senses. Bundled requirements get half-implemented.
- **Every quantity has a unit and a basis.** State the reference frame and origin for positions. Give a tolerance or range where the real requirement is a range.
- **No unanchored words.** Avoid pronouns with unclear antecedents ("those", "it"), unquantified adjectives ("large", "vibrant", "near"), and rules without a formula. Replace them, or define them.
- **Make it verifiable.** Every MUST that can be checked says how it is checked, or points to the Verification section.
- **Label examples.** Write "example, not a requirement". Readers otherwise copy examples as if they were binding.
- **Mark volatile facts.** Put "(as of YYYY-MM-DD; re-verify)" on versions, prices, products and research claims. Measured facts are labelled measured.
- **Phrase delegated determinations as tasks.** For example: "Determine X, cite sources, and check it against Y."
- **Front-load.** Put the purpose, the priority order and the hardest constraints near the top. Long documents lose their middle.
- **Keep the layers separate.**
  1. Product requirements: always included.
  2. Interaction protocol (how the implementer should work with the user): include it only if the conversation established one.
  3. Evaluation harness: include it only on request.
- **Include personal details only when they change the work.** For example, the user's skill level, tools or role. Leave out other people's details unless the artifact needs them.
- **Make it as short as completeness allows.** If a sentence restates what any competent implementer would do, cut it.

### 6. Cold-read test

Give the draft spec, and only the spec, to a fresh agent: a general-purpose subagent with no conversation, no ledger and no files. The user's invocation of this skill authorizes spawning it. In coding workspaces where subagents inherit file-reading tools, explicitly forbid reading the workspace so existing code or transcripts cannot mask missing requirements. Use this prompt:

> You are about to implement the spec below. Do not implement it, and **do not read, search, or inspect any workspace files, git history, or transcripts**—rely solely on the spec text provided here. Report:
> (1) every point where you would have to guess, with the guess you would make;
> (2) every term, quantity or instruction you find ambiguous, quoted;
> (3) any requirements that conflict;
> (4) any MUST you could not verify;
> (5) a five-line summary of what you would build.
> Be specific and terse.

Then compare the report against the ledger:

- **A guess that matches the ledger** means dropping that item was correct. Leave it out.
- **A guess that contradicts the ledger** means a requirement is missing. Add it.
- **A guess on a genuinely free choice that made the reader hesitate:** add it to Latitude.
- **An ambiguity:** rewrite the wording.
- **A summary that misses the point:** the purpose or overview section is defective. Fix it first.

If no subagent tool is available, give the user the prompt and the spec, and ask them to paste both into a fresh chat and return the reply.

### 7. Interview the user, once

Ask a single round of at most 7 questions, merged from three sources:

- `TACIT` items that would become MUSTs;
- `OPEN` items and conflicts;
- defects from the cold read that only the user can resolve.

Also ask about anything unreachable, and whether anything changed outside the chat (edits to files, decisions made offline).

Each question offers 2–4 options and a recommended default, e.g. "(a) … (b) … [default] (c) …". Give a fill-in reply template, then **stop and wait** for the user's reply before step 8. If the user says to take defaults or leaves individual questions blank in their reply, take the defaults and list them in the delivery message.

### 8. Revise and deliver

1. **Apply the answers.** Re-check the spec against the writing rules in step 5.
2. **Write the file.** Save it as `docs/SPEC-<short-slug>.md` when working in a repository that has a `docs/` directory, or `SPEC-<short-slug>.md` otherwise. Use a short, lowercase, hyphenated slug for the artifact (e.g. `SPEC-smaug-lid.md`). Set the high-water mark on the **Distilled from** line to the last turn you read.
3. **Send or link the file.**
4. **Write the reply.** Keep it to a few lines, and don't paste the spec into the chat. Cover:
   - the requirement count, broken down by MUST, SHOULD and MAY;
   - the defaults you took;
   - the open issues that remain;
   - what the cold read changed, or that it was skipped.
5. **Offer to save it to project knowledge** (if the chat is in a Claude Project) or commit it (if in a git repository), in one line.

## Template

Omit any section that would be empty. Keep the section order, so the user's specs stay comparable.

```markdown
# <Artifact name>: Functional spec (draft <n>)

<One paragraph: what is being made, for whom, and what it is for.>

**Status:** <Draft: open issues remain | Complete to the best of the author's knowledge; report omissions.>
**Owner:** <user> · **Date:** <YYYY-MM-DD>
**Distilled from:** <project › chat name, through turn N; other chats; files>   <!-- high-water mark; see below -->

**How to read this spec**
- Must / should / may: RFC 2119 senses.
- Requirement IDs: cite them in your work so it can be checked against this spec.
- Units: <conventions>.
- Priorities: when requirements conflict, decide in this order: <…>.
- Working with the user: <only if established, e.g. their skill level and how to explain choices>.

## 0. How to work            <!-- interaction protocol; omit if none established -->
## 1. Purpose and scenarios   <!-- the why; rationale that governs unstated cases -->
## 2. Given facts             <!-- measured values, environment, kit on hand, what is NOT available -->
## 3. Requirements            <!-- grouped by area, one ID per bullet -->
## 4. Latitude                <!-- choices deliberately left to the implementer -->
## 5. Nongoals and rejected alternatives   <!-- each with a one-line reason -->
## 6. Verification            <!-- how each checkable MUST is checked; acceptance criteria -->
## 7. Deliverables            <!-- files, formats, names, destination -->
## 8. Open issues             <!-- each with options and a recommended default -->

## Appendix A. Evaluation harness    <!-- only with the harness argument -->
## Appendix B. Decision ledger       <!-- condensed: requirement ID, source, provenance -->

## Revision history
| Draft | Date | Changes |
```

The "through turn N" on the **Distilled from** line is a **high-water mark**: the last source turn this draft covers. Count turns as user messages, so turn N is the Nth user message in that chat; quote its first few words too, because counts can drift. The next update treats only material after the mark as new. Record a mark for every chat the draft drew on.

### Appendix A (when `harness` is requested)

Include `Appendix A. Evaluation harness` only when the user passes `harness` (or asks for a benchmark/evaluation spec). Specify four parts:
1. **Execution environment & inputs:** allowed tools, network/closed-book rules, time/step budget, and fixture paths.
2. **Scoring rubric:** a deterministic check for every verifiable MUST (pass/fail gate) and weighted points for SHOULD items, keyed by requirement ID (`AREA-n`). Any failed MUST fails the run overall, while still reporting partial scores.
3. **Machine-readable results schema:** a JSON object written to `eval-results.json` (or fenced at the end of the run) containing `spec_id`, `spec_draft`, `overall_pass` (boolean), `must_passed`, `must_total`, `should_score`, `checks` (array of `{id, level, passed, evidence}`), and `notes`.
4. **Transcript & artifact capture:** what files, command outputs, renders, or logs the evaluator requires to audit each `evidence` claim without re-running the build.

### Domain checklists

Use these to find gaps in the ledger, not as sections to fill. Include a line only if it passes the default-delta test.

- **Physical / fabrication:** coordinate frame and origin; units; tolerances; materials; tools on hand and tools *not* available; loads and margins; environment (heat, moisture); safety; moving-part states; what the builder marks from real hardware rather than from the model.
- **Software:** interfaces and data formats; platforms and versions; error and edge cases; performance limits; security and privacy; what existing code must not change.
- **Visual / document:** audience; medium and dimensions; destination; tone; brand constraints; length; required content; accessibility.
- **Research / analysis:** the decision it feeds; the scope; source quality and recency requirements; how confidence is reported.

## Updating an existing spec

A spec is living: revise it rather than rewriting it.

**Find the baseline,** meaning the current approved draft, in this order:

1. A spec attached or named by path in this chat.
2. A matching file in the repository (`docs/SPEC-*.md` or `SPEC-*.md`) or Claude Project knowledge, or, failing that, the only `SPEC-*.md` file there.
3. Ask the user to attach or name it.

Never reconstruct a baseline from memory or from a past chat's text. Files sent in other chats are not readable from here.

**Decide what is new.** Read the baseline's **Distilled from** line:

- If its high-water mark points at this chat, only the turns after the mark are new.
- Otherwise, all of this chat is new.

Run steps 1–4 on the new material only.

**Treat the baseline as `USER`.** The user may have edited the spec by hand since it was distilled; their edits are decisions. Change a baseline line only when the new material contradicts it or adds to it. List every such change in the revision history. Never revert wording toward an older conversation.

Then run steps 5–8 as usual, with the cold read on the whole revised spec, and follow these rules:

- Never renumber requirement IDs. Retire an obsolete ID by marking it "(retired in draft n)". Never reuse it.
- Bump the draft number, and add a revision-history row that names what changed. Note explicitly when no requirement changed.

## Failure modes to check before delivering

- **Omission.** Walk the ledger once more. Every kept entry maps to a spec line, and every spec line maps back to a ledger entry.
- **Invented requirement.** A spec line with no ledger source.
- **Laundered prior.** A `TACIT` item written as a MUST without the user's confirmation.
- **Stale content.** A superseded value that survived.
- **Averaging.** Conflicting statements blended into vague wording.
- **Implementation bias.** The spec describes the existing solution rather than the need.
- **Transcript creep.** Narrative of how the conversation went. The spec states outcomes, not history.
