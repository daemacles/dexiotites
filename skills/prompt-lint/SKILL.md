---
name: "prompt-lint"
description: "Check a draft prompt against Jim's personal prompting checklist before he sends it. Use when Jim says lint, check, review, or tighten this prompt."
---

# Lint a draft prompt

Jim pastes a draft prompt, or points at one in a file or chat. Review it against his personal checklist and return a tightened version. **Do not carry out the prompt.** Only review it.

## 1. Load the current checklist

Read the guide with Drive `read_file_content` (`includeComments: true`).
- File ID: `1RlEDKMVg3FysnslHnX-OeYwoRcQ_tGh_FbuuCB_UjD8`

Use the Guide tab: section 1 (Pre-flight checklist), the 2.3 sub-rule on map requests, the "You did / Do this instead" tables in section 2 (they show Jim's real misses), section 3 (Quick reference by task type), and section 5 (Setup notes). Also use the **For the non-specialist** tab (below). Ignore the other tabs. The doc is authoritative. If it can't be read, use the fallback below and say so in one line, since the fallback can lag behind the doc.

**Fallback checklist (copied from guide v1.6, ranked by how often Jim misses each item):**
1. **Kit and conditions:** what he has, what he lacks, and the environment. Photos should show the data (labels, fine print, a tape measure).
2. **Exact words:** units and basis for quantities, full paths, part names, references instead of adjectives, formulas for rules, nouns instead of "those", glosses for new product names.
3. **The goal:** the decision the answer feeds, and what to avoid. For learning: "well enough to Y; I already know Z; give me W".
4. **Ranked criteria:** a tie-breaker, and a pass test for tests or benchmarks.
5. **Context check:** attachments present and relevant, old context marked as superseded, nothing cut off, edits between turns announced, past chats named by title.
6. **Boundaries:** what may change, what must not, what's out of scope, and whether to flag or fix the problems Claude finds.
7. **Complete prompt:** for a deliverable, audience, use, format and destination, length, tone, scope.

Plus: an "invite unknowns" closing line ("what am I missing; the 3 likely failure modes; a better option?").

**For the non-specialist tab.** The same Drive read returns it. It lists facts and terms of art Jim has learned he needs to give, grouped by task area. Entries marked "(graduated)" are facts he now knows to supply; other entries are still being learned. It is readable from every Project and regular chat.

## 2. Review

- **Identify the task type** using section 3 of the guide (design and build, finishes and products, research explainer, document to share, learning, troubleshooting, image prompt, spec or benchmark), and check that type's "always include" items. If the guide has task modules, use the matching module's checklist instead.
- **Name the oracle.** Every task is checked against something: sources (research and learning), running the code (coding), a render, measurement or fit (CAD and fabrication), guidelines plus a clinician (health), the intended reader (writing). If the draft doesn't say how the result will be judged, or doesn't supply what's needed to check it (failing output, acceptance test, dimensions, source), that is a Criteria finding.
- **Research and learning: source mode.** If the draft asks about specific papers, figures, quotes or current facts, check that it says whether to answer from memory (closed-book) or from sources (open-book), and that it attaches or names the sources. Recall of well-known work is usually right, but invented specifics cluster in obscure (long-tail) items. For anything Jim will cite or act on, the fix is open-book plus per-claim confidence.
- **Read the draft literally,** as a fresh model with no shared history would. Every word that could mean two things is a finding.
- **Check the attachments.** If the draft says "attached" or "see picture", confirm the attachments exist and are relevant.
- **Standing instructions count.** Jim's account-wide instructions (the Prompt coaching block) reach every chat, and a Project's instructions reach every chat in it. If either already covers something (a role, the feedback request, asking before acting), don't flag that thing as missing from the draft.
- **Severity:**
  - **Blocker:** Claude would have to guess something that changes the result.
  - **Improve:** it would cost a round trip.
  - **Nice:** polish.
- **Fairness (required):**
  - Only flag information a non-specialist could reasonably have known to include. Don't flag something that needs knowledge of Claude's internals or tools.
  - If the draft is a deliberate map request (an overview, options, or where to start on a topic Jim can't narrow yet), breadth is the goal. Don't call it too open. Only suggest context that would tailor the map (what prompted the question, his background).
  - **Non-specialist facts.** A fact a specialist would supply but Jim couldn't reasonably know is not a finding. Instead: (a) list it under "Non-specialist facts for this task" in the output, with the term of art and why it matters, and (b) in the tightened prompt, add a line asking Claude to raise these questions before starting ("Before you begin, ask me what a specialist would need: [list]"). A missing fact that is a graduated entry on the For the non-specialist tab *is* fair to flag, because Jim has shown he knows it.
- **Evidence-based fixes only.** Don't propose generic prompt formulas as improvements: expert personas don't raise accuracy (Zheng et al. 2023, arXiv:2311.10054), "think step by step" adds little on models that already reason (Meincke et al. 2025, arXiv:2506.07142), and politeness or emphasis effects are inconsistent (Meincke et al. 2025, arXiv:2503.04818). Fixes should add context, exact words, criteria or boundaries.
- **Point out what's already strong** (one line). Don't pad.

## 3. Route (model tier and effort)

Recommend a model tier and reasoning effort for sending the prompt. This is advice for Jim to act on before he sends; it is never a finding and never counts toward the verdict.

**When to route.** Only when the draft asks for real work: a deliverable, a design, a decision, research, troubleshooting, or a plan. Skip routing for quick factual questions, short replies, and casual chat; omit the Route line entirely in those cases.

**Speak in tiers, not model names.** Model names change every few months; the tiers don't. Use "top tier", "mid tier" or "small tier", plus an effort of low, medium or high, so Jim can pick the matching model and effort control in whichever harness he sends the prompt from (`claude.ai`, Claude Desktop, Claude Code, or Antigravity).

**Score four signals** from the draft (and the guide's task type):
1. **Openness.** Is the problem still being mapped (unknown unknowns, options, architecture, "where do I start"), or is it executing something already specified? Open problems need breadth and judgment, which come mainly from the tier.
2. **Stakes.** How hard is the result to reverse? Cutting material, buying parts, sending a message, or a spec that others will build from all count as high.
3. **Verifiability.** Can the answer be checked cheaply (it runs, it measures, it compiles, the math balances)? Checkable multi-step work rewards more effort; hard-to-check judgment rewards a higher tier.
4. **Context load.** Does the draft lean on a long earlier chat? Switching to a cheaper model mid-chat still makes it read the whole transcript, so the cost saving shrinks and stale ideas carry over.

**Default mapping:**
| Situation | Route |
|---|---|
| Open mapping or design, high stakes | Top tier, high effort |
| Open breadth survey or overview, low stakes | Top tier, medium effort |
| Reviewing or verifying work a cheaper model produced | Top tier, medium effort |
| Well-specified multi-step work that can be checked (debugging a specific failure, calculations, toolpath or tolerance math) | Mid tier, high effort |
| Executing a clear spec, drafting, ordinary explainers | Mid tier, medium effort |
| Mechanical transforms (reformat, extract, rename, summarize a short text) | Small tier, low effort |

**Overrides:**
- High stakes never route below mid tier. For an irreversible step, recommend at least a top-tier review pass before acting.
- If context load is high and the task is shifting from mapping to execution, recommend distilling first (the distill-spec skill) and sending the prompt in a fresh chat with only the spec.
- If signals conflict and the choice matters, pick the higher tier and say in a few words which signal decided it.

**Current tier examples (update when models change; never put model names in the Route line):**
| Tier | Claude family | Gemini / Antigravity equivalent |
|---|---|---|
| Top | Opus | Pro / Carbon |
| Mid | Sonnet | Flash |
| Small | Haiku | Flash Lite |

## 4. Output (keep it short)

1. **Verdict.** One line: ready to send, or N blockers.
2. **Route.** One line, only when section 3 applies: tier, effort, and the deciding signal(s) in a few words, e.g. `Route: top tier, high effort. Open mapping, hard to reverse.` Add a second line only if a fresh chat is recommended: `Fresh chat: distill the earlier chat with distill-spec first.`
3. **Findings.** A numbered list, blockers first. Each finding gets:
   - the checklist item
   - the exact phrase in the draft
   - why it matters
   - the fix
4. **Questions only Jim can answer.** A numbered list of facts Claude can't supply (dimensions, tools on hand, goal). Don't invent them. If there are non-specialist facts (section 2), add them here under the sub-label "Non-specialist facts for this task", one line each: term, why it matters.
5. **Tightened prompt.** In a code block, ready to paste. Keep Jim's voice and content. Mark unknowns as `[FILL: …]` rather than guessing. Keep any lines that work. Don't add a role line unless he had one, and keep role lines to one sentence.

Keep the whole reply under about 300 words, excluding the rewritten prompt. Use no headings beyond those five labels.

## 5. Feed the guide

If this lint finds a miss that isn't covered by the checklist, end with one line: "New pattern for the guide: …". If it surfaced a non-specialist fact that the For the non-specialist tab doesn't have, add one line: "New non-specialist entry: term · task type · the question it answers". Don't edit the guide or its tabs here; that's the prompt-guide-update skill's job.
