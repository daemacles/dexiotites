#!/usr/bin/env python3
"""Install or update the dexiotites commenting standard in one or more projects.

One command does a first install and every later update:

    python3 /path/to/dexiotites/install.py [PROJECT ...]     (default: current directory)

Run without a clone, the script fetches one and reruns itself from it:

    curl -fsSL https://raw.githubusercontent.com/daemacles/dexiotites/main/install.py | python3 -

What it puts in a project (all plain files, so a fresh clone of the project needs nothing else):

    docs/COMMENTING.md                 the full standard
    .agents/skills/<skill>/            each requested skill (default: annotate-code)
    .claude/skills/<skill>             symlink to the folder above, for Claude Code
    AGENTS.md                          the always-loaded rules, in a marked block
    CLAUDE.md                          an `@AGENTS.md` import line, if missing
    doc-linter config                  per language found: Cargo.toml `[lints]` block (Rust),
                                       ruff.toml (Python), .luarc.json (Lua),
                                       config/detekt/detekt-comments.yml (Kotlin)
    .dexiotites.json                   manifest: source commit, options, hash of each copied file

Safety rules:
    - Nothing is written unless every change is safe. A copied file is safe to replace when it
      is unchanged since the last install (manifest hash) or is byte-identical to some version
      dexiotites has shipped (looked up in this clone's git history). Anything else is a
      conflict: the script lists the conflicts, writes nothing and exits 1. `--force` replaces
      conflicting files.
    - Existing linter configs that the script did not create are never edited; it prints what
      to merge by hand.
    - Running it twice changes nothing the second time.

Exit codes: 0 done or already current; 1 conflicts, or `--check` found pending changes;
2 usage or environment error. Requires Python 3.9 or newer and git.

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
from dataclasses import dataclass
from pathlib import Path

SOURCE_URL = "https://github.com/daemacles/dexiotites"
MANIFEST = ".dexiotites.json"
DEFAULT_SKILLS = ("annotate-code",)
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

    `AGENTS.md` and `.agents/skills/<name>/` are where the installer puts the real content. A
    harness that reads both by itself (Antigravity does) needs no entry. Add an entry to
    `HARNESSES` for a harness that looks somewhere else.

    Attributes:
        name: Name used in messages.
        rules_file: Project-relative file the harness always loads in place of AGENTS.md, or
            empty if it loads AGENTS.md itself.
        import_line: The line that makes `rules_file` pull in AGENTS.md, in the harness's own
            import syntax. Empty if the harness has none: `rules_file` is then created as a
            symlink to AGENTS.md.
        skills_dir: Project-relative folder the harness discovers skills in, or empty if it
            reads `.agents/skills/` itself. Each installed skill is symlinked into it.
    """

    name: str
    rules_file: str = ""
    import_line: str = ""
    skills_dir: str = ""


