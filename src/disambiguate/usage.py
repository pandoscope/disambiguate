"""
Usage by link: a term any file in the repository links is in use.

`prune` measured use as link reachability from the roots, so a fresh
stamp lost every vendored term that agent docs and scripts link while
the roots do not (disambiguate#84). Use is an explicit cross-reference
to the term, markdown or wiki syntax, in any text file the repository
carries. The glossary directory itself is excluded: a term linking
another term is a cross-reference, and the reachability walk already
owns those.

A bare mention never counts. The same spelling can carry another
meaning, and keeping a term for it would blunt prune; an unlinked
mention is what `--drift` reports instead.

DECISION:SCOPE — "git-tracked" in the ticket is read as "what git would
carry": tracked files plus untracked files that are not ignored. The
post-stamp prune runs before the first commit, when every file is still
untracked, and reading the ticket literally would prune the fresh stamp
it was filed to protect. Ignored files (build output, caches) stay out.
Without a usable git the tree is walked directly, minus `.git/`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from disambiguate.glossary import Glossary
from disambiguate.parser import extract_all_link_slugs

# Files above this size are not prose anyone wrote; skipping them keeps
# a stray dump from turning every prune into a full-disk read.
_MAX_BYTES = 1_000_000
_SNIFF_BYTES = 8_192


def linked_slugs(glossary: Glossary, repo_root: Path) -> set[str]:
    """
    Return the slugs of every term some file under `repo_root` links.

    glossary: the loaded glossary; its directory is excluded from the scan.
    repo_root: the working tree to scan.

    Returns
    -------
    A set of slugs, empty when nothing outside the glossary links a term.
    A link whose slug names no term is ignored; code is never scanned.

    """
    glossary_dir = glossary.root.resolve()
    found: set[str] = set()
    for path in _candidate_files(repo_root):
        if glossary_dir in path.resolve().parents:
            continue
        text = _read_text(path)
        if text is None:
            continue
        found.update(
            slug for slug in extract_all_link_slugs(text) if slug in glossary.terms
        )
        if len(found) == len(glossary.terms):
            return found
    return found


def _candidate_files(repo_root: Path) -> list[Path]:
    """Every file git would carry; the whole tree minus `.git/` without git."""
    listed = _git_listed(repo_root)
    if listed is not None:
        return listed
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        files.extend(Path(dirpath) / name for name in filenames)
    return files


def _git_listed(repo_root: Path) -> list[Path] | None:
    """Tracked plus untracked-and-not-ignored paths, or None without git."""
    try:
        result = subprocess.run(
            [  # noqa: S607 — git resolved on PATH by design
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [
        repo_root / entry.decode("utf-8", errors="surrogateescape")
        for entry in result.stdout.split(b"\0")
        if entry
    ]


def _read_text(path: Path) -> str | None:
    """The file's text, or None for a binary, oversized or unreadable file."""
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None
        with path.open("rb") as handle:
            head = handle.read(_SNIFF_BYTES)
            if b"\0" in head:
                return None
            rest = handle.read()
    except OSError:
        return None
    return (head + rest).decode("utf-8", errors="ignore")
