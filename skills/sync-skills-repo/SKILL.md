---
name: sync-skills-repo
description: Copy Jim's own account skills into his dexiotites GitHub repo (skills/ folder), then commit and push. Use when Jim asks to sync, back up, or update the skills repo, or right after a new skill has been saved. Optional argument is the path to an existing local clone of the repo.
---

# Sync account skills into the dexiotites repo

The repo `github.com/daemacles/dexiotites` (remote `git@github.com:daemacles/dexiotites.git`,
branch `main`) keeps a copy of each of Jim's account skills in `skills/<name>/`. **The account
versions are the master copies.** This skill makes the repo match them, then commits and pushes.

Argument (optional): path to a local clone. Jim's usual clone is `~/programming/dexiotites.git`
on his computer.

## 1. Get the repo

- **Path given:** use it with whichever shell can reach it: the local shell, or the device
  bridge's shell (`mcp__remote-devices__device_bash`) when the path is on Jim's computer.
  Confirm it is a git repo whose `origin` is `daemacles/dexiotites`. Run `git status`. If there
  are uncommitted changes, **stop**, show them, and ask Jim to commit or discard them first, so
  that they don't end up in the sync commit. Then `git pull --ff-only` (skip this if the branch
  has no commits yet).
- **No path:** clone a fresh copy into the working directory. In a cloud session, first attach
  the repo with the `add_repo` tool (owner `daemacles`, repo `dexiotites`, access `push`) and run
  the clone command it returns. That is how a cloud session gets push rights: the session's git
  proxy carries the credentials over HTTPS. The cloud workspace has no SSH client, and the
  proxy rewrites `git@github.com:` URLs to HTTPS, so SSH keys play no part there. Outside the
  cloud, run `git clone git@github.com:daemacles/dexiotites.git`.

## 2. Find Jim's account skills

- Synced copies are in `~/.claude/skills/synced/*/`. The `manifest.json` there lists each skill
  with `name`, `source` and `updatedAt`. **Jim's own skills are the entries whose `source` is
  neither `anthropic` nor `anthropic-example`.** Each skill's files are in the folder with the
  skill's name, next to the manifest.
- If there is no manifest, ask Jim where to find the skills rather than reconstructing them from memory.
- A skill saved moments ago may not have synced yet. If Jim names a skill that is missing,
  say so instead of skipping it silently.
- Check whether any synced skill references another non-built-in skill (for example,
  `prompt-guide-update` loads `google-workspace`). If that dependency comes from an external
  source and isn't synced here, note it in the final report so external dependencies stay visible.

## 3. Compare, then copy

First find the most recent sync commit in the repo (`LAST_SYNC=$(git log -1 --grep='^Sync account skills' --format=%H)`), if any.

For each of Jim's skills:

1. **Check for repo-side edits.** Ignore differences that are only formatting the app applies
   when a skill is saved: quotes around frontmatter values and a missing final newline. If
   `skills/<name>/` exists and still differs from the account version, check whether the repo copy
   was modified independently:
   - Did any commit touch `skills/<name>` *after* `$LAST_SYNC` (`git log "$LAST_SYNC..HEAD" --oneline -- "skills/<name>"`)?
   - Or, if `$LAST_SYNC` is empty, is `git log -1 --format=%cI -- "skills/<name>"` newer than the
     account skill's `updatedAt`?
   - **Neither (account version is strictly ahead, the usual case):** the account wins. Go on to step 2.
   - **Either holds (repo has independent edits):** someone edited the repo copy in git, and an
     accidental re-save in the app must not clobber it. **Stop for that skill.** Show Jim the diff
     and ask which he wants:
     - **(a) Merge.** Combine both versions, resolving conflicts yourself. Show Jim the merged
       result before writing it. Once he approves, write it to the repo and offer to update the
       account skill to match on a skill review card. Until the account matches, every sync
       will flag this skill again.
     - **(b) Overwrite.** Replace the repo copy with the account version.
2. **Copy** every file of the account skill into `skills/<name>/` (ensuring a trailing newline on
   markdown files), replacing what's there.
3. **Embedded files.** If `SKILL.md` contains a line `<!-- embedded-file: <relative path> -->`
   immediately followed by a fenced code block, create parent directories as needed and write that
   block's contents (without the fence lines, ending with a single trailing newline) to
   `skills/<name>/<relative path>`. If the written content starts with `#!`, mark the file
   executable (`chmod +x`). This regenerates repo-only helper files from the copy inside the
   skill, e.g. annotate-code's `scripts/comment_diff_check.py`.
4. **Never delete.** If a skill exists in the repo but not in the account, leave it and report it.

Leave `instructions/`, `docs/`, `tests/`, and `MAINTENANCE.md` alone. For a skill **new** to the
repo, also add a row for it to the appropriate skills table in `README.md`, writing a concise
one-sentence summary of what it does (omitting `"Use when…"` trigger instructions so it matches
existing rows).

## 4. Validate, commit, and push

1. If nothing changed, say so and stop. Don't make an empty commit.
2. **Validate before committing:**
   - Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` from the repo root.
     Fix any hygiene failure (missing `README.md` row, trailing newline, `+x` bit, embedded-file
     extraction). If an embedded script's own tests fail, **stop** and report the failure instead
     of committing broken code.
   - Read `MAINTENANCE.md` (§1 and §4) and check the diff (`git diff`) of changed skills against
     it. Do not rewrite Jim's account skills silently during a sync—record any checklist findings
     for step 5's report so Jim can tighten them if needed.
3. Commit with the message `Sync account skills: <comma-separated names>`, then push to `origin main`.
4. **How to push depends on where the clone is:**
   - **Cloud clone (attached with `add_repo`):** run `git -c push.negotiate=true push origin main`.
     If the push is refused for lack of permission, the repo was attached read-only. Call
     `add_repo` again with access `push`. A warning that push negotiation failed does not mean
     the push failed.
   - **Clone on Jim's computer, reached through the device bridge:** git there can't delete its
     own lock files until deletion is allowed. Request it once for the repo folder with
     `mcp__remote-devices__device_request_delete_permission` before committing. That shell
     usually can't reach GitHub. If the push fails, keep the commit and tell Jim to run
     `git push` himself, or push from a cloud clone instead.
   - **Local shell on Jim's computer** (e.g. Claude Code run there): a plain `git push`, which
     uses Jim's own SSH setup.
   Never write credentials into the repo or into this skill.

## 5. Report

Tell Jim which skills were added, updated, unchanged, or present only in the repo, plus any
conflicts you stopped on, any `MAINTENANCE.md` checklist findings on changed skills, external skill
dependencies, and the commit hash and push status.
