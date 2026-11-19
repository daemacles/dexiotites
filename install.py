#!/usr/bin/env python3
"""Install or update the dexiotites commenting standard in one or more projects.

One command does a first install and every later update:

    python3 /path/to/dexiotites/install.py [PROJECT ...]     (default: current directory)

Run without a clone, the script fetches one and reruns itself from it:

    curl -fsSL https://raw.githubusercontent.com/daemacles/dexiotites/main/install.py | python3 -

What it puts in a project. All of it is plain files, so a fresh clone needs nothing else:

    docs/COMMENTING.md                 the full standard
    .agents/skills/<skill>/            each requested skill (default: annotate-code)
    .claude/skills/<skill>             symlink to the folder above, for Claude Code
    AGENTS.md                          the always-loaded rules, in a marked block
    PROJECT_INSTRUCTIONS.md            an empty file for the project's own instructions,
                                       created once and never touched again
    .agents/rules/                     a rule that tells agents to read that file; with
                                       `--with-jim`, also the maintainer's personal defaults
    CLAUDE.md                          import lines for AGENTS.md and the files above, if missing
    doc-linter config                  per language found: Cargo.toml `[lints]` block (Rust),
                                       ruff.toml (Python), .luarc.json (Lua),
                                       config/detekt/detekt-comments.yml (Kotlin)
    .dexiotites.json                   manifest: source commit, options, hash of each copied file

It then commits those paths, and only those. The message is
`dexiotites installed to remote @ <hash>`, or `updated` for a later run. The hash is the first
six characters of the dexiotites commit installed. Pass `--dont-add` to leave them uncommitted.

Safety rules:
    - Nothing is written unless every change is safe. A copied file is safe to replace when it
      is unchanged since the last install (manifest hash) or is byte-identical to some version
      dexiotites has shipped (looked up in this clone's git history). Anything else is a
      conflict: the script lists the conflicts, writes nothing and exits 1. `--force` replaces
      conflicting files.
    - Existing linter configs that the script did not create are never edited; it prints what
      to merge by hand.
    - Running it twice changes nothing the second time.
    - The commit holds the installer's changes and nothing else. Where the installer edits a
      file the project owns (AGENTS.md, CLAUDE.md, Cargo.toml), it commits its edit applied to
      the file's last committed version, so uncommitted work in that file stays uncommitted.
      Other staged or modified files are never included.

Exit codes: 0 done or already current; 1 conflicts, or `--check` found pending changes or an
uncommitted install; 2 usage or environment error, which includes a commit git refused.
Requires Python 3.9 or newer and git.

Extending: each supported doc linter and each agent harness is one entry in the `LINT_CONFIGS`
and `HARNESSES` tables below. The README section "Extending to a new language or harness" lists
the other files a new language or harness touches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

SOURCE_URL = "https://github.com/daemacles/dexiotites"
MANIFEST = ".dexiotites.json"
DEFAULT_SKILLS = ("annotate-code",)
PROJECT_FILE = "PROJECT_INSTRUCTIONS.md"
# Rule files copied from `instructions/rules/` into the project's `.agents/rules/`, where
# Antigravity loads every file by itself. The second is installed only with `--with-jim`.
PROJECT_RULE = "project-instructions.md"
JIM_RULE = "jim-defaults.md"
TEMPLATE = Path("instructions") / "AGENTS-commenting-section.md"

BEGIN = ("<!-- dexiotites:begin (managed by dexiotites install.py: rerun it to update; "
         "edits inside this block are overwritten) -->")
END = "<!-- dexiotites:end -->"
BEGIN_RE = re.compile(r"^<!-- dexiotites:begin\b.*-->\s*$")
# The section heading, with any numbering the project gave it ("## 6. Code Comments ...").
HEADING_RE = re.compile(r"^(#{1,6})\s+(?:\d+(?:\.\d+)*\.?\s+)?Code Comments\b")

TOML_BEGIN = "# dexiotites:begin doc lints (managed by dexiotites install.py; rerun it to update)"
TOML_END = "# dexiotites:end"
LINTS_TABLE_RE = re.compile(r"^\[(?:workspace\.)?lints\b", re.MULTILINE)

# Top-level folders never scanned when detecting a project's languages. Dot-folders are
# skipped too, so the installed checker script does not make every project "Python".
SKIP_DIRS = {"target", "build", "node_modules", "dist", "venv", "__pycache__"}


@dataclass(frozen=True)
class LintConfig:
    """A doc-linter config that is installed into a project as a file of its own.

    Adding an entry to `LINT_CONFIGS` is the installer's whole share of supporting a new
    language. A linter that is configured inside a file the project owns cannot be an entry:
    it needs its own planner that edits a marked block, as `plan_cargo_lints` does for Rust.

    Attributes:
        language: Name used in messages.
        suffixes: File suffixes (with the dot) whose presence means the project uses the language.
        template: The config's file name under `instructions/lint/`.
        dest: Project-relative path the config is installed at.
        rivals: File names that, anywhere in the project, mean the project already configures
            this linter itself. The installer then installs nothing and asks for a manual merge.
        rival_markers: `(file name, text)` pairs; a file of that name containing the text is
            also an existing config (a `pyproject.toml` holding a `[tool.ruff` table).
        manual_step: A step the installer cannot do, such as a build-file edit. Printed as a
            note on every run. Empty if there is none.
    """

    language: str
    suffixes: tuple[str, ...]
    template: str
    dest: str
    rivals: tuple[str, ...] = ()
    rival_markers: tuple[tuple[str, str], ...] = ()
    manual_step: str = ""


LINT_CONFIGS = (
    LintConfig("Python", (".py",), "ruff-docstrings.toml", "ruff.toml",
               rivals=("ruff.toml", ".ruff.toml"), rival_markers=(("pyproject.toml", "[tool.ruff"),)),
    LintConfig("Lua", (".lua",), "luarc-docs.json", ".luarc.json",
               rivals=(".luarc.json", ".luarc.jsonc")),
    LintConfig("Kotlin", (".kt",), "detekt-comments.yml", "config/detekt/detekt-comments.yml",
               manual_step="the detekt Gradle plugin block is a manual edit; see 'Kotlin build "
                           "file' in the dexiotites README"),
)


@dataclass(frozen=True)
class Harness:
    """What one agent harness needs in order to find the installed rules and skills.

    The installer puts the real content in `AGENTS.md` and `.agents/skills/<name>/`. A harness
    that reads both by itself needs no entry; Antigravity is one. Add an entry to `HARNESSES`
    for a harness that looks somewhere else.

    Attributes:
        name: Name used in messages.
        rules_file: Project-relative file the harness always loads in place of AGENTS.md, or
            empty if it loads AGENTS.md itself.
        import_format: How one import line is written in `rules_file`, with `{path}` standing
            for the imported file. The installer writes one such line for AGENTS.md, one for the
            project's own instructions file, and one per optional rule file. Empty if the
            harness has no import syntax: `rules_file` is then created as a symlink to AGENTS.md
            and the other files are not loaded by this harness.
        skills_dir: Project-relative folder the harness discovers skills in, or empty if it
            reads `.agents/skills/` itself. Each installed skill is symlinked into it.
    """

    name: str
    rules_file: str = ""
    import_format: str = ""
    skills_dir: str = ""


HARNESSES = (
    Harness("Claude Code", rules_file="CLAUDE.md", import_format="@{path}", skills_dir=".claude/skills"),
)


@dataclass
class Change:
    """One planned effect on a project, or a note for the user.

    Attributes:
        path: Project-relative path the change applies to.
        status: `create`, `update`, `remove`, `unchanged`, `conflict` or `note`.
        detail: Human-readable reason, printed after the path.
        content: New file bytes for `create`/`update` of a regular file.
        executable: Whether the written file gets the executable bit.
        link: Symlink target for `create`/`update` of a symlink (then `content` is None).
        managed: Whether the file is recorded in the manifest (copied verbatim from dexiotites).
        staged: Bytes to commit when they must differ from `content`: the installer's edit
            applied to the file's last committed version instead of its working copy.
        track: False when the installer cannot work out what to commit for this path.
    """

    path: str
    status: str
    detail: str = ""
    content: bytes | None = None
    executable: bool = False
    link: str | None = None
    managed: bool = False
    staged: bytes | None = None
    track: bool = True


class InstallError(Exception):
    """A usage or environment problem that stops the run with exit code 2."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command and capture its output; never raises on a non-zero exit.

    Args:
        cwd: Folder git runs in.
        *args: The git subcommand and its arguments.
    """
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def _head_text(project: Path, rel: str) -> str | None:
    """Return a file's text as last committed in the project.

    Args:
        project: Root of the target project.
        rel: Project-relative path of the file.

    Returns:
        The committed text; an empty string if the path is not committed (or the project has
        no commits or is not a git repository); None if the committed entry is not a regular
        file (a symlink or submodule).
    """
    listed = _git(project, "ls-tree", "HEAD", "--", rel).stdout.split()
    if not listed:
        return ""
    if not listed[0].startswith("100"):
        return None
    return _git(project, "show", f"HEAD:{rel}").stdout


def _set_staged(project: Path, change: Change, edit: Callable[[str], str | None]) -> Change:
    """Work out what to commit for a file the project owns and the installer edits in place.

    Args:
        project: Root of the target project.
        change: The planned change to the working copy; updated in place and returned.
        edit: The installer's edit as a function of the file's text. It is applied here to the
            committed version. Returning None, or raising InstallError, means the edit cannot
            be applied to that version; the path is then left for the user to commit.
    """
    head = _head_text(project, change.path)
    try:
        text = None if head is None else edit(head)
    except InstallError:
        text = None
    if text is None:
        change.track = False
    else:
        change.staged = text.encode("utf-8")
    return change


def was_ever_shipped(source: Path, data: bytes) -> bool:
    """Report whether some contents match a file version in the source's git history.

    This is how an unmanifested file from an older, hand-made install is told apart from a
    file the project wrote or edited itself.

    Args:
        source: Root of the dexiotites checkout.
        data: Current contents of the project's file.

    Returns:
        True if the source's git object store holds a blob with these contents. False when it
        does not, or when the source is not a git checkout (no history to consult).
    """
    blob = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    return _git(source, "cat-file", "-e", blob).returncode == 0


def source_commit(source: Path) -> str:
    """Return the commit the source checkout is at, marked if it has local changes.

    Returns:
        The full commit hash, with `+dirty` appended when shipped files have uncommitted
        changes, or `unknown` when the source is not a git checkout.
    """
    head = _git(source, "rev-parse", "HEAD")
    if head.returncode != 0:
        return "unknown"
    dirty = _git(source, "status", "--porcelain", "--", "instructions", "skills", "install.py")
    return head.stdout.strip() + ("+dirty" if dirty.stdout.strip() else "")


def project_files(project: Path) -> list[str]:
    """List the project's own files as relative paths, for language detection.

    In a git repository the list is git's view: tracked files plus untracked files that are not
    ignored. Elsewhere the tree is walked. Dot-folders and build folders are left out.
    """
    listed = _git(project, "ls-files", "--cached", "--others", "--exclude-standard")
    if listed.returncode == 0:
        paths = listed.stdout.splitlines()
    else:
        paths = [str(p.relative_to(project)) for p in project.rglob("*") if p.is_file()]
    keep = []
    for rel in paths:
        parts = Path(rel).parts
        if any(part.startswith(".") or part in SKIP_DIRS for part in parts[:-1]):
            continue
        keep.append(rel)
    return keep


def load_manifest(project: Path) -> dict:
    """Read the project's manifest, or return an empty one if none exists.

    Raises:
        InstallError: if the manifest exists but is not valid JSON.
    """
    path = project / MANIFEST
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstallError(f"{path} is not valid JSON ({exc}); fix or delete it") from exc


# --------------------------------------------------------------------------- copied files


def lint_files(source: Path, project: Path, files: list[str],
               recorded: dict) -> tuple[dict[str, Path], list[Change]]:
    """Choose which standalone linter configs to copy, by the languages the project uses.

    The candidates are the `LINT_CONFIGS` entries. One is copied when its language is present
    and the project has no config of that kind. An existing config counts as absent when this
    script installed it, which the manifest records.

    Args:
        source: Root of the dexiotites checkout.
        project: Root of the target project.
        files: The project's own files, from `project_files`.
        recorded: The manifest's `files` mapping (path -> hash) from the previous install.

    Returns:
        A mapping of project-relative destination to source file, and notes for configs that
        need a manual merge or a manual build-file edit.
    """
    suffixes = {Path(f).suffix for f in files}
    out: dict[str, Path] = {}
    notes: list[Change] = []
    for cfg in LINT_CONFIGS:
        if not suffixes.intersection(cfg.suffixes):
            continue
        theirs = [f for f in files if Path(f).name in cfg.rivals
                  and not (f == cfg.dest and f in recorded)]
        theirs += [f for f in files for name, text in cfg.rival_markers
                   if Path(f).name == name and text in _read_text(project / f)]
        if theirs:
            notes.append(Change(cfg.dest, "note",
                                f"{cfg.language}: existing linter config ({', '.join(theirs)}) left as "
                                f"is; merge instructions/lint/{cfg.template} into it by hand"))
            continue
        out[cfg.dest] = source / "instructions" / "lint" / cfg.template
        if cfg.manual_step:
            notes.append(Change(cfg.dest, "note", f"{cfg.language}: {cfg.manual_step}"))
    return out, notes


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def plan_copies(source: Path, project: Path, manifest: dict, skills: list[str],
                lint: bool, files: list[str], rules: list[str]) -> list[Change]:
    """Plan every verbatim file copy, and removal of copies dexiotites no longer ships.

    Args:
        source: Root of the dexiotites checkout.
        project: Root of the target project.
        manifest: The project's current manifest (empty on a first install).
        skills: Skill folder names to install.
        lint: Whether to install standalone linter configs.
        files: The project's own files, from `project_files`.
        rules: Names of the rule files to install, from `instructions/rules/`.

    Returns:
        One `Change` per shipped file (status `create`, `update`, `unchanged` or `conflict`),
        per obsolete file (`remove`, or `note` if it was edited), plus lint notes.
    """
    recorded: dict = manifest.get("files", {})
    shipped: dict[str, Path] = {"docs/COMMENTING.md": source / "instructions" / "COMMENTING.md"}
    for rule in rules:
        shipped[f".agents/rules/{rule}"] = source / "instructions" / "rules" / rule
    for skill in skills:
        root = source / "skills" / skill
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                shipped[f".agents/skills/{skill}/{path.relative_to(root).as_posix()}"] = path
    notes: list[Change] = []
    if lint:
        configs, notes = lint_files(source, project, files, recorded)
        shipped.update(configs)

    changes: list[Change] = []
    for rel, src in shipped.items():
        new = src.read_bytes()
        exe = os.access(src, os.X_OK)
        dst = project / rel
        change = Change(rel, "create", content=new, executable=exe, managed=True)
        if dst.is_symlink() or dst.is_dir():
            change.status, change.detail = "conflict", "is a symlink or folder, expected a file"
        elif dst.exists():
            cur = dst.read_bytes()
            if cur == new and os.access(dst, os.X_OK) == exe:
                change.status = "unchanged"
            elif rel in recorded and _sha256(cur) != recorded[rel]:
                change.status, change.detail = "conflict", "edited in this project since it was installed"
            elif rel in recorded or cur == new or was_ever_shipped(source, cur):
                change.status = "update"
            else:
                change.status, change.detail = "conflict", "exists and is not a version dexiotites shipped"
        changes.append(change)

    for rel in sorted(set(recorded) - set(shipped)):
        dst = project / rel
        if not dst.is_file():
            continue
        if _sha256(dst.read_bytes()) == recorded[rel]:
            changes.append(Change(rel, "remove", "no longer shipped by dexiotites"))
        else:
            changes.append(Change(rel, "note", "no longer shipped, but edited here: left in place"))
    return changes + notes


# --------------------------------------------------------------------------- AGENTS.md block


def _body(section: str) -> str:
    """Return a section's text without its heading line, whitespace-normalized for comparison."""
    lines = [line.rstrip() for line in section.strip().splitlines()]
    if lines and HEADING_RE.match(lines[0]):
        lines = lines[1:]
    return "\n".join(lines).strip()


