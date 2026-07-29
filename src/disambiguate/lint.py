"""
Lint a glossary against seven fatal-on-violation checks.

The checks: cycles, broken cross-references, duplicate slugs, missing H2
headings, invalid slug format, malformed piped wikilinks (glossary term
files only), and reachability orphans. Duplicate slugs are
caught by the loader and surface as a `DuplicateSlugError`; the other five
are reported as `LintFinding` objects so the CLI can present all problems
at once instead of stopping on the first.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from graphlib import CycleError as _GraphlibCycleError
from graphlib import TopologicalSorter
from pathlib import Path

from .glossary import Glossary
from .parser import (
    extract_malformed_wikilinks,
    extract_md_link_paths,
    extract_wikilink_slugs,
)

logger = logging.getLogger(__name__)

# Canonical slug format: lowercase letters and digits, with single hyphens
# between segments. No leading/trailing hyphens, no consecutive hyphens.
_CANONICAL_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class LintFinding:
    """
    A single lint violation.

    kind: one of "cycle", "broken-link", "missing-h2", "invalid-slug",
        "malformed-wikilink", "orphan". "duplicate-slug" is raised at load
        time and never reaches a finding.
    message: human-readable description, used directly in error output.
    """

    kind: str
    message: str


def _check_cycles(glossary: Glossary) -> list[LintFinding]:
    """Return one finding per cycle detected in the dependency graph."""
    sorter: TopologicalSorter[str] = TopologicalSorter()
    for slug, deps in glossary.dependencies.items():
        sorter.add(slug, *deps)
    try:
        sorter.prepare()
    except _GraphlibCycleError as e:
        detail = e.args[1] if len(e.args) > 1 else e
        return [
            LintFinding(
                kind="cycle",
                message=f"Cycle in dependency graph: {detail}",
            )
        ]
    return []


def _check_broken_links(glossary: Glossary) -> list[LintFinding]:
    """Return one finding per broken cross-reference, deterministic order."""
    findings: list[LintFinding] = []
    for slug in sorted(glossary.broken_links):
        for target in glossary.broken_links[slug]:
            findings.append(
                LintFinding(
                    kind="broken-link",
                    message=(
                        f"{slug}: cross-reference to unknown term "
                        f"{target!r} (no glossary file matches)"
                    ),
                )
            )
    return findings


def _check_missing_h2(glossary: Glossary) -> list[LintFinding]:
    """Return one finding per term file lacking an H2 heading."""
    findings: list[LintFinding] = []
    for slug in sorted(glossary.terms):
        term = glossary.terms[slug]
        if term.canonical_name is None:
            findings.append(
                LintFinding(
                    kind="missing-h2",
                    message=f"{slug}: missing required H2 heading in {term.path}",
                )
            )
    return findings


def _check_slug_format(glossary: Glossary) -> list[LintFinding]:
    """Return one finding per slug not matching the canonical slug format."""
    findings: list[LintFinding] = []
    for slug in sorted(glossary.terms):
        if _CANONICAL_SLUG.fullmatch(slug):
            continue
        findings.append(
            LintFinding(
                kind="invalid-slug",
                message=(
                    f"{slug}: slug does not match canonical format "
                    f"(lowercase letters, digits, and single hyphens "
                    f"between segments; no leading or trailing hyphen)"
                ),
            )
        )
    return findings


def _check_malformed_wikilinks(glossary: Glossary) -> list[LintFinding]:
    """
    Return one finding per malformed piped wikilink in glossary term files.

    Only term files are checked — external documents visited by the
    reachability walk are not Disambiguate's to police.
    """
    findings: list[LintFinding] = []
    for slug in sorted(glossary.terms):
        term = glossary.terms[slug]
        for raw_link in extract_malformed_wikilinks(term.body):
            findings.append(
                LintFinding(
                    kind="malformed-wikilink",
                    message=(
                        f"{slug}: malformed piped wikilink {raw_link} in "
                        f"{term.path} (expected [[slug|display text]] with "
                        f"non-empty slug and display text, single pipe)"
                    ),
                )
            )
    return findings


def walk_reachable(
    roots: Iterable[Path],
    glossary: Glossary,
) -> set[Path]:
    """
    Return the set of `.md` file paths reachable from `roots` by link.

    Walks both glossary terms and external markdown documents. Cycles are
    handled by the visited-set check, not by topological sort. Non-`.md`
    links and external URLs are ignored.
    """
    visited: set[Path] = set()
    queue: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in visited:
            queue.append(resolved)

    # Cache slug -> term path for wikilink and basename-fallback resolution.
    slug_to_path: dict[str, Path] = {
        slug: term.path.resolve() for slug, term in glossary.terms.items()
    }

    while queue:
        current = queue.pop()
        if current in visited:
            continue
        visited.add(current)
        try:
            text = current.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("could not read %s during reachability walk: %s", current, e)
            continue

        for raw_path in extract_md_link_paths(text):
            target_path = (current.parent / raw_path).resolve()
            if target_path.is_file() and target_path not in visited:
                queue.append(target_path)
            else:
                # Path-relative resolution failed; fall back to basename
                # resolution against glossary slugs. Covers the case where
                # an external doc writes `[term](term.md)` from a directory
                # that doesn't actually contain the file.
                basename = raw_path.rsplit("/", 1)[-1]
                slug = basename[: -len(".md")] if basename.endswith(".md") else basename
                fallback = slug_to_path.get(slug)
                if fallback is not None and fallback not in visited:
                    queue.append(fallback)

        for slug in extract_wikilink_slugs(text):
            target = slug_to_path.get(slug)
            if target is not None and target not in visited:
                queue.append(target)

    return visited


def orphan_slugs(glossary: Glossary, roots: list[Path]) -> list[str]:
    """
    Return the slugs of every term not reachable from `roots`, sorted.

    Reachability is transitive through cross-references, so a term
    reachable from a root has a path made entirely of reachable terms.
    That makes the orphan set closed under its own removal: deleting
    orphans can never orphan a term that was reachable.
    """
    visited = walk_reachable(roots, glossary)
    return sorted(
        slug
        for slug, term in glossary.terms.items()
        if term.path.resolve() not in visited
    )


def _check_orphans(glossary: Glossary, roots: list[Path]) -> list[LintFinding]:
    """Return one finding listing every term not reachable from `roots`."""
    orphan_slugs_found = orphan_slugs(glossary, roots)
    if not orphan_slugs_found:
        return []

    root_names = ", ".join(p.name for p in roots) or "(none)"
    bullets = "\n".join(f"  - {slug}" for slug in orphan_slugs_found)
    message = (
        f"Orphan terms found (not reachable from roots: {root_names}):\n"
        f"{bullets}\n"
        f"\nOrphans must be reachable from at least one root via markdown links.\n"
        f"Add links from a root document, or override roots with `--roots <files>`\n"
        f"or `DISAMBIGUATE_ROOTS=...`."
    )
    return [LintFinding(kind="orphan", message=message)]


def lint_glossary(glossary: Glossary, roots: list[Path]) -> list[LintFinding]:
    """
    Run every lint check against `glossary` and return the combined findings.

    glossary: loaded glossary.
    roots: documents from which reachability is measured. Caller is
        responsible for resolving the roots (flag, env, default).

    Returns
    -------
    A list of LintFinding objects; empty list means clean. Order is
    deterministic: cycles, broken-links, missing-h2, invalid-slug,
    malformed-wikilink, orphans.

    """
    findings: list[LintFinding] = []
    findings.extend(_check_cycles(glossary))
    findings.extend(_check_broken_links(glossary))
    findings.extend(_check_missing_h2(glossary))
    findings.extend(_check_slug_format(glossary))
    findings.extend(_check_malformed_wikilinks(glossary))
    findings.extend(_check_orphans(glossary, roots))
    return findings
