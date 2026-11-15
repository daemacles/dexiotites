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