def shipped_bodies(source: Path) -> set[str]:
    """Return the body of every version of the AGENTS.md section dexiotites has shipped.

    Falls back to the current version alone when the source has no git history.
    """
    bodies = {_body((source / TEMPLATE).read_text(encoding="utf-8"))}
    log = _git(source, "log", "--format=%H", "--", TEMPLATE.as_posix())
    for commit in log.stdout.split():
        shown = _git(source, "show", f"{commit}:{TEMPLATE.as_posix()}")
        if shown.returncode == 0:
            bodies.add(_body(shown.stdout))
    return bodies


def agents_md_text(source: Path, old: str, where: str = "AGENTS.md") -> tuple[str, str, bool]:
    """Return the text of an AGENTS.md with the marked rules block in place and up to date.

    Three starting states are handled:
    - A marked block: its body is replaced.
    - An unmarked "Code Comments" section from a hand-made install: replaced if its body is a
      version dexiotites shipped, otherwise a conflict.
    - Neither: the block is appended.

    The project's own heading line is kept, so numbering such as "## 6. Code Comments" survives.

    Args:
        source: Root of the dexiotites checkout.
        old: Current text of the file; empty if it does not exist.
        where: Name of the file, for error messages.

    Returns:
        The new text, a note describing what was done (may be empty), and whether replacing
        the existing section is a conflict.

    Raises:
        InstallError: if `old` has a begin marker without an end marker, or two blocks.
    """
    template = (source / TEMPLATE).read_text(encoding="utf-8").strip().splitlines()
    lines = old.splitlines()

    begins = [i for i, line in enumerate(lines) if BEGIN_RE.match(line)]
    ends = [i for i, line in enumerate(lines) if line.strip() == END]
    if len(begins) > 1 or len(ends) > 1 or (begins and (not ends or ends[0] < begins[0])):
        raise InstallError(f"{where}: malformed dexiotites markers; expected one begin/end pair")

    detail, conflict = "", False
    if begins:
        start, stop = begins[0], ends[0] + 1
        inner = lines[start + 1:ends[0]]
    else:
        heads = [i for i, line in enumerate(lines) if HEADING_RE.match(line)]
        if heads:
            start = heads[0]
            level = len(HEADING_RE.match(lines[start]).group(1))
            stop = next((i for i in range(start + 1, len(lines))
                         if re.match(r"^#{1,%d}\s" % level, lines[i])), len(lines))
            inner = lines[start:stop]
            detail = "existing Code Comments section put under dexiotites markers"
            if _body("\n".join(inner)) not in shipped_bodies(source):
                conflict = True
                detail = "has a Code Comments section that differs from every shipped version"
        else:
            start = stop = len(lines)
            inner = []
    heading = inner[0] if inner and HEADING_RE.match(inner[0]) else template[0]
    block = [BEGIN, heading, *template[1:], END]

    before, after = lines[:start], lines[stop:]
    while before and not before[-1].strip():
        before.pop()
    while after and not after[0].strip():
        after.pop(0)
    parts = [*before, *([""] if before else []), *block, *([""] if after else []), *after]
    return "\n".join(parts) + "\n", detail, conflict


