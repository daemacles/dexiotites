#!/usr/bin/env python3
"""Check that the test suite notices the mistakes it exists to prevent.

This is mutation testing: break the code on purpose and see whether a test fails.

Each entry in `MUTATIONS` plants one fault in a scratch copy of this repository: either a
safety rule removed from `install.py`, or an edit to one file that leaves another file out of
step with it. The suite is then run on the copy. A fault the suite fails on is CAUGHT; one it
passes on SURVIVED, which means a test is missing or too weak. Faults marked `gap` are ones no
mechanical test is expected to catch, because they need a reader's judgment. They are listed
so the limits of the suite stay visible.

Usage:
    python3 tests/mutation_audit.py            run every mutation
    python3 tests/mutation_audit.py -k cargo   run mutations whose id or description contains "cargo"

Exit code 0 if every non-gap mutation is caught, 1 if any survives, 2 if the unmodified copy
does not pass, since the audit would then be meaningless. Not part of `unittest discover`: it
takes a few minutes. Run it after adding or changing a test, and add a mutation for each new invariant.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Fast modules first: the audit stops at the first module that fails.
MODULES = ["test_repo_hygiene", "test_sync_classify", "test_comment_diff_check", "test_comment_load",
           "test_install", "test_lint_configs"]

INSTALL = "install.py"
GUIDE = "instructions/COMMENTING.md"
SECTION = "instructions/AGENTS-commenting-section.md"
CHECKER = "skills/annotate-code/scripts/comment_diff_check.py"

# (id, description, file, text to find exactly once, replacement). A replacement of None
# deletes the file; `needs` names a CLI tool without which the mutation is skipped.
MUTATIONS: list[dict] = [
    # ---- installer safety rules -------------------------------------------------------
    dict(id="scan-dot-folders", why="installed tooling counted as the project's own code",
         file=INSTALL, old='if any(part.startswith(".") or part in SKIP_DIRS for part in parts[:-1]):',
         new="if any(part in SKIP_DIRS for part in parts[:-1]):"),
    dict(id="trust-any-file", why="any existing file treated as an old dexiotites version",
         file=INSTALL, old='return _git(source, "cat-file", "-e", blob).returncode == 0', new="return True"),
    dict(id="ignore-local-edits", why="a copy edited in the project is overwritten silently",
         file=INSTALL, old="elif rel in recorded and _sha256(cur) != recorded[rel]:", new="elif False:"),
    dict(id="write-despite-conflicts", why="safe changes applied although a conflict was found",
         file=INSTALL, old="    if conflicts:\n        print(", new="    if False:\n        print("),
    dict(id="force-does-nothing", why="--force leaves conflicts unresolved",
         file=INSTALL, old="    if force:\n", new="    if False:\n"),
    dict(id="check-writes", why="--check modifies the project",
         file=INSTALL, old="    if args.check:\n", new="    if False:\n"),
    dict(id="drop-project-heading", why="a project's numbered heading replaced by the template's",
         file=INSTALL, old="heading = inner[0] if inner and HEADING_RE.match(inner[0]) else template[0]",
         new="heading = template[0]"),
    dict(id="adopt-any-section", why="a customized Code Comments section replaced without --force",
         file=INSTALL, old='if _body("\\n".join(inner)) not in shipped_bodies(source):', new="if False:"),
    dict(id="write-through-claude-symlink", why="CLAUDE.md symlink edited through to its target",
         file=INSTALL,
         old='if path.is_symlink() or (path.exists() and (project / "AGENTS.md").resolve() == path.resolve()):',
         new="if False:"),
    dict(id="lose-exec-bit", why="installed checker script not executable",
         file=INSTALL, old="dst.chmod(0o755 if c.executable else 0o644)", new="dst.chmod(0o644)"),
    dict(id="manifest-churn", why="manifest rewritten when nothing in the project changed",
         file=INSTALL, old="    if content_changed or old_view != {k: new_manifest[k] for k in old_view}:",
         new="    if True:"),
    dict(id="clobber-cargo-lints", why="a project's own [lints] tables get a second set appended",
         file=INSTALL, old="    if LINTS_TABLE_RE.search(old):", new="    if False:"),
    dict(id="clobber-ruff-config", why="existing ruff configuration shadowed by a new ruff.toml",
         file=INSTALL, old="        if theirs:\n", new="        if False:\n"),
    dict(id="harness-link-ignores-depth", why="skill symlink target wrong for a harness with a deeper skills folder",
         file=INSTALL, old='target = os.path.relpath(f".agents/skills/{skill}", harness.skills_dir)',
         new='target = f"../../.agents/skills/{skill}"'),
    dict(id="lint-table-names-missing-template", why="a LINT_CONFIGS entry points at a config file that does not exist",
         file=INSTALL, old='LintConfig("Lua", (".lua",), "luarc-docs.json"', new='LintConfig("Lua", (".lua",), "luarc.json"'),
    dict(id="keep-dropped-files", why="files dexiotites stopped shipping stay in projects",
         file=INSTALL, old="        if _sha256(dst.read_bytes()) == recorded[rel]:", new="        if False:"),
    dict(id="install-into-self", why="installer run against the dexiotites repo itself",
         file=INSTALL, old="    if project.resolve() == source.resolve():", new="    if False:"),
    dict(id="guide-installed-elsewhere", why="guide installed where the instructions do not point",
         file=INSTALL, old='{"docs/COMMENTING.md": source', new='{"doc/COMMENTING.md": source'),
    dict(id="forget-extra-skills", why="a bare rerun drops skills added with --skill",
         file=INSTALL, old='sorted(set(manifest.get("skills", DEFAULT_SKILLS)) | set(skills or ()))',
         new="sorted(set(skills or DEFAULT_SKILLS))"),
    dict(id="commit-sweeps-in-user-work", why="uncommitted work in a file the installer edits gets committed",
         file=INSTALL, old="data = c.content if c.staged is None else c.staged", new="data = c.content"),
    dict(id="commit-through-the-real-index", why="files the user staged are committed or unstaged by the install",
         file=INSTALL, old='env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}',
         new="env = dict(os.environ)"),
    dict(id="dont-add-ignored", why="--dont-add commits anyway",
         file=INSTALL, old="    if args.dont_add:\n", new="    if False:\n"),
    dict(id="always-says-installed", why="update commits are labelled as first installs",
         file=INSTALL, old='verb = "updated" if', new='verb = "installed" if'),
    dict(id="check-misses-uncommitted-install", why="--check passes although the install is not committed",
         file=INSTALL, old="        if loose:\n", new="        if False:\n"),
    dict(id="commit-loses-exec-bit", why="checker script committed without its executable bit",
         file=INSTALL, old='mode = ("100755" if c.executable else "100644") if', new='mode = "100644" if'),
    # ---- one file edited, another left out of step ------------------------------------
    dict(id="renumber-guide", why="guide section 8 becomes something else; citations now point wrong",
         file=GUIDE, old="## 8. Enforcement with doc linters (Tier 1)", new="## 8. Glossary"),
    dict(id="rename-section-heading", why="AGENTS.md section heading the installer searches for is renamed",
         file=SECTION, old="## Code Comments (Purpose-First Documentation)", new="## Commenting rules"),
    dict(id="section-points-to-missing-path", why="AGENTS.md section names a skill folder that is not installed",
         file=SECTION, old="`.agents/skills/annotate-code/`", new="`.agents/skills/annotate/`"),
    dict(id="guide-gate-differs", why="guide's Python gate command changed, README and config not",
         file=GUIDE, old="| `ruff check --select D .` |", new="| `ruff check --select D,DOC .` |"),
    dict(id="readme-gate-differs", why="README's Rust gate command changed, guide not",
         file="README.md", old="| `cargo clippy --all-targets -- -D missing_docs` and", new="| `cargo clippy -- -D missing_docs` and"),
    dict(id="lint-config-renamed", why="a lint config is renamed; installer, README and guide still use the old name",
         file="instructions/lint/luarc-docs.json", rename="instructions/lint/luarc.json"),
    dict(id="checker-edited-alone", why="checker script edited without its embedded copy in SKILL.md",
         file=CHECKER, old='NL = "\\n"', new='NL = "\\n"  # edited'),
    dict(id="checker-new-language-undocumented", why="checker gains a file type the docs do not list",
         file=CHECKER, old='LUA = {".lua"}', new='LUA = {".lua", ".luau"}'),
    dict(id="readme-skill-row-removed", why="a skill disappears from the README tables",
         file="README.md", old="| `distill-spec` | Distills", new="| distill-spec | Distills"),
    dict(id="doc-names-missing-file", why="a doc refers to a test file that does not exist",
         file="AGENTS.md", old="`tests/test_repo_hygiene.py`", new="`tests/test_hygiene.py`"),
    dict(id="readme-link-broken", why="a README heading is renamed and links to it break",
         file="README.md", old="### Doc linters (Tier 1)", new="### Doc linters"),
    dict(id="skill-frontmatter-broken", why="a skill loses its name field",
         file="skills/distill-spec/SKILL.md", old='name: "distill-spec"\n', new=""),
    dict(id="rust-lints-weakened", why="shipped Rust config no longer flags undocumented items",
         file="instructions/lint/rust-cargo-lints.toml", old='undocumented_unsafe_blocks = "deny"',
         new='undocumented_unsafe_blocks = "warn"', needs="cargo"),
    dict(id="rust-gate-imports-style-policy", why="Rust gate goes back to failing on clippy style warnings",
         file=GUIDE, old="`cargo clippy --all-targets -- -D missing_docs`",
         new="`cargo clippy --all-targets -- -D warnings`", needs="cargo"),
    dict(id="ruff-convention-changed", why="shipped ruff config enforces a different docstring style than the guide",
         file="instructions/lint/ruff-docstrings.toml", old='convention = "google"',
         new='convention = "numpy"', needs="ruff"),
    dict(id="voice-counter-edited-alone", why="comment_load.py edited without its embedded copy in SKILL.md",
         file="skills/annotate-code/scripts/comment_load.py", old="if len(names) > 2:", new="if len(names) > 3:"),
    dict(id="voice-section-renumbered", why="the guide's Voice section stops being section 10, which the skill and counter cite",
         file=GUIDE, old="## 10. Voice: write for a reader with a small working memory", new="## 11. Voice"),
    # ---- known gaps: need a reader, not a test ----------------------------------------
    dict(id="rule-reworded-in-guide-only", gap=True,
         why="a rule's meaning changes in the guide while the AGENTS.md summary keeps the old wording "
             "(MAINTENANCE.md section 2 asks for this cross-check by hand)",
         file=GUIDE, old="## 3. Prohibited comments", new="## 3. Prohibited comments\n\nChange history is now allowed.\n"),
    dict(id="skill-step-edited-in-repo-only", gap=True,
         why="a skill is edited here but not in the Claude account (caught later by sync-skills-repo's "
             "classifier, not by these tests)",
         file="skills/distill-spec/SKILL.md", old="## Why this skill exists", new="## Why this skill exists now"),
]


def run_suite(repo: Path) -> str | None:
    """Run the test modules on a copy of the repository.

    Args:
        repo: Root of the scratch copy.

    Returns:
        The first failing test's name, or None if every module passes.
    """
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for module in MODULES:
        res = subprocess.run([sys.executable, "-m", "unittest", "-f", f"tests.{module}"],
                             cwd=repo, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            failing = [line.split()[1] for line in res.stderr.splitlines()
                       if line.startswith(("FAIL:", "ERROR:"))]
            return f"{module}.{failing[0]}" if failing else f"{module} (crashed)"
    return None


def apply_mutation(repo: Path, m: dict) -> dict[Path, bytes | None]:
    """Plant one mutation in the scratch copy.

    Args:
        repo: Root of the scratch copy.
        m: The entry from `MUTATIONS` to apply.

    Returns:
        The original bytes of each path touched, for `restore`. None marks a path that did
        not exist before.

    Raises:
        ValueError: if the text to replace does not occur exactly once (the mutation is stale).
    """
    path = repo / m["file"]
    saved: dict[Path, bytes | None] = {path: path.read_bytes()}
    if "rename" in m:
        target = repo / m["rename"]
        saved[target] = None
        path.rename(target)
        return saved
    text = path.read_text(encoding="utf-8")
    if text.count(m["old"]) != 1:
        raise ValueError(f"{m['id']}: expected exactly one match in {m['file']}, found {text.count(m['old'])}")
    path.write_text(text.replace(m["old"], m["new"]), encoding="utf-8")
    return saved


def restore(saved: dict[Path, bytes | None]) -> None:
    """Undo a planted mutation, keeping each restored file's permission bits.

    Args:
        saved: What `apply_mutation` returned.
    """
    for path, data in saved.items():
        if data is None:
            path.unlink(missing_ok=True)
        elif not path.exists():
            path.write_bytes(data)
        else:
            mode = path.stat().st_mode
            path.write_bytes(data)
            path.chmod(mode)


def main() -> int:
    """Run the audit and print one line per mutation; see the module docstring."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-k", metavar="TEXT", help="only mutations whose id or description contains TEXT")
    args = ap.parse_args()
    chosen = [m for m in MUTATIONS if not args.k or args.k in m["id"] or args.k in m["why"]]

    with tempfile.TemporaryDirectory(prefix="dex-mutation-") as tmp:
        repo = Path(tmp) / "repo"
        shutil.copytree(REPO_ROOT, repo, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", ".ruff_cache"))
        git = ["git", "-c", "user.name=audit", "-c", "user.email=audit@example.com", "-C", str(repo)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "baseline"], check=True)

        baseline = run_suite(repo)
        if baseline:
            print(f"The unmodified copy fails ({baseline}); fix the suite before auditing it.")
            return 2

        survived = 0
        for m in chosen:
            if m.get("needs") and not shutil.which(m["needs"]):
                print(f"SKIPPED   {m['id']}: needs {m['needs']}")
                continue
            saved = apply_mutation(repo, m)
            try:
                caught_by = run_suite(repo)
            finally:
                restore(saved)
            if m.get("gap"):
                verdict = "KNOWN GAP" if caught_by is None else "CAUGHT*  "
            elif caught_by is None:
                verdict, survived = "SURVIVED ", survived + 1
            else:
                verdict = "CAUGHT   "
            print(f"{verdict} {m['id']}: {m['why']}" + (f"\n            by {caught_by}" if caught_by else ""))
        print(f"\n{survived} mutation(s) survived." if survived else "\nEvery non-gap mutation was caught.")
        return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
