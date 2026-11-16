"""End-to-end tests for install.py, the project installer.

Every test builds a throwaway dexiotites source (this checkout's shipped files committed to a
fresh git repository, so later commits can stand in for "dexiotites was updated") and one or
more throwaway projects, then runs the installer as a subprocess exactly as a user would.
The properties checked are the installer's safety rules: nothing is written when any change
is unsafe, a second run changes nothing, content the project owns is never replaced without
`--force`, and what it installs works (the installed checker runs).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
CARGO = '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n'
MARK = "<!-- dexiotites:begin"


def git(cwd: Path, *args: str) -> str:
    """Run git in `cwd` and return stdout; raises CalledProcessError on failure."""
    return subprocess.run(["git", *GIT_ID, "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout


def snapshot(root: Path) -> dict[str, tuple]:
    """Capture every file under `root` (outside .git) as content-or-link-target plus exec bit."""
    snap = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/") or rel == ".git":
            continue
        if path.is_symlink():
            snap[rel] = ("link", os.readlink(path))
        elif path.is_file():
            snap[rel] = (path.read_bytes(), os.access(path, os.X_OK))
    return snap


class InstallTestCase(unittest.TestCase):
    """Shared fixtures: a temporary source repository and helpers to build and install projects."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="dex-install-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.source = self.tmp / "dexiotites"
        self.source.mkdir()
        for name in ("instructions", "skills"):
            shutil.copytree(REPO_ROOT / name, self.source / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(REPO_ROOT / "install.py", self.source / "install.py")
        # Files a real checkout has but a project must never be affected by.
        (self.source / "tests" / "fixtures").mkdir(parents=True)
        (self.source / "tests" / "fixtures" / "Bad.kt").write_text("class Bad\n")
        (self.source / "tests" / "test_x.py").write_text("x = 1\n")
        git(self.source, "init", "-q", "-b", "main")
        self.commit_source("v1")

    def commit_source(self, message: str) -> None:
        git(self.source, "add", "-A")
        git(self.source, "commit", "-q", "-m", message)

    def project(self, name: str = "proj", files: dict[str, str] | None = None) -> Path:
        """Create a committed git project holding `files` (default: a one-file Rust crate)."""
        root = self.tmp / name
        root.mkdir()
        files = {"Cargo.toml": CARGO, "src/main.rs": "fn main() {}\n"} if files is None else files
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
        git(root, "init", "-q", "-b", "main")
        git(root, "add", "-A")
        git(root, "commit", "-q", "--allow-empty", "-m", "init")
        return root

    def install(self, *args: object, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.source / "install.py"), *map(str, args)],
                              cwd=cwd or self.tmp, capture_output=True, text=True)

    def edit_source(self, rel: str, old: str, new: str) -> None:
        path = self.source / rel
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))