def plan_agents_md(source: Path, project: Path) -> Change:
    """Plan the marked rules block in the project's AGENTS.md; see `agents_md_text`.

    Raises:
        InstallError: if the working copy's markers are malformed.
    """
    path = project / "AGENTS.md"
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    new, detail, conflict = agents_md_text(source, old, str(path))
    status = "unchanged" if new == old else "conflict" if conflict else "update" if old else "create"
    change = Change("AGENTS.md", status, detail if new != old else "", content=new.encode("utf-8"))

    def committed_edit(head: str) -> str | None:
        text, _, head_conflict = agents_md_text(source, head)
        return None if head_conflict else text

    return _set_staged(project, change, committed_edit)


# --------------------------------------------------------------------------- other files


def plan_rules_file(project: Path, harness: Harness, imports: list[str]) -> list[Change]:
    """Plan the file that makes a harness load AGENTS.md, if it does not load it by itself.

    With an import syntax, one line per path in `imports` is kept at the top of the harness's
    rules file; lines already there are left alone and missing ones are added after them. Without one,
    the rules file is created as a symlink to AGENTS.md. A rules file that is already a
    symlink is left alone: it normally points at AGENTS.md, and writing through it would edit
    its target. So is one that AGENTS.md is a symlink to, where the import would make the file
    import itself.
    """
    if not harness.rules_file:
        return []
    rel = harness.rules_file
    path = project / rel
    if path.is_symlink() or (path.exists() and (project / "AGENTS.md").resolve() == path.resolve()):
        return [Change(rel, "unchanged")]
    if not harness.import_format:
        if path.exists():
            return [Change(rel, "note", f"exists and is not a symlink to AGENTS.md: left as is; "
                           f"{harness.name} will not load the commenting rules from it")]
        return [Change(rel, "create", link=os.path.relpath("AGENTS.md", Path(rel).parent))]

    wanted = [harness.import_format.format(path=path) for path in imports]
    marker = harness.import_format.split("{path}")[0]

    def with_import(text: str) -> str:
        lines = text.splitlines()
        missing = [w for w in wanted if not any(line.strip().startswith(w) for line in lines)]
        if not missing:
            return text
        head = 0                                  # length of the leading run of import lines
        while head < len(lines) and marker and lines[head].startswith(marker):
            head += 1
        rest = lines[head:]
        gap = [""] if rest and rest[0].strip() else []
        return "\n".join([*lines[:head], *missing, *gap, *rest]) + "\n"

    old = path.read_text(encoding="utf-8") if path.exists() else ""
    new = with_import(old)
    status = "unchanged" if new == old else "update" if path.exists() else "create"
    detail = "added import lines" if status == "update" else ""
    return [_set_staged(project, Change(rel, status, detail, content=new.encode("utf-8")), with_import)]


