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

- Synced copies are in `~/.claude/skills/synced/*/` (the **account root**). Its `manifest.json`
  lists each skill with `name`, `source` and `updatedAt`. **Jim's own skills are the entries whose
  `source` is neither `anthropic` nor `anthropic-example`.** Each skill's files are in the folder
  with the skill's name, next to the manifest.
- If there is no manifest, ask Jim where to find the skills rather than reconstructing them from memory.
- A skill saved moments ago may not have synced yet. If Jim names a skill that is missing,
  say so instead of skipping it silently.
- Check whether any synced skill references another non-built-in skill (for example,
  `prompt-guide-update` loads `google-workspace`). If that dependency comes from an external
  source and isn't synced here, note it in the final report so external dependencies stay visible.

## 3. Classify, then copy

The repo records, in `skills/.sync-base.json`, a fingerprint of the account version each skill
was last synced from: its **merge base**. Comparing the account version, the repo copy, and the
base tells apart "only the account changed" from "the repo was edited in git". The classifier
script embedded at the end of this file does the comparison. It ignores the formatting the app
applies when it saves a skill (quoted frontmatter values, a missing final newline).

1. **Classify.** Write the embedded `scripts/sync_classify.py` block to a temporary file outside
   the repo (e.g. `/tmp/sync_classify.py`); this account copy is the master. Then run:
   ```
   python3 /tmp/sync_classify.py --account-root <account root> --repo <repo root>
   ```
   It prints one JSON line per skill with a `status`.
2. **Act on each status:**
   - `unchanged`: nothing to copy.
   - `account-ahead` or `new`: the account wins; copy it (step 3).
   - `repo-ahead`, `diverged` or `no-base`: the repo copy has edits the account may not have.
     **Stop for that skill.** Show Jim the diff between the account version and the repo copy, and
     ask which he wants:
     - **(a) Merge.** Combine both versions, resolving conflicts yourself. Show Jim the merged
       result before writing it. Once he approves, write it to `skills/<name>/` and offer to update
       the account skill to match on a skill review card. Until the account matches, the classifier
       will keep reporting this skill as `repo-ahead`.
     - **(b) Overwrite.** Copy the account version (step 3).

     Stop and wait for Jim's reply before acting on these skills.
   - `repo-only`: a repo skill with no account skill. Leave it and report it; never delete.
3. **Copy** every file of the account skill into `skills/<name>/` (ensuring a trailing newline on
   markdown files), replacing what's there.
4. **Embedded files.** If `SKILL.md` contains a line `<!-- embedded-file: <relative path> -->`
   immediately followed by a fenced code block, create parent directories as needed and write that
   block's contents (without the fence lines, ending with a single trailing newline) to
   `skills/<name>/<relative path>`. If the written content starts with `#!`, mark the file
   executable (`chmod +x`). This regenerates repo-only helper files from the copy inside the
   skill, e.g. annotate-code's `scripts/comment_diff_check.py` and this skill's
   `scripts/sync_classify.py`.
5. **Record the merge base** for every skill you copied, merged, or found `unchanged`:
   ```
   python3 /tmp/sync_classify.py --account-root <account root> --repo <repo root> --record <names>
   ```
   This rewrites `skills/.sync-base.json`; commit it with the skills. Don't record skills you
   stopped on and haven't resolved.

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
skills you stopped on (with their status), any `MAINTENANCE.md` checklist findings on changed
skills, external skill dependencies, and the commit hash and push status.

## Embedded classifier

This block must stay identical to `scripts/sync_classify.py`; the sync regenerates that file from
this block, so edit the script here.

