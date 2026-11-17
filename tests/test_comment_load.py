"""Tests for comment_load.py, the advisory counter for the guide's sentence rules (section 10).

Each case feeds a small source file through the script's functions and checks which warnings
a sentence earns. The counter must flag the constructions the guide names, stay quiet on
comments written in the guide's voice, and never fail a run unless asked to.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "annotate-code" / "scripts" / "comment_load.py"
spec = importlib.util.spec_from_file_location("comment_load", SCRIPT)
comment_load = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comment_load)

DENSE_KOTLIN = '''
/**
 * Enforces [ActivityInfo.LANDSCAPE] and registers a [DisplayListener] so flips between
 * [Surface.ROTATION_90] and [Surface.ROTATION_270] update the model (`FLAG_KEEP_SCREEN_ON`).
 *
 * Copies pixels into [workerPixelCopy] at `4.0 Hz` per `.agents/rules/camera.md` §4.
 *
 * @param rate Capture rate in `Hz` (clamped to `1.0..15.0`), see [DEFAULT_RATE] and [MAX_RATE].
 */
class Dense {
    private val workerPixelCopy = IntArray(4)
}
'''

PLAIN_KOTLIN = '''
/**
 * Saves image strips to disk while recording is on.
 *
 * A strip offered while the writer is busy is dropped, so the camera thread never waits.
 * Sessions may be started and stopped from any thread.
 *
 * Typical use:
 * ```
 * val logger = Logger(context)   // (not prose) `1.0` [x] [y] [z]
 * ```
 */
class Plain
'''


def warnings_for(suffix: str, source: str) -> tuple[int, list[str]]:
    """Run the counter on `source` saved with `suffix`; return sentence count and warning ids."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"sample{suffix}"
        path.write_text(source)
        total, _, lines = comment_load.report(path)
    return total, [line.split(": ")[1].split()[0] for line in lines]


class TestSentenceRules(unittest.TestCase):
    def test_dense_comment_earns_every_warning(self) -> None:
        _, found = warnings_for(".kt", DENSE_KOTLIN)
        self.assertEqual(sorted(set(found)), ["W1", "W2", "W3", "W4", "W5", "W6"])

    def test_comment_in_the_guides_voice_is_clean_and_examples_and_tags_are_ignored(self) -> None:
        total, found = warnings_for(".kt", PLAIN_KOTLIN)
        self.assertEqual(found, [])
        self.assertEqual(total, 3)
        # The @param line of the dense sample holds five code names and must not be counted.
        _, dense = warnings_for(".kt", DENSE_KOTLIN.split(" *\n * Copies")[0] + " */\nclass D")
        self.assertNotIn("W6", dense)

    def test_each_supported_language_is_read(self) -> None:
        rust = "/// Adds `a`, `b` and `c` (wrapping).\npub fn f() {}\n"
        python = 'def f():\n    """Return `_cache` size.\n\n    Args:\n        x: The `a`, `b`, `c` (ignored).\n    """\n'
        lua = "--- Sums [a], [b] and [c] values.\n---@param a number the `1`, `2`, `3` (ignored)\nfunction f() end\n"
        self.assertEqual(sorted(warnings_for(".rs", rust)[1]), ["W1", "W2", "W3"])
        self.assertEqual(sorted(warnings_for(".py", python)[1]), ["W1", "W6"])
        self.assertEqual(sorted(warnings_for(".lua", lua)[1]), ["W1", "W2"])

    def test_report_is_advisory_unless_a_limit_is_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dense = Path(tmp) / "Dense.kt"
            dense.write_text(DENSE_KOTLIN)
            other = Path(tmp) / "notes.md"
            other.write_text("# x\n")
            run = [sys.executable, str(SCRIPT)]
            plain = subprocess.run([*run, str(dense), str(other)], capture_output=True, text=True)
            self.assertEqual(plain.returncode, 0)
            self.assertIn("SCORE", plain.stdout)
            self.assertIn("SKIP", plain.stdout)
            self.assertRegex(plain.stdout, r"Dense\.kt:\d+: W2 ")
            limited = subprocess.run([*run, "--fail-over", "10", str(dense)], capture_output=True, text=True)
            self.assertEqual(limited.returncode, 1)


if __name__ == "__main__":
    unittest.main()