def plan_skill_links(project: Path, skills: list[str], harness: Harness) -> list[Change]:
    """Plan the symlinks that let a harness see each skill in its own skills folder.

    Nothing is planned for a skill the harness can already reach there. That happens when its
    skills folder is itself a symlink to `.agents/skills`. A real folder or file in the way is
    reported and left alone.
    """
    if not harness.skills_dir:
        return []
    changes = []
    canonical = project / ".agents" / "skills"
    shared = (project / harness.skills_dir).resolve() == canonical.resolve()
    for skill in skills:
        rel = f"{harness.skills_dir}/{skill}"
        if shared:
            changes.append(Change(rel, "unchanged"))
            continue
        link = project / rel
        target = os.path.relpath(f".agents/skills/{skill}", harness.skills_dir)
        if link.is_symlink() and os.readlink(link) == target:
            changes.append(Change(rel, "unchanged", link=target))
        elif link.exists() and link.resolve() == (canonical / skill).resolve():
            changes.append(Change(rel, "unchanged"))
        elif link.is_symlink():
            changes.append(Change(rel, "update", "symlink repointed", link=target))
        elif link.exists():
            changes.append(Change(rel, "note", "exists and is not a symlink to "
                                  f".agents/skills/{skill}: left as is; {harness.name} may load a stale copy"))
        else:
            changes.append(Change(rel, "create", link=target))
    return changes


