"""
Usage by mention: a term the repository names anywhere is in use.

`prune` measured use as link reachability from the roots, so a fresh
stamp lost every vendored term that agent docs, scripts and workflows
name without linking (disambiguate#84). A mention is a case-insensitive,
hyphen-aware whole-word occurrence of a term's canonical name or slug
in any text file the repository carries. The glossary directory itself
is excluded: a term naming another term is a cross-reference, and the
reachability walk already owns those.

DECISION:SCOPE — "git-tracked" in the ticket is read as "what git would
carry": tracked files plus untracked files that are not ignored. The
post-stamp prune runs before the first commit, when every file is still
untracked, and reading the ticket literally would prune the fresh stamp
it was filed to protect. Ignored files (build output, caches) stay out.
Without a usable git the tree is walked directly, minus `.git/`.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

from disambiguate.glossary import Glossary

# Files above this size are not prose anyone wrote; skipping them keeps
# a stray dump from turning every prune into a full-disk read.
_MAX_BYTES = 1_000_000
_SNIFF_BYTES = 8_192


def mentioned_slugs(glossary: Glossary, repo_root: Path) -> set[str]:
    """
    Return the slugs of every term some file under `repo_root` mentions.

    glossary: the loaded glossary; its directory is excluded from the scan.
    repo_root: the working tree to scan.

    Returns
    -------
    A set of slugs, empty when nothing outside the glossary names a term.

    """
    pattern = _mention_pattern(glossary)
    if pattern is None:
        return set()
    by_variant = _variant_index(glossary)
    glossary_dir = glossary.root.resolve()
    found: set[str] = set()
    for path in _candidate_files(repo_root):
        if glossary_dir in path.resolve().parents:
            continue
        text = _read_text(path)
        if text is None:
            continue
        for match in pattern.finditer(text):
            found.add(by_variant[match.group(0).lower()])
            if len(found) == len(glossary.terms):
                return found
    return found


def _variants(glossary: Glossary) -> Iterator[tuple[str, str]]:
    """Yield `(spelling, slug)` for every spelling that counts as a mention."""
    for slug, term in glossary.terms.items():
        yield slug, slug
        if term.canonical_name:
            yield term.canonical_name, slug


def _variant_index(glossary: Glossary) -> dict[str, str]:
    return {spelling.lower(): slug for spelling, slug in _variants(glossary)}


def _mention_pattern(glossary: Glossary) -> re.Pattern[str] | None:
    """
    One alternation over every spelling, longest first, hyphen-aware.

    The boundary treats `[A-Za-z0-9-]` as word characters, the same rule
    the drift matcher applies: `term` never matches inside
    `unlinked-term`, so a compound term is not a mention of its parts.
    """
    spellings = sorted({s for s, _ in _variants(glossary)}, key=len, reverse=True)
    if not spellings:
        return None
    alternation = "|".join(re.escape(s) for s in spellings)
    return re.compile(
        rf"(?<![A-Za-z0-9-])(?:{alternation})(?![A-Za-z0-9-])",
        re.IGNORECASE,
    )


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
