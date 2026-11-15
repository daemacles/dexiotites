"""Unit tests for skills/annotate-code/scripts/comment_diff_check.py.

Covers lexical and AST edge cases across Kotlin, Rust, Python, and Lua, plus CLI
exit-code contracts (including `--strict`) in temporary git repositories.
"""

from __future__ import annotations

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

    def test_line_break_that_splits_a_statement_is_a_code_change(self) -> None:
        # `val x = a` / `+ b` parses as two statements in Kotlin, so this "rewrap" changes
        # behavior even though the tokens are the same.
        base = "fun f(a: Int, b: Int): Int {\n    val x = a + b\n    return x\n}\n"
        rewrapped = "fun f(a: Int, b: Int): Int {\n    val x = a // first operand\n        + b\n    return x\n}\n"
        self.assertNotEqual(cdc.strip_c_like(base, False), cdc.strip_c_like(rewrapped, False))

    def test_line_break_inside_lambda_within_call_is_meaningful(self) -> None:
        base = "val r = run({ a + b })\n"
        rewrapped = "val r = run({ a\n    + b })\n"
        self.assertNotEqual(cdc.strip_c_like(base, False), cdc.strip_c_like(rewrapped, False))

    def test_comment_lines_between_statements_and_chained_calls_are_comment_only(self) -> None:
        base = "class A {\n    fun f() {\n        val y = list\n            .map { it }\n        g(y)\n    }\n}\n"
        after = (
            "/** Holder for f. */\nclass A {\n\n    /** Maps then forwards. */\n    fun f() {\n"
            "        val y = list // source\n            // transform each item\n"
            "            .map { it }\n\n        g(y) // forward\n    }\n}\n"
        )
        self.assertEqual(cdc.strip_c_like(base, False), cdc.strip_c_like(after, False))


class TestLuaStrip(unittest.TestCase):
    def test_doc_annotations_and_long_comments_are_comment_only(self) -> None:
        base = (
            "local M = {}\n"
            "function M.range(h, p)\n  return h / math.sin(p)\nend\n"
            "return M\n"
        )
        after = (
            "--[==[\nFile header: geometry helpers. Mentions ]] without closing.\n]==]\n"
            "local M = {} -- module table\n\n"
            "--- Returns the slant range.\n"
            "---@param h number Camera height in meters.\n"
            "---@param p number Pitch in radians.\n"
            "---@return number range_m Slant range in meters.\n"
            "function M.range(\n  h, -- meters\n  p  -- radians\n)\n"
            "  --[[ implementation note ]] return h / math.sin(p)\nend\n"
            "return M\n"
        )
        self.assertEqual(cdc.strip_lua(base), cdc.strip_lua(after))

    def test_floor_division_is_code_not_comment(self) -> None:
        base = "local q = a // b -- floor\n"
        changed = "local q = a / b -- floor\n"
        self.assertNotEqual(cdc.strip_lua(base), cdc.strip_lua(changed))
        self.assertIn("/", cdc.strip_lua(base))

    def test_strings_containing_comment_markers_are_preserved(self) -> None:
        base = 'local u = "http://x -- y"\nlocal s = [[-- not a comment]]\nlocal t = [=[a]]b]=]\n'
        for mutated in (
            base.replace("-- y", "-- z"),
            base.replace("not a comment", "NOT A COMMENT"),
            base.replace("a]]b", "a]]c"),
        ):
            self.assertNotEqual(cdc.strip_lua(base), cdc.strip_lua(mutated))

    def test_single_bracket_after_dashes_is_a_line_comment(self) -> None:
        base = "local a = 1\nlocal b = 2\n"
        after = "local a = 1 --[ not a long comment\nlocal b = 2\n"
        self.assertEqual(cdc.strip_lua(base), cdc.strip_lua(after))

    def test_escapes_including_z_continuation(self) -> None:
        base = 'local s = "a\\"b\\z\n     c"\nlocal t = \'it\\\'s\'\nlocal n = 1\n'
        after = '-- strings\n' + base.replace("local n = 1", "local n = 1 -- one")
        changed = base.replace("local n = 1", "local n = 2")
        self.assertEqual(cdc.strip_lua(base), cdc.strip_lua(after))
        self.assertNotEqual(cdc.strip_lua(base), cdc.strip_lua(changed))


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

            # Lua is supported: a comment-only edit passes --strict, a code edit fails.
            lua = Path(tmp) / "m.lua"
            lua.write_text("local M = {}\nreturn M\n", encoding="utf-8")
            subprocess.run(["git", "add", "m.lua"], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "lua"], cwd=tmp, check=True)
            lua.write_text("--- Module table.\nlocal M = {}\nreturn M\n", encoding="utf-8")
            res_lua_ok = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--strict", "m.lua"],
                cwd=tmp,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_lua_ok.returncode, 0, res_lua_ok.stdout + res_lua_ok.stderr)
            lua.write_text("local M = { x = 1 }\nreturn M\n", encoding="utf-8")
            res_lua_bad = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--strict", "m.lua"],
                cwd=tmp,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_lua_bad.returncode, 1)
            self.assertIn("FAIL", res_lua_bad.stdout)

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