def cargo_lints_text(source: Path, old: str, lint: bool) -> tuple[str | None, str]:
    """Return the text of a Cargo.toml with the documentation lints block added or refreshed.

    The block sits at the end of the file between marker comments and is replaced in place
    when already there. With `lint` False, a block added earlier is removed.

    Returns:
        The new text and an empty note; or None and a note when the file is left alone
        because it has its own `[lints]` tables or is a workspace root (merging TOML tables
        safely needs a human). None with an empty note means there is nothing to do.
    """
    template = (source / "instructions" / "lint" / "rust-cargo-lints.toml").read_text(encoding="utf-8")
    block = f"{TOML_BEGIN}\n{template.strip()}\n{TOML_END}\n"
    pattern = re.compile(r"^# dexiotites:begin doc lints.*?^# dexiotites:end\n?", re.DOTALL | re.MULTILINE)
    if pattern.search(old):
        new = pattern.sub(lambda _: block if lint else "", old, count=1)
        return new.rstrip("\n") + "\n", ""
    if not lint:
        return None, ""
    if LINTS_TABLE_RE.search(old):
        return None, ("Rust: existing [lints] tables left as is; merge "
                      "instructions/lint/rust-cargo-lints.toml into them by hand")
    if re.search(r"^\[workspace\]", old, re.MULTILINE):
        return None, ("Rust: workspace root left as is; add the tables from "
                      "instructions/lint/rust-cargo-lints.toml as [workspace.lints.*] by hand "
                      "(see that file's header)")
    return old.rstrip("\n") + "\n\n" + block, ""


