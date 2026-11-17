"""Unit tests for skills/sync-skills-repo/scripts/sync_classify.py.

Covers every status, the app's save-time formatting, and repo-only extracted files that must
not affect comparisons. One sequence gets its own case: after a merge, a sync must keep
flagging the merged skill until the account copy catches up.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "skills" / "sync-skills-repo" / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "sync_classify.py"
sys.path.insert(0, str(SCRIPT_DIR))

import sync_classify as sc  # noqa: E402

REPO_TEXT = '---\nname: demo\ndescription: Says "hi".\n---\n\nBody v1.\n'
# The same content as the app saves it: quoted frontmatter, no final newline.
APP_TEXT = '---\nname: "demo"\ndescription: "Says \\"hi\\"."\n---\n\nBody v1.'


class Fixture:
    """Temporary account root and repo with helpers to write skill versions."""

    def __init__(self, tmp: str) -> None:
        self.account = Path(tmp) / "account"
        self.repo = Path(tmp) / "repo"
        (self.repo / "skills").mkdir(parents=True)
        self.account.mkdir()
        self.manifest: list[dict] = [
            {"name": "builtin", "source": "anthropic", "updatedAt": "2026-01-01T00:00:00Z"}
        ]
        self._write_manifest()

    def _write_manifest(self) -> None:
        (self.account / "manifest.json").write_text(json.dumps({"skills": self.manifest}))

    def set_account(self, name: str, text: str, updated: str = "2026-11-01T00:00:00Z") -> None:
        (self.account / name).mkdir(exist_ok=True)
        (self.account / name / "SKILL.md").write_text(text, encoding="utf-8")
        self.manifest = [m for m in self.manifest if m["name"] != name]
        self.manifest.append({"name": name, "source": "plugin", "updatedAt": updated})
        self._write_manifest()

    def set_repo(self, name: str, text: str) -> None:
        (self.repo / "skills" / name).mkdir(exist_ok=True)
        (self.repo / "skills" / name / "SKILL.md").write_text(text, encoding="utf-8")

    def status(self, name: str) -> str:
        rows = sc.classify(self.account, self.repo)
        return next(r["status"] for r in rows if r["skill"] == name)


class TestClassify(unittest.TestCase):
    def test_app_formatting_alone_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp)
            f.set_account("demo", APP_TEXT)
            f.set_repo("demo", REPO_TEXT)
            self.assertEqual(f.status("demo"), "unchanged")

    def test_no_base_new_and_repo_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp)
            f.set_account("demo", APP_TEXT)
            f.set_repo("demo", REPO_TEXT.replace("v1", "edited"))
            f.set_account("fresh", "---\nname: fresh\n---\nx\n")
            f.set_repo("orphan", "---\nname: orphan\n---\nx\n")
            rows = {r["skill"]: r["status"] for r in sc.classify(f.account, f.repo)}
            self.assertEqual(rows, {"demo": "no-base", "fresh": "new", "orphan": "repo-only"})
            self.assertNotIn("builtin", rows)

    def test_account_ahead_repo_ahead_and_diverged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp)
            f.set_account("demo", APP_TEXT)
            f.set_repo("demo", REPO_TEXT)
            sc.record(f.account, f.repo, ["demo"])

            f.set_account("demo", APP_TEXT.replace("v1", "v2"))
            self.assertEqual(f.status("demo"), "account-ahead")

            f.set_account("demo", APP_TEXT)
            f.set_repo("demo", REPO_TEXT.replace("v1", "repo edit"))
            self.assertEqual(f.status("demo"), "repo-ahead")

            f.set_account("demo", APP_TEXT.replace("v1", "v2"))
            self.assertEqual(f.status("demo"), "diverged")

    def test_merge_keeps_flagging_until_account_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp)
            f.set_account("demo", APP_TEXT)
            f.set_repo("demo", REPO_TEXT)
            sc.record(f.account, f.repo, ["demo"])

            # Both sides edit; Jim picks "merge": merged text goes to the repo, and the base
            # is recorded as the account version at merge time.
            f.set_account("demo", APP_TEXT.replace("v1", "acct"))
            f.set_repo("demo", REPO_TEXT.replace("v1", "repo"))
            self.assertEqual(f.status("demo"), "diverged")
            f.set_repo("demo", REPO_TEXT.replace("v1", "acct+repo"))
            sc.record(f.account, f.repo, ["demo"])

            # Account not yet updated: must stay flagged, never silently overwritten.
            self.assertEqual(f.status("demo"), "repo-ahead")

            # Account updated to the merged text: settled.
            f.set_account("demo", APP_TEXT.replace("v1", "acct+repo"))
            self.assertEqual(f.status("demo"), "unchanged")

    def test_repo_only_extracted_files_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp)
            f.set_account("demo", APP_TEXT)
            f.set_repo("demo", REPO_TEXT)
            (f.repo / "skills" / "demo" / "scripts").mkdir()
            (f.repo / "skills" / "demo" / "scripts" / "tool.py").write_text("print(1)\n")
            self.assertEqual(f.status("demo"), "unchanged")


class TestCli(unittest.TestCase):
    def test_report_and_record_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp)
            f.set_account("demo", APP_TEXT)
            f.set_repo("demo", REPO_TEXT.replace("v1", "edited"))
            args = [sys.executable, str(SCRIPT_PATH), "--account-root", str(f.account), "--repo", str(f.repo)]
            out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
            self.assertEqual(json.loads(out.splitlines()[0])["status"], "no-base")

            subprocess.run(args + ["--record", "demo"], check=True)
            base = json.loads((f.repo / "skills" / ".sync-base.json").read_text())
            self.assertIn("demo", base)
            out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
            self.assertEqual(json.loads(out.splitlines()[0])["status"], "repo-ahead")

            bad = subprocess.run(args + ["--record", "builtin"], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