class TestFreshInstall(InstallTestCase):
    def test_layout_manifest_and_working_checker(self) -> None:
        proj = self.project(files={"Cargo.toml": CARGO, "src/main.rs": "fn main() {}\n",
                                   "scripts/run.lua": "print(1)\n"})
        res = self.install(proj)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

        self.assertEqual((proj / "docs/COMMENTING.md").read_bytes(),
                         (self.source / "instructions/COMMENTING.md").read_bytes())
        checker = proj / ".agents/skills/annotate-code/scripts/comment_diff_check.py"
        self.assertTrue(os.access(checker, os.X_OK), "checker lost its executable bit")
        self.assertEqual(os.readlink(proj / ".claude/skills/annotate-code"),
                         "../../.agents/skills/annotate-code")
        self.assertTrue((proj / ".claude/skills/annotate-code/SKILL.md").is_file())
        self.assertEqual((proj / "CLAUDE.md").read_text(), "@AGENTS.md\n")
        agents = (proj / "AGENTS.md").read_text()
        self.assertEqual(agents.count(MARK), 1)
        self.assertTrue(agents.rstrip().endswith("<!-- dexiotites:end -->"))
        self.assertEqual((proj / ".luarc.json").read_bytes(),
                         (self.source / "instructions/lint/luarc-docs.json").read_bytes())
        self.assertFalse((proj / "ruff.toml").exists(), "no Python here: must not install ruff.toml")
        self.assertFalse((proj / "config").exists(), "no Kotlin here: must not install detekt config")

        manifest = json.loads((proj / ".dexiotites.json").read_text())
        self.assertEqual(manifest["skills"], ["annotate-code"])
        for rel, digest in manifest["files"].items():
            self.assertEqual(hashlib.sha256((proj / rel).read_bytes()).hexdigest(), digest, rel)
        self.assertEqual(manifest["commit"], git(self.source, "rev-parse", "HEAD").strip())

        cargo = (proj / "Cargo.toml").read_text()
        self.assertTrue(cargo.startswith(CARGO), "original Cargo.toml content must be kept intact")
        self.assertIn('[lints.rust]\nmissing_docs = "warn"', cargo)
        if sys.version_info >= (3, 11):
            import tomllib
            self.assertIn("clippy", tomllib.loads(cargo)["lints"])

        # Every project path the installed instructions tell agents to use must exist.
        block = agents[agents.index(MARK):]
        skill = (proj / ".agents/skills/annotate-code/SKILL.md").read_text().split("## Embedded")[0]
        for text in (block, skill):
            for rel in re.findall(r"`((?:docs|\.agents|\.claude)/[A-Za-z0-9_./-]+)`", text):
                self.assertTrue((proj / rel).exists(), f"installed instructions name `{rel}`, not installed")
        self.assertIn("`docs/COMMENTING.md`", block)

        # The installed checker must run from the project: comment-only edit passes, code edit fails.
        git(proj, "add", "-A")
        git(proj, "commit", "-q", "-m", "install")
        (proj / "src/main.rs").write_text("// entry point\nfn main() {}\n")
        ok = subprocess.run([sys.executable, str(checker), "--strict", "src/main.rs"],
                            cwd=proj, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        (proj / "src/main.rs").write_text("fn main() { let _x = 1; }\n")
        bad = subprocess.run([sys.executable, str(checker), "--strict", "src/main.rs"],
                             cwd=proj, capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)

    def test_second_run_changes_nothing(self) -> None:
        # A Rust-only project: the installed checker (.py) must not turn it into a "Python project".
        proj = self.project()
        self.assertEqual(self.install(proj).returncode, 0)
        before = snapshot(proj)
        res = self.install(proj)
        self.assertEqual(res.returncode, 0)
        self.assertIn("already up to date", res.stdout)
        self.assertEqual(snapshot(proj), before)
        self.assertEqual(self.install(proj, "--check").returncode, 0)

    def test_check_reports_pending_and_writes_nothing(self) -> None:
        proj = self.project()
        before = snapshot(proj)
        res = self.install(proj, "--check")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(snapshot(proj), before)

    def test_default_project_is_current_directory(self) -> None:
        proj = self.project()
        self.assertEqual(self.install(cwd=proj).returncode, 0)
        self.assertTrue((proj / "docs/COMMENTING.md").is_file())

    def test_several_projects_and_worst_exit_code(self) -> None:
        good = self.project("good")
        bad = self.project("bad", {"docs/COMMENTING.md": "our own, unrelated guide\n"})
        res = self.install(good, bad)
        self.assertEqual(res.returncode, 1)
        self.assertTrue((good / ".dexiotites.json").is_file())
        self.assertFalse((bad / ".dexiotites.json").exists())

    def test_non_git_folder_warns_but_installs(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        (plain / "tool.py").write_text('"""Tool."""\n')
        res = self.install(plain)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("not the root of a git repository", res.stdout)
        self.assertTrue((plain / "ruff.toml").is_file())

    def test_refuses_to_install_into_the_source(self) -> None:
        before = snapshot(self.source)
        res = self.install(self.source)
        self.assertEqual(res.returncode, 2)
        self.assertEqual(snapshot(self.source), before)

    def test_unknown_skill_is_an_error_and_extra_skill_is_remembered(self) -> None:
        proj = self.project()
        self.assertEqual(self.install(proj, "--skill", "no-such-skill").returncode, 2)
        self.assertFalse((proj / "docs").exists())
        self.assertEqual(self.install(proj, "--skill", "distill-spec").returncode, 0)
        self.assertTrue((proj / ".agents/skills/distill-spec/SKILL.md").is_file())
        self.assertTrue((proj / ".agents/skills/annotate-code/SKILL.md").is_file())
        before = snapshot(proj)
        self.assertEqual(self.install(proj).returncode, 0)      # bare rerun keeps both skills
        self.assertEqual(snapshot(proj), before)


class TestAgentsAndClaudeFiles(InstallTestCase):
    def body(self) -> str:
        text = (self.source / "instructions/AGENTS-commenting-section.md").read_text()
        return text.split("\n", 1)[1]

    def test_existing_agents_content_is_kept_and_block_appended(self) -> None:
        proj = self.project(files={"AGENTS.md": "# Rules\n\n## 1. Build\nUse make.\n"})
        self.assertEqual(self.install(proj).returncode, 0)
        agents = (proj / "AGENTS.md").read_text()
        self.assertTrue(agents.startswith("# Rules\n\n## 1. Build\nUse make.\n\n" + MARK))

    def test_numbered_legacy_section_is_adopted_and_keeps_its_heading(self) -> None:
        # A hand-made install from the previous dexiotites version, renumbered by the project.
        legacy = ("# Rules\n\n## 5. Build\nUse make.\n\n"
                  "## 6. Code Comments (Purpose-First Documentation)\n" + self.body() +
                  "\n## 7. Release\nTag it.\n")
        proj = self.project(files={"AGENTS.md": legacy})
        self.edit_source("instructions/AGENTS-commenting-section.md",
                         "**Keep comments true:**", "**Keep every comment true:**")
        self.commit_source("v2: reword a rule")
        res = self.install(proj)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        agents = (proj / "AGENTS.md").read_text()
        self.assertIn("-->\n## 6. Code Comments (Purpose-First Documentation)\n", agents)
        self.assertIn("**Keep every comment true:**", agents)
        self.assertNotIn("**Keep comments true:**", agents)
        self.assertTrue(agents.startswith("# Rules\n\n## 5. Build\nUse make.\n\n" + MARK))
        self.assertTrue(agents.endswith("<!-- dexiotites:end -->\n\n## 7. Release\nTag it.\n"))
        # Later updates rewrite only the block and still keep the project's heading.
        self.edit_source("instructions/AGENTS-commenting-section.md",
                         "**Keep every comment true:**", "**Comments stay true:**")
        self.commit_source("v3")
        self.assertEqual(self.install(proj).returncode, 0)
        agents = (proj / "AGENTS.md").read_text()
        self.assertIn("-->\n## 6. Code Comments (Purpose-First Documentation)\n", agents)
        self.assertIn("**Comments stay true:**", agents)
        self.assertEqual(agents.count("Code Comments (Purpose-First"), 1)

    def test_customized_legacy_section_blocks_the_whole_run_until_forced(self) -> None:
        legacy = "## Code Comments (Purpose-First Documentation)\n" + self.body() + "- Our own extra rule.\n"
        proj = self.project(files={"AGENTS.md": legacy})
        before = snapshot(proj)
        res = self.install(proj)
        self.assertEqual(res.returncode, 1)
        self.assertIn("NOTHING WRITTEN", res.stdout)
        self.assertEqual(snapshot(proj), before, "a conflict must leave the project untouched")
        self.assertEqual(self.install(proj, "--force").returncode, 0)
        agents = (proj / "AGENTS.md").read_text()
        self.assertNotIn("Our own extra rule", agents)
        self.assertEqual(agents.count(MARK), 1)

    def test_malformed_markers_are_an_error(self) -> None:
        proj = self.project(files={"AGENTS.md": MARK + " -->\n## Code Comments\nno end marker\n"})
        before = snapshot(proj)
        self.assertEqual(self.install(proj).returncode, 2)
        self.assertEqual(snapshot(proj), before)

    def test_claude_md_variants(self) -> None:
        with_import = self.project("a", {"CLAUDE.md": "@AGENTS.md\n\nNotes.\n"})
        without = self.project("b", {"CLAUDE.md": "Notes.\n"})
        linked = self.project("c", {"AGENTS.md": "# Rules\n"})
        (linked / "CLAUDE.md").symlink_to("AGENTS.md")
        reverse = self.project("d", {"CLAUDE.md": "# Rules\n"})
        (reverse / "AGENTS.md").symlink_to("CLAUDE.md")
        for proj in (with_import, without, linked, reverse):
            res = self.install(proj)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual((with_import / "CLAUDE.md").read_text(), "@AGENTS.md\n\nNotes.\n")
        self.assertEqual((without / "CLAUDE.md").read_text(), "@AGENTS.md\n\nNotes.\n")
        self.assertTrue((linked / "CLAUDE.md").is_symlink())
        self.assertIn(MARK, (linked / "AGENTS.md").read_text())
        self.assertNotIn("@AGENTS.md", (linked / "AGENTS.md").read_text(), "wrote through the symlink")
        # AGENTS.md -> CLAUDE.md: the block lands in the real file, with no self-import line.
        self.assertTrue((reverse / "AGENTS.md").is_symlink())
        text = (reverse / "CLAUDE.md").read_text()
        self.assertIn(MARK, text)
        self.assertNotIn("@AGENTS.md", text)

    def test_claude_skills_folder_variants(self) -> None:
        shared = self.project("shared")
        (shared / ".claude").mkdir()
        (shared / ".agents/skills").mkdir(parents=True)
        (shared / ".claude/skills").symlink_to("../.agents/skills")
        self.assertEqual(self.install(shared).returncode, 0)
        self.assertTrue((shared / ".claude/skills/annotate-code/SKILL.md").is_file())
        self.assertFalse((shared / ".agents/skills/annotate-code").is_symlink())

        blocked = self.project("blocked", {".claude/skills/annotate-code/SKILL.md": "stale copy\n"})
        res = self.install(blocked)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Claude Code may load a stale copy", res.stdout)
        self.assertEqual((blocked / ".claude/skills/annotate-code/SKILL.md").read_text(), "stale copy\n")

        wrong = self.project("wrong")
        (wrong / ".claude/skills").mkdir(parents=True)
        (wrong / ".claude/skills/annotate-code").symlink_to("/nonexistent")
        self.assertEqual(self.install(wrong).returncode, 0)
        self.assertEqual(os.readlink(wrong / ".claude/skills/annotate-code"),
                         "../../.agents/skills/annotate-code")


class TestUpdatesAndConflicts(InstallTestCase):
    def test_update_follows_the_source_and_removes_dropped_files(self) -> None:
        extra = self.source / "skills/annotate-code/reference/notes.md"
        extra.parent.mkdir()
        extra.write_text("notes\n")
        self.commit_source("v1 with an extra file")
        proj = self.project()
        self.assertEqual(self.install(proj).returncode, 0)
        self.assertTrue((proj / ".agents/skills/annotate-code/reference/notes.md").is_file())

        extra.unlink()
        self.edit_source("instructions/COMMENTING.md", "## 1.", "## 1. (revised)")
        self.commit_source("v2")
        self.assertEqual(self.install(proj, "--check").returncode, 1)
        self.assertEqual(self.install(proj).returncode, 0)
        self.assertIn("## 1. (revised)", (proj / "docs/COMMENTING.md").read_text())
        self.assertFalse((proj / ".agents/skills/annotate-code/reference").exists())
        manifest = json.loads((proj / ".dexiotites.json").read_text())
        self.assertEqual(manifest["commit"], git(self.source, "rev-parse", "HEAD").strip())
        self.assertNotIn(".agents/skills/annotate-code/reference/notes.md", manifest["files"])
        self.assertEqual(self.install(proj, "--check").returncode, 0)

    def test_unrelated_source_commit_leaves_the_project_untouched(self) -> None:
        proj = self.project()
        self.assertEqual(self.install(proj).returncode, 0)
        before = snapshot(proj)
        (self.source / "README.md").write_text("docs only\n")
        self.commit_source("unrelated")
        self.assertEqual(self.install(proj, "--check").returncode, 0)
        self.assertEqual(self.install(proj).returncode, 0)
        self.assertEqual(snapshot(proj), before)

    def test_locally_edited_copy_blocks_the_update_until_forced(self) -> None:
        proj = self.project()
        self.assertEqual(self.install(proj).returncode, 0)
        guide = proj / "docs/COMMENTING.md"
        guide.write_text(guide.read_text() + "\nLocal rule.\n")
        self.edit_source("skills/annotate-code/SKILL.md", "## Steps", "## Steps (v2)")
        self.commit_source("v2")
        before = snapshot(proj)
        res = self.install(proj)
        self.assertEqual(res.returncode, 1)
        self.assertIn("edited in this project", res.stdout)
        self.assertEqual(snapshot(proj), before, "the safe skill update must not be applied either")
        self.assertEqual(self.install(proj, "--check").returncode, 1)
        self.assertEqual(self.install(proj, "--force").returncode, 0)
        self.assertNotIn("Local rule.", guide.read_text())
        self.assertIn("## Steps (v2)", (proj / ".agents/skills/annotate-code/SKILL.md").read_text())
        self.assertEqual(self.install(proj, "--check").returncode, 0)

    def test_hand_made_install_of_an_older_version_is_updated_without_force(self) -> None:
        proj = self.project()
        (proj / "docs").mkdir()
        shutil.copy2(self.source / "instructions/COMMENTING.md", proj / "docs/COMMENTING.md")
        shutil.copytree(self.source / "skills/annotate-code", proj / ".agents/skills/annotate-code")
        self.edit_source("instructions/COMMENTING.md", "## 1.", "## 1. (revised)")
        self.edit_source("skills/annotate-code/SKILL.md", "## Steps", "## Steps (v2)")
        self.commit_source("v2")
        res = self.install(proj)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("## 1. (revised)", (proj / "docs/COMMENTING.md").read_text())
        self.assertIn("## Steps (v2)", (proj / ".agents/skills/annotate-code/SKILL.md").read_text())

    def test_file_the_project_wrote_itself_is_a_conflict(self) -> None:
        proj = self.project(files={"docs/COMMENTING.md": "our own, unrelated guide\n"})
        before = snapshot(proj)
        res = self.install(proj)
        self.assertEqual(res.returncode, 1)
        self.assertIn("not a version dexiotites shipped", res.stdout)
        self.assertEqual(snapshot(proj), before)

    def test_lost_executable_bit_is_repaired(self) -> None:
        proj = self.project()
        self.assertEqual(self.install(proj).returncode, 0)
        checker = proj / ".agents/skills/annotate-code/scripts/comment_diff_check.py"
        checker.chmod(0o644)
        self.assertEqual(self.install(proj, "--check").returncode, 1)
        self.assertEqual(self.install(proj).returncode, 0)
        self.assertTrue(os.access(checker, os.X_OK))


class TestLinterConfigs(InstallTestCase):
    def test_cargo_with_its_own_lints_or_a_workspace_is_left_alone(self) -> None:
        own = CARGO + '\n[lints.clippy]\npedantic = "warn"\n'
        workspace = '[workspace]\nmembers = ["a"]\n'
        for name, text in (("own", own), ("ws", workspace)):
            proj = self.project(name, {"Cargo.toml": text})
            res = self.install(proj)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertEqual((proj / "Cargo.toml").read_text(), text)
            self.assertIn("by hand", res.stdout)

    def test_cargo_block_is_replaced_in_place_on_update(self) -> None:
        proj = self.project()
        self.assertEqual(self.install(proj).returncode, 0)
        cargo = proj / "Cargo.toml"
        cargo.write_text(cargo.read_text() + '\n[profile.release]\nlto = true\n')
        self.edit_source("instructions/lint/rust-cargo-lints.toml",
                         'missing_panics_doc = "deny"', 'missing_panics_doc = "forbid"')
        self.commit_source("v2")
        self.assertEqual(self.install(proj).returncode, 0)
        text = cargo.read_text()
        self.assertEqual(text.count("[lints.rust]"), 1)
        self.assertIn('missing_panics_doc = "forbid"', text)
        self.assertTrue(text.startswith(CARGO))
        self.assertTrue(text.endswith('\n[profile.release]\nlto = true\n'))

    def test_python_and_kotlin_configs(self) -> None:
        proj = self.project(files={"app/main.py": '"""App."""\n', "android/A.kt": "class A\n"})
        res = self.install(proj)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual((proj / "ruff.toml").read_bytes(),
                         (self.source / "instructions/lint/ruff-docstrings.toml").read_bytes())
        self.assertTrue((proj / "config/detekt/detekt-comments.yml").is_file())
        self.assertIn("Kotlin", res.stdout)

    def test_existing_linter_configs_are_never_touched(self) -> None:
        files = {"a.py": "x = 1\n", "b.lua": "print(1)\n",
                 "pkg/pyproject.toml": "[tool.ruff]\nline-length = 100\n",
                 ".luarc.json": '{"runtime.version": "Lua 5.4"}\n'}
        proj = self.project(files=files)
        res = self.install(proj)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertFalse((proj / "ruff.toml").exists())
        self.assertEqual((proj / ".luarc.json").read_text(), files[".luarc.json"])
        self.assertEqual(res.stdout.count("by hand"), 2)
        self.assertNotIn("ruff.toml", json.loads((proj / ".dexiotites.json").read_text())["files"])

    def test_no_lint_removes_what_was_installed_and_lint_restores_it(self) -> None:
        proj = self.project(files={"Cargo.toml": CARGO, "src/main.rs": "fn main() {}\n", "a.lua": "print(1)\n"})
        self.assertEqual(self.install(proj).returncode, 0)
        with_lint = snapshot(proj)
        self.assertEqual(self.install(proj, "--no-lint").returncode, 0)
        self.assertFalse((proj / ".luarc.json").exists())
        self.assertEqual((proj / "Cargo.toml").read_text(), CARGO)
        self.assertEqual(self.install(proj).returncode, 0)          # the choice is remembered
        self.assertFalse((proj / ".luarc.json").exists())
        self.assertEqual(self.install(proj, "--lint").returncode, 0)
        self.assertEqual(snapshot(proj), with_lint)


class TestOtherWaysToRunIt(InstallTestCase):
    def test_piped_script_clones_the_source_and_installs(self) -> None:
        proj = self.project()
        env = {**os.environ, "DEXIOTITES_URL": str(self.source)}
        with (self.source / "install.py").open("rb") as script:
            res = subprocess.run([sys.executable, "-"], stdin=script, cwd=proj, env=env,
                                 capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue((proj / ".agents/skills/annotate-code/SKILL.md").is_file())
        self.assertEqual(json.loads((proj / ".dexiotites.json").read_text())["commit"],
                         git(self.source, "rev-parse", "HEAD").strip())

    def test_git_submodule_as_the_source(self) -> None:
        # dexiotites vendored as a submodule, installer run from inside it. The project must end
        # up self-contained: a clone that never fetches the submodule still has a working install.
        proj = self.project()
        git(proj, "-c", "protocol.file.allow=always", "submodule", "add", "-q",
            str(self.source), ".dexiotites")
        res = subprocess.run([sys.executable, ".dexiotites/install.py"], cwd=proj,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertFalse((proj / "ruff.toml").exists(), "submodule's Python must not count as the project's")
        self.assertFalse((proj / "config").exists(), "submodule's Kotlin fixtures must not count either")
        git(proj, "add", "-A")
        git(proj, "commit", "-q", "-m", "add dexiotites")

        clone = self.tmp / "clone"
        git(self.tmp, "clone", "-q", str(proj), str(clone))          # no --recurse-submodules
        self.assertEqual(list((clone / ".dexiotites").iterdir()), [])
        self.assertTrue((clone / "docs/COMMENTING.md").is_file())
        checker = clone / ".claude/skills/annotate-code/scripts/comment_diff_check.py"
        ok = subprocess.run([sys.executable, str(checker), "--strict", "src/main.rs"],
                            cwd=clone, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)


class TestExtensionTables(InstallTestCase):
    """The README's claim that one table entry in install.py adds a linter or a harness."""

    def test_one_lint_config_entry_supports_a_new_language(self) -> None:
        (self.source / "instructions/lint/godoc-lint.yml").write_text("rules: [exported]\n")
        self.edit_source("install.py", "LINT_CONFIGS = (\n",
                         'LINT_CONFIGS = (\n    LintConfig("Go", (".go",), "godoc-lint.yml", '
                         '".godoc-lint.yml", rivals=(".godoc-lint.yml",)),\n')
        self.commit_source("add Go")
        fresh = self.project("fresh", {"main.go": "package main\n"})
        res = self.install(fresh)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual((fresh / ".godoc-lint.yml").read_text(), "rules: [exported]\n")
        self.assertIn(".godoc-lint.yml", json.loads((fresh / ".dexiotites.json").read_text())["files"])
        before = snapshot(fresh)
        self.assertEqual(self.install(fresh).returncode, 0)
        self.assertEqual(snapshot(fresh), before)

        own = self.project("own", {"main.go": "package main\n", ".godoc-lint.yml": "rules: []\n"})
        res = self.install(own)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual((own / ".godoc-lint.yml").read_text(), "rules: []\n")
        self.assertIn("Go: existing linter config", res.stdout)

        rust_only = self.project("rust-only")
        self.assertEqual(self.install(rust_only).returncode, 0)
        self.assertFalse((rust_only / ".godoc-lint.yml").exists())

    def test_one_harness_entry_supports_a_new_harness(self) -> None:
        self.edit_source("install.py", "HARNESSES = (\n",
                         'HARNESSES = (\n'
                         '    Harness("Importer", rules_file="IMPORTER.md", import_line="!include AGENTS.md", '
                         'skills_dir=".importer/tools/skills"),\n'
                         '    Harness("Linker", rules_file=".linker/RULES.md"),\n')
        self.commit_source("add two harnesses")
        proj = self.project(files={"Cargo.toml": CARGO, "src/main.rs": "fn main() {}\n",
                                   "IMPORTER.md": "House rules.\n"})
        res = self.install(proj)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        # A harness with an import syntax: the line is added, existing content kept, skills linked.
        self.assertEqual((proj / "IMPORTER.md").read_text(), "!include AGENTS.md\n\nHouse rules.\n")
        self.assertEqual(os.readlink(proj / ".importer/tools/skills/annotate-code"),
                         "../../../.agents/skills/annotate-code")
        self.assertTrue((proj / ".importer/tools/skills/annotate-code/SKILL.md").is_file())
        # A harness without one: its rules file is a symlink that resolves to AGENTS.md.
        self.assertEqual(os.readlink(proj / ".linker/RULES.md"), "../AGENTS.md")
        self.assertIn(MARK, (proj / ".linker/RULES.md").read_text())
        # Claude Code's entry still works alongside them.
        self.assertEqual((proj / "CLAUDE.md").read_text(), "@AGENTS.md\n")
        before = snapshot(proj)
        self.assertEqual(self.install(proj).returncode, 0)
        self.assertEqual(snapshot(proj), before)

    def test_rules_file_in_the_way_of_a_symlink_is_left_alone(self) -> None:
        self.edit_source("install.py", "HARNESSES = (\n",
                         'HARNESSES = (\n    Harness("Linker", rules_file="RULES.md"),\n')
        self.commit_source("add a harness")
        proj = self.project(files={"RULES.md": "Our own rules.\n"})
        res = self.install(proj)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual((proj / "RULES.md").read_text(), "Our own rules.\n")
        self.assertIn("Linker will not load the commenting rules", res.stdout)


if __name__ == "__main__":
    unittest.main()
