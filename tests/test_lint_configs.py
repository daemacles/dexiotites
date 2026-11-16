"""Integration tests for the doc-linter configs in instructions/lint/.

Each test copies a compliant ("good") and a non-compliant ("bad") fixture project from
tests/fixtures/lint/ into a temporary folder, installs the distributed config there, runs
the language's finish-gate command from COMMENTING.md section 8, and expects the good
project to pass and the bad one to fail. A test is skipped when its tool isn't installed:
    Kotlin  detekt 2.0 CLI: `detekt` on PATH, or DETEKT_CLI_JAR=<path to detekt-cli-*-all.jar>
    Rust    cargo with clippy
    Python  ruff
    Lua     lua-language-server
"""

from __future__ import annotations

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
LINT = REPO_ROOT / "instructions" / "lint"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "lint"


def _run(cmd: list[str] | str, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command (a string runs through the shell) and capture its output."""
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600, env=env,
                          shell=isinstance(cmd, str))


def gate_commands(language: str) -> list[str]:
    """Return the finish-gate commands COMMENTING.md section 8 gives for `language`.

    The tests run these exact strings, so the commands agents are told to run are the ones
    proven against the fixtures.
    """
    guide = (REPO_ROOT / "instructions" / "COMMENTING.md").read_text(encoding="utf-8")
    section = guide.split("\n## 8.", 1)[1].split("\n## ", 1)[0]
    for line in section.splitlines():
        cells = line.split("|")
        if len(cells) >= 4 and cells[1].strip() == language:
            return re.findall(r"`([^`]+)`", cells[3])
    raise AssertionError(f"COMMENTING.md section 8 has no gate row for {language}")


def _detekt_cmd() -> list[str] | None:
    if shutil.which("detekt"):
        return ["detekt"]
    jar = os.environ.get("DETEKT_CLI_JAR")
    if jar and Path(jar).is_file() and shutil.which("java"):
        return ["java", "-jar", jar]
    return None


class TestDocLinterConfigs(unittest.TestCase):
    def _copy(self, lang: str, case: str, tmp: str) -> Path:
        dest = Path(tmp) / f"{lang}-{case}"
        shutil.copytree(FIXTURES / lang / case, dest)
        return dest

    @unittest.skipUnless(_detekt_cmd(), "detekt CLI not available (set DETEKT_CLI_JAR)")
    def test_kotlin_detekt(self) -> None:
        cmd = _detekt_cmd()
        assert cmd is not None
        with tempfile.TemporaryDirectory() as tmp:
            for case, should_pass in (("good", True), ("bad", False)):
                proj = self._copy("kotlin", case, tmp)
                res = _run(cmd + ["--input", str(proj), "--config", str(LINT / "detekt-comments.yml"),
                                  "--build-upon-default-config"], proj)
                self.assertEqual(res.returncode == 0, should_pass, f"{case}:\n{res.stdout}{res.stderr}")
                if not should_pass:
                    for rule in ("UndocumentedPublicClass", "UndocumentedPublicFunction",
                                 "UndocumentedPublicProperty", "OutdatedDocumentation"):
                        self.assertIn(rule, res.stdout + res.stderr)

    @unittest.skipUnless(shutil.which("cargo") and _run(["cargo", "clippy", "--version"], REPO_ROOT).returncode == 0,
                         "cargo clippy not available")
    def test_rust_clippy_and_rustdoc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for case, should_pass in (("good", True), ("bad", False)):
                proj = self._copy("rust", case, tmp)
                with (proj / "Cargo.toml").open("a", encoding="utf-8") as f:
                    f.write("\n" + (LINT / "rust-cargo-lints.toml").read_text(encoding="utf-8"))
                env = dict(os.environ, CARGO_TARGET_DIR=str(Path(tmp) / "target"))
                clippy_cmd, doc_cmd = gate_commands("Rust")
                clippy = _run(clippy_cmd, proj, env)
                doc = _run(doc_cmd, proj, env)
                passed = clippy.returncode == 0 and doc.returncode == 0
                self.assertEqual(passed, should_pass, f"{case}:\n{clippy.stderr}{doc.stderr}")
                if not should_pass:
                    # Each shipped lint must be reported as an error, not merely a warning.
                    for finding in ("missing documentation for", "missing `# Errors` section",
                                    "missing `# Panics` section", "missing a `# Safety` section",
                                    "unsafe block missing a safety comment"):
                        self.assertRegex(clippy.stderr, rf"(?m)^error: .*{re.escape(finding)}")
                    self.assertIn("unresolved link", doc.stderr)
                else:
                    # The good fixture has a clippy style warning: the gate must show it, not fail on it.
                    self.assertIn("needless_return", clippy.stderr)

    @unittest.skipUnless(shutil.which("ruff"), "ruff not available")
    def test_python_ruff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for case, should_pass in (("good", True), ("bad", False)):
                proj = self._copy("python", case, tmp)
                shutil.copy(LINT / "ruff-docstrings.toml", proj / "ruff.toml")
                (gate,) = gate_commands("Python")
                res = _run(gate, proj, dict(os.environ, RUFF_NO_CACHE="true"))
                self.assertEqual(res.returncode == 0, should_pass, f"{case}:\n{res.stdout}{res.stderr}")
                if not should_pass:
                    for code in ("D100", "D103", "D417"):
                        self.assertIn(code, res.stdout)

    @unittest.skipUnless(shutil.which("lua-language-server"), "lua-language-server not available")
    def test_lua_luals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for case, should_pass in (("good", True), ("bad", False)):
                proj = self._copy("lua", case, tmp)
                shutil.copy(LINT / "luarc-docs.json", proj / ".luarc.json")
                (gate,) = gate_commands("Lua")
                res = _run(f"{gate} --logpath={Path(tmp) / 'log'}", proj)
                self.assertEqual(res.returncode == 0, should_pass, f"{case}:\n{res.stdout}{res.stderr}")


if __name__ == "__main__":
    unittest.main()