def plan_cargo_lints(source: Path, project: Path, lint: bool) -> list[Change]:
    """Plan the documentation lints block in the project's root Cargo.toml, if it has one."""
    path = project / "Cargo.toml"
    if not path.is_file():
        return []
    old = path.read_text(encoding="utf-8")
    new, note = cargo_lints_text(source, old, lint)
    if new is None:
        return [Change("Cargo.toml", "note", note)] if note else []
    change = Change("Cargo.toml", "unchanged" if new == old else "update",
                    "" if new == old else "documentation [lints] block", content=new.encode("utf-8"))
    return [_set_staged(project, change, lambda head: cargo_lints_text(source, head, lint)[0] if head else None)]


# --------------------------------------------------------------------------- driver


def plan_project_file(project: Path) -> list[Change]:
    """Plan the project's own instructions file: created empty once, then left to the project.

    The file is committed only while it is still empty and not yet committed, so content the
    project writes into it is never committed by the installer.
    """
    path = project / PROJECT_FILE
    if not path.exists():
        return [Change(PROJECT_FILE, "create", content=b"")]
    committed = _git(project, "ls-tree", "HEAD", "--", PROJECT_FILE).stdout.strip()
    if path.is_file() and not committed and path.read_bytes() == b"":
        return [Change(PROJECT_FILE, "unchanged", content=b"")]
    return [Change(PROJECT_FILE, "unchanged")]


def plan(source: Path, project: Path, skills: list[str] | None, lint: bool | None,
         force: bool = False, with_jim: bool = False) -> tuple[list[Change], dict]:
    """Compute every change needed to bring one project up to date with the source.

    Args:
        source: Root of the dexiotites checkout.
        project: Root of the target project.
        skills: Skills to add to the set already recorded in the manifest (which starts as
            `annotate-code`), or None to add none.
        lint: False to remove linter configs this script installed, True to install them,
            None to reuse the manifest's choice (default True).
        force: Turn conflicts into updates, replacing the conflicting content.
        with_jim: Also install the maintainer's personal default instructions. Once set, the
            manifest remembers it.

    Returns:
        The planned changes, and the manifest to write if any managed content changes.

    Raises:
        InstallError: if the project is the source itself, or a requested skill does not exist.
    """
    if project.resolve() == source.resolve():
        raise InstallError("refusing to install dexiotites into its own repository")
    manifest = load_manifest(project)
    skills = sorted(set(manifest.get("skills", DEFAULT_SKILLS)) | set(skills or ()))
    lint = manifest.get("lint", True) if lint is None else lint
    with_jim = with_jim or bool(manifest.get("with_jim"))
    rules = [PROJECT_RULE, *([JIM_RULE] if with_jim else [])]
    imports = ["AGENTS.md", PROJECT_FILE, *([f".agents/rules/{JIM_RULE}"] if with_jim else [])]
    for skill in skills:
        if not (source / "skills" / skill / "SKILL.md").is_file():
            available = sorted(p.name for p in (source / "skills").iterdir() if p.is_dir())
            raise InstallError(f"no such skill: {skill} (available: {', '.join(available)})")

    files = project_files(project)
    changes = plan_copies(source, project, manifest, skills, lint, files, rules)
    changes.extend(plan_project_file(project))
    changes.append(plan_agents_md(source, project))
    for harness in HARNESSES:
        changes.extend(plan_rules_file(project, harness, imports))
        changes.extend(plan_skill_links(project, skills, harness))
    changes.extend(plan_cargo_lints(source, project, lint))
    if force:
        for c in changes:
            if c.status == "conflict":
                c.status, c.detail = "update", f"FORCED, replacing a file that {c.detail}"

    hashes = {c.path: _sha256(c.content) for c in changes
              if c.managed and c.content is not None}
    new_manifest = {
        "source": SOURCE_URL,
        "commit": source_commit(source),
        "skills": skills,
        "lint": lint,
        **({"with_jim": True} if with_jim else {}),
        "files": dict(sorted(hashes.items())),
    }
    old_view = {k: manifest.get(k) for k in ("skills", "lint", "files", "with_jim")}
    content_changed = any(c.status in ("create", "update", "remove") for c in changes)
    if content_changed or old_view != {k: new_manifest.get(k) for k in old_view}:
        data = (json.dumps(new_manifest, indent=2) + "\n").encode("utf-8")
        status = "update" if (project / MANIFEST).exists() else "create"
        changes.append(Change(MANIFEST, status, content=data))
    else:
        changes.append(Change(MANIFEST, "unchanged", content=(project / MANIFEST).read_bytes()))
    return changes, new_manifest


