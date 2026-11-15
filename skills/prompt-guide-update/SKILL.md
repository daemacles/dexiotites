---
name: "prompt-guide-update"
description: "Update Jim's living prompting guide (Google Doc) with prompt feedback from chats not yet processed. Use for \"update my prompt guide\" or any request to fold new feedback into it."
---

# Update the prompting guide

The guide is a Google Doc: **Prompting Guide: Working with Claude**
- File ID: `1RlEDKMVg3FysnslHnX-OeYwoRcQ_tGh_FbuuCB_UjD8`
- Link: https://docs.google.com/document/d/1RlEDKMVg3FysnslHnX-OeYwoRcQ_tGh_FbuuCB_UjD8/edit

It is a synthesis, not a quote log. Each update folds new evidence into the existing structure. The doc has five tabs:
- **Guide** (`t.0`): the reader-facing guide. In order, it holds: the header and "How to use it" paragraph; the **Introduction** ("Introduction: what a good prompt carries"); sections 1 to 5; and the **appendices** (Appendix A onward). Sections 1 to 5 are: 1 pre-flight checklist, 2 principles (2.1 to 2.8), 3 task table, 4 habits, and 5 setup and tooling notes (ending with what Claude's requests to Jim should include).
- **Prompt coaching block** (`t.u0ecpbneurxc`): paste-ready text for Jim's account-wide instructions (Settings → Your Claude → Instructions; older layout: Settings → Account → Instructions for Claude), which apply to every chat, Projects included. The block runs from Jim's general rules, through `<prompt_coaching>` … `</prompt_coaching>`, to a closing marker line that starts "[The text above is my standing instructions from my account settings". Its numbered priority list mirrors the checklist in section 1. **This skill maintains that list; Jim never edits it by hand.** Project instructions hold only each Project's own context, never a copy of the block.
- **For the non-specialist** (`t.yqusl9zd8kem`): a reader-facing glossary of facts and terms of art Jim couldn't have known to give, maintained by this skill from every scope. It opens with a short "How it is kept" section, then one Heading 2 per task area (LLM collaboration, Research and learning, Coding, CAD and fabrication, Health, and others as needed). Each entry is a paragraph holding the term in bold, followed by bullets with bold labels: "Why it matters:", "The question it answers:", and "Example:" (with the chat date). A graduated entry gets " (graduated)" after its term. The Guide-tab rules apply here too: no to-dos, history or counts.
- **My own notes**: Jim's. Never edit it.
- **Maintenance** (`t.gyai9ejglmo9`): bookkeeping for this skill, made up of the run log and the source ledger.

**The Guide tab must stand on its own as of its last update.** It holds only "do this" guidance, examples, and the explanatory Introduction and appendices. Never put any of these in it:
- to-dos or recommendations to change a Project (those go in the reply)
- status of setup work ("adopted in Home DIY")
- revision history, changelogs, or retired advice
- bookkeeping counts in the reader-facing text (header, introduction, habits intro, principle text, appendices)

The only counts allowed in the Guide are the checklist's "Missed in" column.

**The Introduction and appendices belong to Jim, not to this skill.** They are exposition he asked for: the Introduction maps the principles in section 2, and the appendices explain why prompting works the way it does, with figures and literature references. Update runs never rewrite, trim, reorder, or fold evidence into them. The one exception is cross-references: the Introduction (and any appendix) cites principles by number and name, such as "The goal (2.3)". When a run adds, removes, renumbers, or renames a principle, update those references in the same run and say so in the reply. Appendix A contains a figure (an inline image or a "[Figure 1 …]" placeholder paragraph); never delete or edit through it.

## 0. Preconditions

- **Edits must land in the same doc, at the same link.** That needs both the **Google Drive** connector (`read_file_content` with `includeComments: true`, used in step 2) and the **Google Docs** connector (`read_doc` / `update_doc`, used in step 7). If either isn't available in this chat, stop. Tell Jim which connector to turn on, and offer to list the proposed changes in chat instead. Never recreate the doc, and never trash it.
- Load the `google-workspace` skill and read its `references/docs.md` (which also provides `docs_index.py` for step 7) before editing. If `google-workspace` isn't installed in this environment, stop before step 7 rather than computing character indices by hand.
- If two update runs could overlap (for example, one per Project), run them one at a time. Jim and other sessions may also have edited the doc since the last run, so always work from a fresh read.

## 1. Establish this run's scope

Chat search only sees the scope it runs in. Outside a Project it sees all regular (non-project) chats. Inside a Project it sees only that Project's chats. Jim can move chats into, out of, and between Projects at any time, so a chat's scope can change after it has been processed.

1. Decide the scope from the session context: the attached Project's name, or "regular" if no Project is attached.
2. Record the run's start time (UTC).
3. **Scope is a location, not ownership.** A run may update any ledger row whose chat it can see, whatever Scope that row currently records.

## 2. Read the current state

1. Read the guide with Drive `read_file_content` (`includeComments: true`). It returns all five tabs as Markdown, each under a `# <tab title>` heading. Note the entries on the For the non-specialist tab, so step 6 can merge new ones instead of duplicating them. Note any comments Jim left: comments are instructions about the guide.
2. From the Maintenance tab's source ledger, collect every row's chat link, **Scope**, and "Processed through" timestamp. **The chat ID in the link is the row's key.** Match chats to rows by ID, never by title. Chat IDs survive moves between scopes (observed 2026-10-14).
3. From the Maintenance tab's run log, find the most recent run that covered this scope.
4. From the Guide tab, note the version in the header, plus the checklist counts and last-seen dates. Note the section numbers the Introduction cites, so step 6 can keep them in sync.

## 3. Find new material

**Inventory the whole scope; don't rely on a time cutoff.** Moving a chat between scopes does not change its last-updated time (observed 2026-10-14). A cutoff filter therefore misses chats moved in from elsewhere, including old chats that were never processed.

1. **List every chat in scope** with `recent_chats`, 20 per call, paging with `before:` set to the earliest `updated_at` of the previous batch. Keep going until a batch comes back short or empty.
   - **Large scopes:** if the scope has more than about 100 chats (5 calls), stop listing. Fall back to a cutoff: the time of the last run in this scope (from the run log), minus one hour, and use `after:`. Say in the reply that this run was cutoff-based and could miss moved chats. Recommend a periodic full account export to close the gap.
2. **Compare each listed chat to the ledger by ID:**
   - **Not in the ledger:** new. Read it all.
   - **In the ledger, last update newer than "Processed through":** read only the messages after that time.
   - **In the ledger, nothing newer:** skip it.
   - **In the ledger as "skipped":** never re-read it, even if it has newer messages. Only relabel its Scope if it moved.
   - **In the ledger with a different Scope** (including blank): the chat has moved, or wasn't seen by a scoped run before. Relabel the Scope to this run's scope, and note it in the run-log line ("moved: A → B", or "scope set: B" if it was blank). Then apply the rules above.
3. **Rows recorded in this scope that the inventory didn't find:** the chat was moved out or deleted. Don't delete the row. Set its Scope cell to "not found in <scope>, YYYY-MM-DD". The next run that sees the chat clears this.
4. **Searches (backstop):** run `conversation_search` for "Prompt feedback", "Feedback:", "Prompting note", "On your prompting", "Feedback on your prompt", "meta-feedback", "I assumed", "ambiguous", "could mean", "I read it as". Any hit not already covered by the inventory goes through step 2.
5. **Skip guide-maintenance chats:** the chat that built the guide (ID starting fb219593), any chat whose main task was updating or reviewing this guide or this skill (including the current chat), and throwaway test chats. Add each one to the ledger once, marked "skipped (guide maintenance)" or "skipped (test chat)", so later runs don't re-examine it. A chat whose main task was a conceptual discussion that Jim then asked to add to the guide (for example, the chat behind Appendix A) still counts as a normal chat for evidence; only the turns that edited the guide are maintenance.
6. **Other scopes:** list them in the reply as not covered. Tell Jim to run this skill inside each Project and once from a regular chat. Alternatively he can attach a fresh account export (`conversations.json`). With an export, parse it with Python (`python3 -I`, data in its own folder), diff by `uuid` and last-message time against the ledger, and treat the export as covering every scope. An export can't show which Project a chat is in, so leave Scope cells as they are.

## 4. Re-check the setup (every run)

Claude can't edit Jim's account settings or Project instructions, so this step only compares and reports. **Everything it finds goes in the reply, not the Guide.**

- **Account instructions vs. the tab.** Jim's account-wide instructions arrive in the session context at the start of his first message, ending with the closing marker line. Compare them with the tab line by line, from the first line of the block to the closing marker. Ignore whitespace and straight-vs-curly quote differences. If they differ, or the tab changed in this run (step 6), list exactly what to re-paste into Settings → Your Claude → Instructions, quoting the tab's current text; when more than a few lines differ, tell him to replace the whole block. If no account instructions are visible, or they lack the closing marker, say so and give the paste steps from the tab's "Where to paste" bullet.
- **Project runs only: Project instructions.** Read the Project's current instructions from the session context. They should hold only that Project's own context and rules, ideally starting with a source line such as "[Home DIY project instructions, not part of my message.]". If they still contain any of the coaching block (`<prompt_coaching>`, the numbered priority list, the feedback format, or the old PROJECT SPECIFIC NOTES heading), list what to delete and what to keep. Suggest the source line if it's missing.
- Note any other setup gaps worth fixing, such as rules sitting in a Project description instead of its instructions field.
- Log setup changes as Setup evidence for the counts, and update the date in the ledger's project-setups row. Name projects only as the hygiene rules in step 6 allow.

## 5. Extract evidence

For each new chat, or each chat's new messages, read Jim's prompts and Claude's replies, and log each item as (chat, date, scope, task type, theme, side, miss or strength, explicit or implicit, one-line paraphrase). **Side** is Jim or Claude.

**Task type** is the kind of work the chat was doing when the item occurred, judged by how the output gets checked, not by subject: `research-learning` (checked against sources), `coding` (checked by running it), `cad-fabrication` (checked by render, measurement or fit), `health` (checked against guidelines or a clinician), `writing` (checked by the reader), `other`. One chat can hold several task types; tag each item by its own turn.

- **Explicit evidence:** any prompt-feedback section in Claude's replies, whatever its label.
- **Implicit evidence on Jim's side:**
  - assumptions Claude stated
  - ambiguities Claude flagged
  - clarifying questions Claude had to ask before starting
  - Jim's corrections ("actually", "I meant", "sorry, I forgot")
- **Edited re-sends are not evidence by themselves.** Jim sometimes presses Enter instead of Shift+Enter and replaces the message right away. Count a re-send as a Complete-prompt miss only when the first version was clearly finished and Claude acted on it, and the later version added a requirement that changed the result.
- **Evidence on Claude's side (theme "Claude's asks"):** a request Claude made of Jim (run a test, measure, photograph, check a setting) that lacked any of:
  - why: the question the action answers
  - steps that fit Jim's actual setup (he uses the Claude Desktop and Mobile apps; a browser-only step is a miss)
  - exactly what to report back, ideally as a fill-in reply
  - what Claude would check itself

  Count a round trip caused by such a request as a Claude-side miss. Count a well-formed request as a Claude-side strength.
- **Feedback fairness (required):** before logging Claude's prompt feedback as a Jim-side miss, check two things.
  - Could a non-specialist reasonably have known to include the missing thing? If it needed knowledge of Claude's internals, tools, or what Claude was about to need, don't log it against Jim. Log it as a Claude-side miss under "Claude's asks" if Claude's own request caused it, or drop it.
  - Was the question a deliberate map request (Jim asked for an overview, options, or where to start, or said he doesn't know enough to narrow it)? Then breadth is the goal, not a miss. Log only missing context that would have tailored the map. An open question that wasn't framed as a map can still be a Goal miss, and the 2.3 sub-rule is the fix to point to.
  - If wrong or unfair feedback already shaped the Guide's text, fix that text and say so in the reply. Don't record the retired advice in the doc.
  - **Non-specialist candidates:** an item dropped by the first check (a non-specialist couldn't have known to include it) is still useful: it is one of Jim's unknown unknowns. Log it as a non-specialist candidate with its task type, the term of art involved, and the question it answers. Step 6 turns these into entries.
- **Strengths count too.** Log what worked, including a well-framed map request.
- **Label drift:** if replies use a feedback label other than "**Prompt feedback:**", note it for the reply.

Theme keys, which map to the Guide's sections:
- Kit (2.1)
- Exact words (2.2)
- Goal (2.3, including map requests)
- Complete prompt (2.4)
- Criteria (2.5)
- Boundaries (2.6)
- Context check (2.7)
- Invite unknowns (2.8)
- Habits (section 4)
- Setup (section 5)
- Claude's asks (last entry of section 5)

An item that fits no key goes on a "candidates" list. Propose a new principle only when at least 3 candidates share a pattern.

## 6. Synthesize

- **Nothing new:** if the scope has no new chats, no new messages, no moved or missing chats, and no setup changes, leave the Guide alone and don't bump the version. Still append the run-log line, because later runs use it as the last-run time.
- **Bookkeeping only:** if the only changes are Scope relabels, not-found flags, or skipped rows, edit the Maintenance tab only, and don't bump the version.
- **Counts:** update each checklist row's "Missed in" (chats, with the instance count in parentheses) and "Last seen". Re-rank by chat count, breaking ties by instance count. Claude-side misses don't go in Jim's checklist.
- **Coaching-block sync (required whenever section 1 changes):** if the checklist's order, item names or "Ask yourself" wording changed, or an item was added or graduated, rewrite the numbered list on the Prompt coaching block tab to match. Keep the tab's format: one line per item, "N. Name: what to look for", written in Jim's voice ("what I don't have"). Then say in the reply that the block changed and quote the lines to re-paste into Settings → Your Claude → Instructions. Never touch the general rules above `<prompt_coaching>` (Jim's own) or the closing marker line.
- **Introduction and appendices sync (required whenever section 2's numbering or names change):** update only the principle numbers and names they cite, so each cross-reference points at the right principle. If a new principle fits one of the Introduction's groups, don't add it there yourself; suggest the wording in the reply and let Jim decide. Never change their other text.
- **Task-type matrix (Maintenance tab):** keep the "Task-type matrix" table of Jim-side misses, with theme keys as rows and task types as columns (that orientation fits the page width), plus a first row counting chats with any miss per task type. Counts are cumulative chat counts; counts up to 2026-11-07 were backfilled from ledger titles and carry no instance counts, so add instance counts in parentheses only for evidence logged since. Update it every run that logs evidence. It is bookkeeping, so it lives on the Maintenance tab, never in the Guide.
- **Module decisions (reply only):** use the matrix to decide whether a task type needs its own module (a short checklist of what that kind of task adds to the core).
  - **Propose a module** when a task type has at least 3 chats whose misses concentrate in something the core checklist doesn't name (for example, CAD misses that are all units and datums), or whose miss profile differs clearly from the overall profile.
  - **Propose folding a module back** when it has existed for 3 or more relevant chats and that task type's misses didn't drop.
  - Put the proposal and the matrix rows behind it in the reply. Don't add, restructure or remove modules in the Guide unless Jim approves; an approved module goes into section 3 (task table) and counts as restructuring for versioning when it changes the Guide's sections.
- **For the non-specialist tab (every scope):** turn each non-specialist candidate into an entry on the tab, under the heading for its task area, in the tab's format. Merge with an existing entry instead of duplicating it. Mark an entry "(graduated)" when Jim has supplied that fact unprompted in about 3 chats, and suggest in the reply where its point should go in the checklist, task table or an approved module. When a candidate is about a sensitive personal matter, write only the general lesson (for example "exact medication names and doses"), never Jim's details. Content hygiene applies.
- **Graduation:** a checklist item whose last miss is more than about 60 days old, with 3 or more relevant chats since, moves to section 4 (Habits). Say so in the reply.
- **Examples (section 2):** each principle with examples shows them in one two-column table under a "From your chats." label. The header row is "You did" | "Do this instead (because…)".
  - **Miss rows:** what Jim did, then the fix plus the reason it matters.
  - **Strength rows:** what Jim did, then "Keep doing this, because …".
  - **Row limits:** about 4 to 8 rows per table. Add a row only if it teaches something the existing rows don't, and replace a weaker row rather than letting the table grow.
  - **2.4 (Complete prompt) has no examples table by design.** It stays "do this" guidance only.
  - **Paraphrase, never quote at length.** No living counts in principle text ("in five chats"), because they go stale.
- **Rules and sub-rules:** add or sharpen them in prose or bullets. Update "Status" lines (adopted, improving, recurring) where a principle has one.
- **Claude's asks:** if there are Claude-side misses, sharpen the "What Claude's requests to you should include" entry in section 5 only if the new example is clearer than what is there. No counts.
- **Header:** exactly "Version X.Y, updated YYYY-MM-DD." Nothing else.
- **Versioning:** bump the header only when the Guide or the coaching block changed. Use a minor bump for routine updates and a major bump (v2.0) for restructuring.
- **Content hygiene (required):**
  - Write the lesson only. Never record health, medical, financial, legal, or relationship details.
  - Ledger rows for sensitive chats use "Personal / health topic (title withheld)".
  - Never name a Project whose name reveals a sensitive topic, in the ledger, the Scope column, the run log, or anywhere else. Say "a personal project".
  - The doc must be safe to share with anyone.

## 7. Write

1. Show Jim a short summary before writing:
   - the scope and how it was covered
   - new chats found, and chats moved or missing
   - counts by theme, Jim's side and Claude's side
   - any checklist re-ranking or graduation
   - any proposed new principle, and any Introduction cross-reference it would change
2. For routine updates where Jim has said "just do it", proceed without waiting.
3. Edit in place with the Google Docs connector, following the google-workspace rules. Scope every request to the right tab (`tabId`, or `tabsCriteria` for `replaceAllText`).
4. **Positions:** `read_doc` results are large and get saved to a file. The saved file wraps the document in a top-level `content` key, so unwrap it first: `python3 -I -c "import json,sys; d=json.load(open(sys.argv[1])); json.dump(d['content'],open(sys.argv[2],'w'))" SAVED.txt doc.json`, then run `docs_index.py find` or `outline` on `doc.json`. Never compute positions from the Markdown read.
5. **Section 5 is no longer the end of the Guide tab.** The appendices follow it. A new section 5 entry goes at the end of the last section 5 bullet (that paragraph's `endIndex - 1`), never at the tab's body end, which is now the end of the last appendix. A new principle goes after the last paragraph of the principle before it. Nothing from an update run goes after the "Appendix A" heading.
6. **Style inheritance traps:**
   - Inserted text takes the style of the text before it.
   - A table inserted right after a bold label comes out bold in every cell.
   - A row added with `insertTableRow` copies its neighbor's style, link styling included.
   - `replaceAllText` gives the whole replacement the style of the first character it replaces.
   - Paragraphs inserted after a bullet inherit its bullet and indent; clear them with `deleteParagraphBullets` and reset `indentStart`/`indentFirstLine` when the new text isn't a list item.

   After any of these, read again and set bold and link styling explicitly. Labels (and table header rows) are bold; body text and table body cells are not. In the ledger, only the chat title is a link (underlined, `rgbColor` blue 0.93333334).
7. **New tables** (for example, when a principle gets its first examples): use `docs_index.py new-table --bold-header`, inserting after the "From your chats." label, then clear bold on the body cells. Give a 5-column table explicit column widths that add up to 468 pt, so dates don't wrap.
8. Write in this order:
   1. Maintenance: ledger rows (append new rows, update changed ones), the task-type matrix, then the run-log line.
   2. Guide: checklist table, principle text and example tables, section 4 and 5 entries, Introduction and appendix cross-references (only if section 2's numbering or names changed), then the header.
   3. Coaching tab: its numbered list, whenever section 1 changed.
   4. For the non-specialist tab, if any entries changed. Insert entries at the end of their section (the last paragraph's `endIndex - 1`), set the bold term and labels explicitly, and bullet the label lines with `createParagraphBullets`.
9. **Run-log line** (append one per run, oldest first): "YYYY-MM-DD HH:MM UTC · scope · full inventory | cutoff | export · vX.Y (or 'no version change'). One short clause of what changed, e.g. +2 chats; moved: regular → Home DIY (1); Exact words now first."

## 8. Verify

- Re-read the doc. Check:
  - every new ledger row links to a real chat and has a Scope
  - no chat ID appears in two rows
  - the counts match your evidence log
  - labels and table headers are bold, and body text and table body cells are not (`docs_index.py find` reports bold)
  - only chat titles look like links
  - no sensitive details slipped in, including Project names
  - the tables still render (export to PDF and look, where you can run code)
  - the Introduction and appendices are unchanged apart from any cross-reference updates, and Appendix A's figure (or its placeholder) is still there
  - new entries on the For the non-specialist tab follow its format (bold term, bulleted bold labels) and hold no personal details
- **Cross-reference check (required).** These must agree after every run. Fix any drift in the same run.
  - The coaching tab's numbered list and section 1: same items, same order, same meaning.
  - The coaching block's requests rule and section 5's "What Claude's requests to you should include": same four parts, same app names.
  - The coaching tab's "How to use it" bullets and section 5's coaching-block and standing-rules bullets: both say the block goes in account settings and Projects hold only their own context.
  - The Introduction's cited principle numbers and names match section 2's headings.
  - The block still ends with the closing marker line, and everything in it keeps the monospace style.
  - The Guide tab holds no to-dos, setup status, history, or living counts outside the checklist.
- Reply with:
  - what changed (or "no change")
  - the link (it stays the same)
  - the scope covered, and whether by full inventory, cutoff, or export
  - the scopes not covered, ledger rows still missing a Scope, and rows flagged "not found"
  - module decisions: any module proposed or proposed for folding, with the matrix rows behind it, or "no module change"
  - non-specialist entries added, merged or graduated on the For the non-specialist tab
  - **setup to-dos**, all here, never in the doc: what to re-paste into Settings → Your Claude → Instructions (quoting the text), coaching text to remove from this Project's instructions, whether `prompt-lint`'s embedded fallback checklist needs refreshing (whenever section 1's items or ranking changed), label drift, and other setup gaps from step 4

## How this skill's own requests to Jim should look

When this run needs Jim to do something (attach an export, run the skill in another scope, re-paste the block, confirm a merge), say why, give steps that work in the Claude Desktop or Mobile app, and give a fill-in reply. For example: "Reply 'export attached' once conversations.json is in this chat."