HARNESSES = (
    Harness("Claude Code", rules_file="CLAUDE.md", import_line="@AGENTS.md", skills_dir=".claude/skills"),
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
    """

    path: str
    status: str
    detail: str = ""
    content: bytes | None = None
    executable: bool = False
    link: str | None = None
    managed: bool = False


class InstallError(Exception):
    """A usage or environment problem that stops the run with exit code 2."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run git in `cwd`, capturing output; never raises on a non-zero exit."""
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def was_ever_shipped(source: Path, data: bytes) -> bool:
    """Report whether `data` is byte-identical to a file version in the source's git history.

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
    """Return the source checkout's commit hash, `+dirty` appended if it has local changes.

    Returns `unknown` when the source is not a git checkout.
    """
    head = _git(source, "rev-parse", "HEAD")
    if head.returncode != 0:
        return "unknown"
    dirty = _git(source, "status", "--porcelain", "--", "instructions", "skills", "install.py")
    return head.stdout.strip() + ("+dirty" if dirty.stdout.strip() else "")


def project_files(project: Path) -> list[str]:
    """List the project's own files (relative paths), for language detection.

    Uses git's view (tracked plus untracked-but-not-ignored) when the project is a git
    repository, otherwise walks the tree. Dot-folders and build folders are left out.
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
    """Choose the `LINT_CONFIGS` entries to copy for the languages the project uses.

    A config is copied when its language is present and the project has no config of that
    kind, or the existing one was installed by this script (it is in the manifest).

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
                lint: bool, files: list[str]) -> list[Change]:
    """Plan every verbatim file copy, and removal of copies dexiotites no longer ships.

    Args:
        source: Root of the dexiotites checkout.
        project: Root of the target project.
        manifest: The project's current manifest (empty on a first install).
        skills: Skill folder names to install.
        lint: Whether to install standalone linter configs.
        files: The project's own files, from `project_files`.

    Returns:
        One `Change` per shipped file (status `create`, `update`, `unchanged` or `conflict`),
        per obsolete file (`remove`, or `note` if it was edited), plus lint notes.
    """
    recorded: dict = manifest.get("files", {})
    shipped: dict[str, Path] = {"docs/COMMENTING.md": source / "instructions" / "COMMENTING.md"}
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


def plan_agents_md(source: Path, project: Path) -> Change:
    """Plan the marked rules block in the project's AGENTS.md.

    Three starting states are handled: a marked block (its body is replaced), an unmarked
    "Code Comments" section from a hand-made install (replaced only if its body is a version
    dexiotites shipped, otherwise a conflict), or neither (the block is appended). The
    project's own heading line is kept, so numbering such as "## 6. Code Comments" survives.

    Raises:
        InstallError: if AGENTS.md has a begin marker without an end marker, or two blocks.
    """
    template = (source / TEMPLATE).read_text(encoding="utf-8").strip().splitlines()
    path = project / "AGENTS.md"
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = old.splitlines()

    begins = [i for i, line in enumerate(lines) if BEGIN_RE.match(line)]
    ends = [i for i, line in enumerate(lines) if line.strip() == END]
    if len(begins) > 1 or len(ends) > 1 or (begins and (not ends or ends[0] < begins[0])):
        raise InstallError(f"{path}: malformed dexiotites markers; expected one begin/end pair")

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
    new = "\n".join(parts) + "\n"

    if new == old:
        return Change("AGENTS.md", "unchanged")
    if conflict:
        return Change("AGENTS.md", "conflict", detail, content=new.encode("utf-8"))
    return Change("AGENTS.md", "update" if old else "create", detail, content=new.encode("utf-8"))


# --------------------------------------------------------------------------- other files


def plan_rules_file(project: Path, harness: Harness) -> list[Change]:
    """Plan the file that makes `harness` load AGENTS.md, if it does not load it by itself.

    With an import line, the line is put at the top of the harness's rules file. Without one,
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
    if not harness.import_line:
        if path.exists():
            return [Change(rel, "note", f"exists and is not a symlink to AGENTS.md: left as is; "
                           f"{harness.name} will not load the commenting rules from it")]
        return [Change(rel, "create", link=os.path.relpath("AGENTS.md", Path(rel).parent))]
    if not path.exists():
        return [Change(rel, "create", content=f"{harness.import_line}\n".encode("utf-8"))]
    old = path.read_text(encoding="utf-8")
    if any(line.strip().startswith(harness.import_line) for line in old.splitlines()):
        return [Change(rel, "unchanged")]
    return [Change(rel, "update", f"added the {harness.import_line} import line",
                   content=f"{harness.import_line}\n\n{old}".encode("utf-8"))]


def plan_skill_links(project: Path, skills: list[str], harness: Harness) -> list[Change]:
    """Plan the symlinks that let `harness` see each skill in its own skills folder.

    Nothing is planned for a skill the harness can already reach there (for example when its
    skills folder is itself a symlink to `.agents/skills`). A real folder or file in the way
    is reported and left alone.
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
            changes.append(Change(rel, "unchanged"))
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


def plan_cargo_lints(source: Path, project: Path, lint: bool) -> list[Change]:
    """Plan the documentation `[lints]` block at the end of the project's root Cargo.toml.

    The block is appended between marker comments and replaced in place on later runs. A
    Cargo.toml that already has its own `[lints]` tables, or that is a workspace root, is
    left alone with a note, because merging TOML tables safely needs a human. With `lint`
    False, a block this script added earlier is removed.
    """
    path = project / "Cargo.toml"
    if not path.is_file():
        return []
    old = path.read_text(encoding="utf-8")
    template = (source / "instructions" / "lint" / "rust-cargo-lints.toml").read_text(encoding="utf-8")
    block = f"{TOML_BEGIN}\n{template.strip()}\n{TOML_END}\n"
    pattern = re.compile(r"^# dexiotites:begin doc lints.*?^# dexiotites:end\n?", re.DOTALL | re.MULTILINE)
    if pattern.search(old):
        new = pattern.sub(lambda _: block if lint else "", old, count=1)
        new = new.rstrip("\n") + "\n"
    elif not lint:
        return []
    elif LINTS_TABLE_RE.search(old):
        return [Change("Cargo.toml", "note", "Rust: existing [lints] tables left as is; merge "
                       "instructions/lint/rust-cargo-lints.toml into them by hand")]
    elif re.search(r"^\[workspace\]", old, re.MULTILINE):
        return [Change("Cargo.toml", "note", "Rust: workspace root left as is; add the tables from "
                       "instructions/lint/rust-cargo-lints.toml as [workspace.lints.*] by hand "
                       "(see that file's header)")]
    else:
        new = old.rstrip("\n") + "\n\n" + block
    if new == old:
        return [Change("Cargo.toml", "unchanged")]
    return [Change("Cargo.toml", "update", "documentation [lints] block", content=new.encode("utf-8"))]


# --------------------------------------------------------------------------- driver


def plan(source: Path, project: Path, skills: list[str] | None, lint: bool | None,
         force: bool = False) -> tuple[list[Change], dict]:
    """Compute every change needed to bring one project up to date with the source.

    Args:
        source: Root of the dexiotites checkout.
        project: Root of the target project.
        skills: Skills to add to the set already recorded in the manifest (which starts as
            `annotate-code`), or None to add none.
        lint: False to remove linter configs this script installed, True to install them,
            None to reuse the manifest's choice (default True).
        force: Turn conflicts into updates, replacing the conflicting content.

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
    for skill in skills:
        if not (source / "skills" / skill / "SKILL.md").is_file():
            available = sorted(p.name for p in (source / "skills").iterdir() if p.is_dir())
            raise InstallError(f"no such skill: {skill} (available: {', '.join(available)})")

    files = project_files(project)
    changes = plan_copies(source, project, manifest, skills, lint, files)
    changes.append(plan_agents_md(source, project))
    for harness in HARNESSES:
        changes.extend(plan_rules_file(project, harness))
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
        "files": dict(sorted(hashes.items())),
    }
    old_view = {k: manifest.get(k) for k in ("skills", "lint", "files")}
    content_changed = any(c.status in ("create", "update", "remove") for c in changes)
    if content_changed or old_view != {k: new_manifest[k] for k in old_view}:
        data = (json.dumps(new_manifest, indent=2) + "\n").encode("utf-8")
        status = "update" if (project / MANIFEST).exists() else "create"
        changes.append(Change(MANIFEST, status, content=data))
    else:
        changes.append(Change(MANIFEST, "unchanged"))
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