def apply(project: Path, changes: list[Change]) -> None:
    """Write the planned creations, updates and removals into the project."""
    for c in changes:
        dst = project / c.path
        if c.status == "remove":
            dst.unlink()
            parent = dst.parent
            while parent != project and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        elif c.status in ("create", "update") and (c.content is not None or c.link):
            dst.parent.mkdir(parents=True, exist_ok=True)
            if c.link:
                if dst.is_symlink():
                    dst.unlink()
                dst.symlink_to(c.link)
            else:
                if dst.is_symlink():
                    dst = dst.resolve()               # write through, e.g. AGENTS.md -> other file
                dst.write_bytes(c.content)
                dst.chmod(0o755 if c.executable else 0o644)


def uncommitted(project: Path, changes: list[Change], write: bool) -> tuple[list[tuple], list[str]]:
    """Compare what the installer put in the project with the project's last commit.

    Args:
        project: Root of the target project; must be the root of a git repository.
        changes: The plan, after it has been applied.
        write: Store the blobs in the repository's object database, as a commit needs. False
            only computes their ids.

    Returns:
        The index entries that differ from HEAD, each `(path, mode, blob id)` or, for a path
        to delete, `(path, None, None)`; and the paths the installer changed but cannot commit
        (`Change.track` is False), which the user has to commit.
    """
    paths = [c.path for c in changes if c.status != "note"]
    tree = {}
    for line in _git(project, "ls-tree", "HEAD", "--", *paths).stdout.splitlines():
        meta, path = line.split("\t", 1)
        mode, _, blob = meta.split()
        tree[path] = (mode, blob)
    entries, skipped = [], []
    for c in changes:
        if c.status == "remove":
            if c.path in tree:
                entries.append((c.path, None, None))
            continue
        if c.status == "note" or (c.content is None and c.link is None):
            continue
        if not c.track:
            skipped.append(c.path)
            continue
        if c.link is not None:
            mode, data = "120000", c.link.encode("utf-8")
        else:
            data = c.content if c.staged is None else c.staged
            kept = tree.get(c.path, ("100644",))[0]
            mode = ("100755" if c.executable else "100644") if c.managed or not kept.startswith("100") else kept
        hashed = subprocess.run(["git", "-C", str(project), "hash-object", *(["-w"] if write else []), "--stdin"],
                                input=data, capture_output=True)
        blob = hashed.stdout.decode().strip()
        if tree.get(c.path) != (mode, blob):
            entries.append((c.path, mode, blob))
    return entries, skipped


