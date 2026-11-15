"""Unit tests for skills/annotate-code/scripts/comment_diff_check.py.

Covers lexical and AST edge cases across Kotlin, Rust, and Python, plus CLI
exit-code contracts (including `--strict`) in temporary git repositories.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "skills" / "annotate-code" / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "comment_diff_check.py"
sys.path.insert(0, str(SCRIPT_DIR))

import comment_diff_check as cdc  # noqa: E402


class TestKotlinStrip(unittest.TestCase):
    def test_multiline_param_wrapping_and_constructor_kdoc(self) -> None:
        before = "data class Point(val x: Float, val y: Float)\nval z = compute(a, b)\n"
        after = """/* File header. */
/** 2D point. */
data class Point(
    /** Eastward offset (m). */
    val x: Float,
    /** Northward offset (m). */
    val y: Float
)
val z = compute(
    a, // meters
    b  // seconds
)
"""
        self.assertEqual(cdc.strip_c_like(before, rust=False), cdc.strip_c_like(after, rust=False))

    def test_kotlin_template_with_nested_url_string_detects_code_change(self) -> None:
        base = 'val u = "url=${build("https://example.com")}"\nval y = 1\n'
        comment_added = 'val u = "url=${build("https://example.com")}"\n// explain y\nval y = 1\n'
        inner_comment = 'val u = "url=${ /* endpoint */ build("https://example.com") }"\nval y = 1\n'
        mutated_url = 'val u = "url=${build("https://other.example.com")}"\nval y = 1\n'

        self.assertEqual(cdc.strip_c_like(base, False), cdc.strip_c_like(comment_added, False))
        self.assertEqual(cdc.strip_c_like(base, False), cdc.strip_c_like(inner_comment, False))
        self.assertNotEqual(cdc.strip_c_like(base, False), cdc.strip_c_like(mutated_url, False))

    def test_kotlin_raw_and_multi_dollar_strings(self) -> None:
        base = 'val raw = """say "hi" ${x + 1}""""\nval md = $$"literal ${notInterp} $${x + 1}"\n'
        commented = (
            '// doc\nval raw = """say "hi" ${ /* add */ x + 1 }""""\n'
            'val md = $$"literal ${notInterp} $${ /* same */ x + 1 }"\n'
        )
        changed_literal = (
            'val raw = """say "hi" ${x + 1}""""\n'
            'val md = $$"CHANGED ${notInterp} $${x + 1}"\n'
        )
        self.assertEqual(cdc.strip_c_like(base, False), cdc.strip_c_like(commented, False))
        self.assertNotEqual(cdc.strip_c_like(base, False), cdc.strip_c_like(changed_literal, False))

    def test_nested_block_comments_and_char_literals(self) -> None:
        base = "val q = '\\''\nval b = '\\\\'\nval u = '\\u0027'\n"
        after = "/* outer /* nested */ still comment */\n" + base
        self.assertEqual(cdc.strip_c_like(base, False), cdc.strip_c_like(after, False))


class TestRustStrip(unittest.TestCase):
    def test_lifetimes_and_raw_strings(self) -> None:
        base = """pub fn parse<'a, 'b>(s: &'a str) -> &'a str {
    let r = r#"not // a comment"#;
    let b = br#"also /* not */ a comment"#;
    let c = cr#"cstr // literal"#;
    s
}
"""
        after = """//! Module docs.
/// Parses `s`.
pub fn parse<'a, 'b>(
    s: &'a str // input slice
) -> &'a str {
    let r = r#"not // a comment"#;
    let b = br#"also /* not */ a comment"#;
    let c = cr#"cstr // literal"#;
    s
}
"""
        mutated = base.replace("cstr // literal", "cstr // CHANGED")
        self.assertEqual(cdc.strip_c_like(base, True), cdc.strip_c_like(after, True))
        self.assertNotEqual(cdc.strip_c_like(base, True), cdc.strip_c_like(mutated, True))


class TestPythonStrip(unittest.TestCase):
    def test_docstrings_and_dataclass_attribute_docstrings(self) -> None:
        base = """from dataclasses import dataclass

MAX_SPEED_MPS = 1.5

@dataclass
class Pose:
    x: float
    y: float = 0.0

    def reset(self) -> None:
        pass
"""
        after = '''"""Pose types."""
from dataclasses import dataclass

MAX_SPEED_MPS = 1.5
"""Upper walk-speed threshold in m/s."""

@dataclass
class Pose:
    """2D pose on the ground plane."""
    x: float
    """Eastward offset in meters."""
    y: float = 0.0
    """Northward offset in meters."""

    def reset(self) -> None:
        """Reset pose."""
'''
        self.assertEqual(cdc.strip_python(base), cdc.strip_python(after))

    def test_python_code_change_reports_ast_divergence(self) -> None:
        a = cdc.strip_python("x = 1\n")
        b = cdc.strip_python("x = 2\n")
        self.assertNotEqual(a, b)
        diff = cdc.first_divergence("ast", a, b)
        self.assertIn("base AST:", diff)
        self.assertIn("current AST:", diff)


class TestCliGitIntegration(unittest.TestCase):
    def test_strict_flag_catches_skip_and_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp, check=True)

            kt = Path(tmp) / "A.kt"
            java = Path(tmp) / "B.java"
            kt.write_text("fun f(x: Int) = x\n", encoding="utf-8")
            java.write_text("class B {}\n", encoding="utf-8")
            subprocess.run(["git", "add", "A.kt", "B.java"], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp, check=True)

            # Comment-only edit on Kotlin passes --strict.
            kt.write_text("/** Identity. */\nfun f(x: Int) = x\n", encoding="utf-8")
            res_ok = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--strict", "A.kt"],
                cwd=tmp,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_ok.returncode, 0, res_ok.stdout + res_ok.stderr)
            self.assertIn("OK", res_ok.stdout)

            # Unsupported extension passes non-strict (SKIP) but fails --strict.
            java.write_text("/** Docs. */\nclass B {}\n", encoding="utf-8")
            res_non_strict = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "B.java"],
                cwd=tmp,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_non_strict.returncode, 0)
            self.assertIn("SKIP", res_non_strict.stdout)

            res_strict_skip = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--strict", "B.java"],
                cwd=tmp,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_strict_skip.returncode, 1)

            # Untracked file fails --strict.
            untracked = Path(tmp) / "New.kt"
            untracked.write_text("val n = 1\n", encoding="utf-8")
            res_strict_new = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--strict", "New.kt"],
                cwd=tmp,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_strict_new.returncode, 1)
            self.assertIn("NEW", res_strict_new.stdout)


if __name__ == "__main__":
    unittest.main()