def run(source: Path, project: Path, args: argparse.Namespace) -> int:
    """Plan, report and (unless checking or blocked by conflicts) apply changes to one project.

    Returns:
        0 if the project is or was brought up to date, 1 if conflicts blocked the run or
        `--check` found pending changes.
    """
    print(f"== {project}")
    if not project.is_dir():
        raise InstallError(f"not a directory: {project}")
    top = _git(project, "rev-parse", "--show-toplevel").stdout.strip()
    if not top or Path(top).resolve() != project.resolve():
        print("  warning: not the root of a git repository; annotate-code's checker needs git")
    lint = False if args.no_lint else (True if args.lint else None)
    changes, manifest = plan(source, project, args.skill, lint, args.force)

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
              "it out before forcing. Project-specific commenting rules belong in AGENTS.md,\n"
              "  outside the dexiotites block (or in dexiotites itself, if every project should get them).")
        return 1
    if args.check:
        if pending or conflicts:
            print(f"  out of date: {len(pending) + len(conflicts)} change(s) pending")
            return 1
        print(f"  up to date ({unchanged} items, dexiotites {manifest['commit'][:7]})")
        return 0
    apply(project, changes)
    if pending:
        print(f"  done: {len(pending)} change(s), {unchanged} unchanged. "
              "Review with `git status`, then commit.")
    else:
        print(f"  already up to date ({unchanged} items)")
    return 0


def bootstrap(argv: list[str]) -> int:
    """Clone dexiotites to a temporary folder and rerun this script from the clone.

    Used when the script runs on its own (piped from curl), without the repository's files
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
