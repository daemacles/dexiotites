"""Repository-wide structural and hygiene checks for `dexiotites`.

Acts as the mechanical oracle paired with `MAINTENANCE.md`, verifying invariants
across all skills, embedded scripts, documentation tables, and tracked text files
so lower-tier models cannot introduce structural drift.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
LINT_DIR = REPO_ROOT / "instructions" / "lint"
CHECKER_DIR = SKILLS_DIR / "annotate-code" / "scripts"

EMBEDDED_RE = re.compile(
    r"<!-- embedded-file: ([^\s>]+) -->\n```[^\n]*\n(.*?)\n```",
    re.DOTALL,
)


def _parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse top-level YAML `key: value` strings (including `>-`/`|` blocks) from `SKILL.md`.

    Args:
        text: Full UTF-8 contents of a `SKILL.md` file.

    Returns:
        Mapping of frontmatter keys to stripped string values, or `None` if the file
        does not open with a `--- ... ---` YAML frontmatter block.
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None

    fields: dict[str, str] = {}
    current_key: str | None = None
    block_lines: list[str] = []

    def flush_block() -> None:
        nonlocal current_key
        if current_key is not None and block_lines:
            fields[current_key] = " ".join(line.strip() for line in block_lines if line.strip())
            block_lines.clear()
            current_key = None

    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if line[0] in (" ", "\t") and current_key is not None:
            block_lines.append(line)
            continue
        flush_block()
        if ":" not in line:
            continue
        key, raw_val = line.split(":", 1)
        key = key.strip()
        val = raw_val.strip()
        if val in ("", ">", ">-", "|", "|-"):
            current_key = key
        else:
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            fields[key] = val

    flush_block()
    return fields


class TestRepoHygiene(unittest.TestCase):
    """Enforces mechanical repository invariants across `skills/`, `instructions/`, and root docs."""

    def test_every_skill_has_valid_frontmatter(self) -> None:
        skill_dirs = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())
        self.assertGreater(len(skill_dirs), 0, "Expected at least one skill in skills/")
        for skill_dir in skill_dirs:
            skill_md = skill_dir / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"Missing SKILL.md in {skill_dir.name}")
            fm = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            self.assertIsNotNone(fm, f"{skill_md} must start with YAML frontmatter (--- ... ---)")
            assert fm is not None
            self.assertEqual(
                fm.get("name"),
                skill_dir.name,
                f"{skill_md}: frontmatter name {fm.get('name')!r} must match directory {skill_dir.name!r}",
            )
            desc = fm.get("description", "")
            self.assertGreaterEqual(
                len(desc),
                20,
                f"{skill_md}: frontmatter description is missing or too short",
            )

    def test_embedded_files_match_extracted_copies_and_shebangs_are_executable(self) -> None:
        checked_any = False
        for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            text = skill_md.read_text(encoding="utf-8")
            for rel_path, body in EMBEDDED_RE.findall(text):
                checked_any = True
                target = skill_md.parent / rel_path
                self.assertTrue(
                    target.is_file(),
                    f"{skill_md} declares embedded-file {rel_path!r}, but {target} does not exist",
                )
                expected = body + "\n"
                actual = target.read_text(encoding="utf-8")
                self.assertEqual(
                    expected,
                    actual,
                    f"Embedded block in {skill_md} differs from {target}; update both together",
                )
        self.assertTrue(checked_any, "Expected at least one embedded-file check to run")

        # Every `#!` script anywhere under skills/ must be executable.
        for path in sorted(SKILLS_DIR.rglob("*")):
            if path.is_file() and not path.is_symlink():
                raw = path.read_bytes()
                if raw.startswith(b"#!"):
                    self.assertTrue(
                        path.stat().st_mode & 0o111,
                        f"Script with shebang lacks +x permission: {path}",
                    )

    def test_no_pycache_or_bytecode_inside_skills(self) -> None:
        bad = [
            p
            for p in SKILLS_DIR.rglob("*")
            if p.name == "__pycache__" or p.suffix in {".pyc", ".pyo"}
        ]
        self.assertEqual(bad, [], f"Bytecode artifacts must not exist inside skills/: {bad}")

    def test_readme_skills_tables_match_skills_directory(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        skills_section = readme.split("\n## Skills\n", 1)[1]
        listed_in_readme = set(re.findall(r"^\|\s*`([a-z0-9-]+)`\s*\|", skills_section, re.MULTILINE))
        actual_skill_dirs = {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()}
        self.assertEqual(
            listed_in_readme,
            actual_skill_dirs,
            "Skills listed under `## Skills` in README.md must match `skills/*/` directories",
        )

    def test_readme_skills_tables_list_external_requirements(self) -> None:
        """Every README skills table has a filled-in External requirements column.

        MAINTENANCE.md §1 (dependency audit) has authors list each skill's connectors, CLI
        tools and external skills in that column.
        """
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        skills_section = readme.split("\n## Skills\n", 1)[1].split("\n## ", 1)[0]
        headers = re.findall(r"^\|\s*Skill\s*\|.*$", skills_section, re.MULTILINE)
        self.assertTrue(headers, "No skills table found under `## Skills` in README.md")
        for header in headers:
            self.assertEqual(
                [c.strip() for c in header.strip().strip("|").split("|")],
                ["Skill", "What it does", "External requirements"],
                f"Skills table needs an External requirements column: {header}",
            )
        for row in re.findall(r"^\|\s*`[a-z0-9-]+`\s*\|.*$", skills_section, re.MULTILINE):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            self.assertEqual(len(cells), 3, f"Skills table row needs exactly 3 cells: {row}")
            self.assertTrue(all(cells), f"Skills table row has an empty cell: {row}")

    def test_all_text_files_end_with_newline_and_json_parses(self) -> None:
        tracked = subprocess.run(
            ["git", "--no-optional-locks", "ls-files"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        candidates = {REPO_ROOT / rel for rel in tracked}
        for folder in ("instructions", "skills", "tests", ".agents"):
            candidates.update((REPO_ROOT / folder).rglob("*"))
        for doc in ("AGENTS.md", "CLAUDE.md", "MAINTENANCE.md", "README.md", ".gitignore"):
            candidates.add(REPO_ROOT / doc)

        for path in sorted(candidates):
            if "__pycache__" in path.parts or not path.exists():
                continue
            if path.is_dir() or path.is_symlink() or path.name == ".gitkeep":
                continue
            data = path.read_bytes()
            if data:
                self.assertTrue(
                    data.endswith(b"\n"),
                    f"File missing trailing newline: {path.relative_to(REPO_ROOT)}",
                )
            if path.suffix == ".json":
                try:
                    json.loads(data.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    self.fail(f"Invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}")


    def test_checker_languages_are_documented_everywhere(self) -> None:
        """Every extension the checker supports appears wherever supported types are listed."""
        sys.path.insert(0, str(CHECKER_DIR))
        try:
            import comment_diff_check as cdc
        finally:
            sys.path.remove(str(CHECKER_DIR))
        supported = sorted(cdc.C_LIKE | cdc.LUA | {".py"})
        for ext in supported:
            self.assertIsNotNone(cdc.code_only("x" + ext, ""), f"code_only does not handle {ext}")
        places = {
            "README.md": (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
            "skills/annotate-code/SKILL.md": (SKILLS_DIR / "annotate-code" / "SKILL.md").read_text(encoding="utf-8"),
        }
        for name, text in places.items():
            for ext in supported:
                self.assertIn(f"`{ext}`", text, f"{name} does not list supported extension {ext}")

    def test_lint_configs_are_documented_and_tested(self) -> None:
        """Each file in instructions/lint/ is referenced by the README, the guide, and the lint tests."""
        configs = sorted(p.name for p in LINT_DIR.iterdir() if p.is_file())
        self.assertGreater(len(configs), 0)
        texts = {
            "README.md": (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
            "instructions/COMMENTING.md": (REPO_ROOT / "instructions" / "COMMENTING.md").read_text(encoding="utf-8"),
            "tests/test_lint_configs.py": (REPO_ROOT / "tests" / "test_lint_configs.py").read_text(encoding="utf-8"),
        }
        for cfg in configs:
            for name, text in texts.items():
                self.assertIn(cfg, text, f"{name} does not mention instructions/lint/{cfg}")

    def test_toml_files_parse(self) -> None:
        """TOML configs parse (needs Python 3.11+ for tomllib; skipped otherwise)."""
        try:
            import tomllib
        except ImportError:
            self.skipTest("tomllib needs Python 3.11+")
        for path in [*LINT_DIR.glob("*.toml"), REPO_ROOT / "ruff.toml"]:
            with path.open("rb") as f:
                tomllib.load(f)

    @unittest.skipUnless(shutil.which("ruff"), "ruff not available")
    def test_repo_python_passes_its_own_doc_linter(self) -> None:
        """This repo's Python meets the same docstring gate it ships (instructions/lint/)."""
        res = subprocess.run(["ruff", "check", "--no-cache", "--select", "D", "."], cwd=REPO_ROOT,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