def commit_install(project: Path, changes: list[Change]) -> str:
    """Commit the installed paths, and nothing else, to the project's current branch.

    The commit is built in a temporary index that starts from HEAD, so files the user has
    staged or modified are not swept in. Afterwards the same entries are set in the real
    index, which leaves the installed paths clean and every other path as it was.

    Returns:
        A one-line report: the new commit and its message, or why nothing was committed.

    Raises:
        InstallError: if git refuses the commit (no identity configured, a hook failed).
    """
    entries, skipped = uncommitted(project, changes, write=True)
    left = f"; commit {', '.join(skipped)} yourself" if skipped else ""
    if not entries:
        return f"nothing to commit{left}"
    has_head = _git(project, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
    verb = "updated" if _git(project, "ls-tree", "HEAD", "--", MANIFEST).stdout.strip() else "installed"
    installed = load_manifest(project).get("commit", "unknown")
    version = installed[:6] + ("+dirty" if installed.endswith("+dirty") else "")
    message = f"dexiotites {verb} to remote @ {version}"

    def stage(env: dict | None) -> None:
        for path, mode, blob in entries:
            args = ["--force-remove", path] if mode is None else ["--add", "--cacheinfo", f"{mode},{blob},{path}"]
            subprocess.run(["git", "-C", str(project), "update-index", *args], env=env, check=True,
                           capture_output=True)

    with tempfile.TemporaryDirectory(prefix="dexiotites-index-") as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        if has_head:
            subprocess.run(["git", "-C", str(project), "read-tree", "HEAD"], env=env, check=True)
        stage(env)
        done = subprocess.run(["git", "-C", str(project), "commit", "-q", "-m", message],
                              env=env, capture_output=True, text=True)
    if done.returncode != 0:
        reason = (done.stderr.strip() or done.stdout.strip()).splitlines()
        raise InstallError("the files are installed, but git refused to commit them: "
                           + (" ".join(reason[:3]) if reason else "no reason given"))
    stage(None)
    short = _git(project, "rev-parse", "--short", "HEAD").stdout.strip()
    return f'committed {short} "{message}"{left}'


def run(source: Path, project: Path, args: argparse.Namespace) -> int:
    """Plan and report the changes for one project, then apply and commit them.

    Nothing is applied when checking, or when a conflict blocks the run.

    Returns:
        0 if the project is or was brought up to date, 1 if conflicts blocked the run or
        `--check` found pending changes.
    """
    print(f"== {project}")
    if not project.is_dir():
        raise InstallError(f"not a directory: {project}")
    top = _git(project, "rev-parse", "--show-toplevel").stdout.strip()
    is_repo_root = bool(top) and Path(top).resolve() == project.resolve()
    if not is_repo_root:
        print("  warning: not the root of a git repository; annotate-code's checker needs git")
    lint = False if args.no_lint else (True if args.lint else None)
    changes, manifest = plan(source, project, args.skill, lint, args.force, args.with_jim)

    conflicts = [c for c in changes if c.status == "conflict"]
    pending = [c for c in changes if c.status in ("create", "update", "remove")]
    for c in changes:
        if c.status != "unchanged":
            print(f"  {c.status:9} {c.path}" + (f"  ({c.detail})" if c.detail else ""))
    unchanged = sum(c.status == "unchanged" for c in changes)

    if conflicts:
        print(f"  NOTHING WRITTEN: {len(conflicts)} conflict(s). The files marked 'conflict' hold "
              "content that did not come from dexiotites.\n  --force replaces those files and "
              "that content is lost: ask the project's owner first.\n  To keep the content, copy "
              "it out before forcing. Instructions for this project alone belong in\n"
              f"  {PROJECT_FILE}; rules for every project belong in dexiotites itself.")
        return 1
    if args.check:
        if pending or conflicts:
            print(f"  out of date: {len(pending) + len(conflicts)} change(s) pending")
            return 1
        loose = uncommitted(project, changes, write=False)[0] if is_repo_root else []
        if loose:
            print(f"  up to date, but {len(loose)} installed path(s) are not committed: "
                  + ", ".join(path for path, _, _ in loose))
            return 1
        print(f"  up to date ({unchanged} items, dexiotites {manifest['commit'][:7]})")
        return 0
    apply(project, changes)
    if pending:
        print(f"  done: {len(pending)} change(s), {unchanged} unchanged.")
    else:
        print(f"  already up to date ({unchanged} items)")
    if args.dont_add:
        print("  not committed (--dont-add): review with `git status`, then commit.")
    elif not is_repo_root:
        print("  not committed: this folder is not the root of a git repository.")
    else:
        print(f"  {commit_install(project, changes)}")
    return 0


def bootstrap(argv: list[str]) -> int:
    """Clone dexiotites to a temporary folder and rerun this script from the clone.

    Used when the script runs on its own, piped from curl, without the repository's files
    beside it. `DEXIOTITES_URL` and `DEXIOTITES_REF` override the clone URL and branch.
    """
    url = os.environ.get("DEXIOTITES_URL", SOURCE_URL)
    ref = os.environ.get("DEXIOTITES_REF")
    with tempfile.TemporaryDirectory(prefix="dexiotites-") as tmp:
        cmd = ["git", "clone", "--quiet", *(["--branch", ref] if ref else []), url, tmp]
        if subprocess.run(cmd).returncode != 0:
            print(f"error: could not clone {url}", file=sys.stderr)
            return 2
        return subprocess.run([sys.executable, str(Path(tmp) / "install.py"), *argv]).returncode


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and install into each named project; see the module docstring."""
    argv = sys.argv[1:] if argv is None else argv
    script = Path(__file__).resolve() if "__file__" in globals() and Path(__file__).is_file() else None
    if script is None or not (script.parent / TEMPLATE).is_file():
        return bootstrap(argv)
    source = script.parent

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projects", nargs="*", type=Path, default=[Path.cwd()], metavar="PROJECT",
                    help="project root(s) to install into (default: the current directory)")
    ap.add_argument("--check", action="store_true",
                    help="write nothing; exit 1 if a project is out of date or has conflicts")
    ap.add_argument("--force", action="store_true",
                    help="replace files that conflict (local edits in them are lost)")
    ap.add_argument("--skill", action="append", metavar="NAME",
                    help="extra skill to install besides annotate-code, e.g. distill-spec; "
                         "repeatable, and remembered for later runs")
    ap.add_argument("--with-jim", action="store_true",
                    help="also install the maintainer's personal default instructions for "
                         "agents (terms of art, plan first, prompt coaching); remembered")
    ap.add_argument("--dont-add", action="store_true",
                    help="install or update the files but do not `git add` or commit them")
    ap.add_argument("--no-lint", action="store_true",
                    help="no doc-linter configs (removes ones this script installed); remembered")
    ap.add_argument("--lint", action="store_true", help="turn doc-linter configs back on")
    args = ap.parse_args(argv)

    worst = 0
    for project in args.projects:
        try:
            worst = max(worst, run(source, project.resolve(), args))
        except InstallError as exc:
            print(f"  error: {exc}", file=sys.stderr)
            worst = 2
    return worst


if __name__ == "__main__":
    sys.exit(main())