<!-- embedded-file: scripts/sync_classify.py -->
```python
#!/usr/bin/env python3
"""Classify each account skill against its repo copy using a recorded merge base.

The Claude app's synced skills (the master copies) live in an account root: a folder
holding `manifest.json` plus one subfolder per skill. The repo keeps a copy of each in
`skills/<name>/` and, in `skills/.sync-base.json`, a fingerprint of the account version
each copy was last synced from (its merge base). Comparing all three tells apart "only
the account changed" (safe to copy), "only the repo changed" and "both changed" (ask).

Usage:
    python3 sync_classify.py --account-root DIR --repo DIR
        Print one JSON object per account skill (and per repo-only skill folder).
    python3 sync_classify.py --account-root DIR --repo DIR --record NAME [NAME ...]
        After the repo copies of NAMEs have been handled, set each NAME's merge base to
        the current account version.

Statuses printed:
    unchanged      repo copy equals the account version
    account-ahead  repo copy still equals the base; only the account changed: copy it
    repo-ahead     account still equals the base; only the repo changed: ask Jim
    diverged       both differ from the base: ask Jim
    no-base        copies differ and no base is recorded: ask Jim
    new            account skill with no repo copy: copy it
    repo-only      repo skill folder with no account skill: report it, never delete

Fingerprints ignore formatting the app applies when it saves a skill: double quotes
around frontmatter values and a missing final newline. Only files present in the
account version are compared, so files the repo extracts from embedded blocks don't count.
Requires Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BASE_FILE = Path("skills") / ".sync-base.json"
_QUOTED_FIELD = re.compile(r'^([A-Za-z_][\w-]*): (".*")$')


def normalize(text: str) -> str:
    """Undo the app's save-time formatting so equal content compares equal.

    Unquotes double-quoted top-level frontmatter values (the app writes
    `name: "x"` with JSON-style escapes) and ensures exactly one trailing newline.
    """
    lines = text.split("\n")
    if lines and lines[0] == "---":
        for idx in range(1, len(lines)):
            if lines[idx] == "---":
                break
            m = _QUOTED_FIELD.match(lines[idx])
            if m:
                try:
                    lines[idx] = f"{m.group(1)}: {json.loads(m.group(2))}"
                except json.JSONDecodeError:
                    pass                                   # not a JSON-style string; keep as is
    return "\n".join(lines).rstrip("\n") + "\n"


def fingerprint(skill_dir: Path, rel_files: list[str]) -> str:
    """Return a SHA-256 over the normalized contents of `rel_files` inside `skill_dir`.

    A missing file contributes a fixed marker, so a missing file never matches content.
    """
    h = hashlib.sha256()
    for rel in sorted(rel_files):
        h.update(rel.encode() + b"\0")
        path = skill_dir / rel
        if path.is_file():
            data = path.read_bytes()
            try:
                data = normalize(data.decode("utf-8")).encode("utf-8")
            except UnicodeDecodeError:
                pass                                       # binary file: compare raw bytes
            h.update(data)
        else:
            h.update(b"\0<missing>\0")
        h.update(b"\0")
    return h.hexdigest()


def account_skills(account_root: Path) -> dict[str, dict]:
    """Return Jim's own skills from `manifest.json`, keyed by name.

    Built-in skills (`source` of `anthropic` or `anthropic-example`) are excluded.
    Each value holds `updatedAt` and `files`, the skill's file paths relative to its folder.
    """
    manifest = json.loads((account_root / "manifest.json").read_text(encoding="utf-8"))
    skills: dict[str, dict] = {}
    for entry in manifest["skills"]:
        if entry.get("source") in ("anthropic", "anthropic-example"):
            continue
        folder = account_root / entry["name"]
        files = [str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file()]
        skills[entry["name"]] = {"updatedAt": entry.get("updatedAt"), "files": files}
    return skills


def classify(account_root: Path, repo: Path) -> list[dict]:
    """Compare every account skill with its repo copy and recorded base; see module doc."""
    base = _load_base(repo)
    acct = account_skills(account_root)
    results = []
    for name, info in sorted(acct.items()):
        repo_dir = repo / "skills" / name
        a = fingerprint(account_root / name, info["files"])
        if not repo_dir.is_dir():
            status = "new"
        else:
            r = fingerprint(repo_dir, info["files"])
            b = base.get(name, {}).get("sha256")
            if r == a:
                status = "unchanged"
            elif b is None:
                status = "no-base"
            elif r == b:
                status = "account-ahead"
            elif a == b:
                status = "repo-ahead"
            else:
                status = "diverged"
        results.append({"skill": name, "status": status, "account_updated_at": info["updatedAt"]})
    skills_dir = repo / "skills"
    if skills_dir.is_dir():
        for d in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            if d.name not in acct:
                results.append({"skill": d.name, "status": "repo-only", "account_updated_at": None})
    return results


def record(account_root: Path, repo: Path, names: list[str]) -> None:
    """Set each named skill's merge base to its current account version.

    Raises:
        KeyError: if a name is not one of Jim's account skills.
    """
    acct = account_skills(account_root)
    base = _load_base(repo)
    for name in names:
        info = acct[name]
        base[name] = {
            "sha256": fingerprint(account_root / name, info["files"]),
            "account_updated_at": info["updatedAt"],
        }
    path = repo / BASE_FILE
    path.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_base(repo: Path) -> dict:
    path = repo / BASE_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def main() -> int:
    """Parse arguments and either print classifications or record merge bases."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--account-root", required=True, type=Path,
                    help="folder containing manifest.json and the synced skill folders")
    ap.add_argument("--repo", required=True, type=Path, help="root of the dexiotites clone")
    ap.add_argument("--record", nargs="+", metavar="NAME",
                    help="record the current account version as the merge base for NAMEs")
    args = ap.parse_args()
    if args.record:
        try:
            record(args.account_root, args.repo, args.record)
        except KeyError as e:
            print(f"not an account skill: {e}", file=sys.stderr)
            return 2
        return 0
    for row in classify(args.account_root, args.repo):
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
