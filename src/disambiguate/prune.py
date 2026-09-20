"""
Remove glossary terms that nothing links or mentions.

A repo can acquire terms it does not link. Those are `orphan` findings,
so `--lint` fails on a repo that did nothing wrong. Exempting them
would make "unlinked" a legitimate state and blunt the check for
everyone; removing them instead keeps the check's teeth and lets the
repo converge to exactly the terms it links.

Removal is consent-based: a term opts in with the `auto-prune`
annotation. `--all-orphans` widens the scope to orphans that never
opted in.
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

from disambiguate.glossary import Glossary
from disambiguate.lint import orphan_slugs

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrunePlan:
    """
    What a prune run would remove.

    remove: slugs to remove now — every term of an orphaned branch
        that consents, or simply orphaned when the caller widened the
        scope.
    additional: slugs `--all-orphans` would remove on top of `remove`;
        empty when the scope is already widened.
    """

    remove: list[str] = field(default_factory=list)
    additional: list[str] = field(default_factory=list)


def plan_prune(
    glossary: Glossary,
    roots: list[Path],
    *,
    all_orphans: bool = False,
    used: Collection[str] = (),
) -> PrunePlan:
    """
    Decide which terms a prune run removes.

    glossary: the loaded glossary.
    roots: documents reachability is measured from.
    all_orphans: also remove orphans that never declared consent.
    used: slugs the repository mentions without linking (disambiguate#84).
        Each joins the roots of the walk, so a mentioned term is in use
        and so is everything it links.

    Returns
    -------
    A PrunePlan. Pure — reads the graph, touches no files.

    """
    del used  # stub: the seam exists, the walk widens in the next commit
    orphans = orphan_slugs(glossary, roots)
    if all_orphans:
        return PrunePlan(remove=list(orphans), additional=[])

    # DECISION: consent is decided per orphaned BRANCH, not per term. A
    # branch goes only when every term in it consents; one
    # non-consenting term anywhere keeps all of it.
    #
    # Branches are connected components, traversed without regard to
    # link direction. Direction would let `consenting -> non-consenting`
    # delete the consenting end, and that case is the one most worth
    # keeping: a consenting term pointing at a non-consenting orphan is
    # most likely a MISSING inbound link, and the consenting term is the
    # context someone needs to fix it. Deleting the context to tidy the
    # report destroys the evidence.
    #
    # This is the authoritative home for that reasoning.
    # docs/glossary/prune.md states the resulting behavior for readers of
    # the vocabulary and points here rather than restating it; the two
    # change together.
    remove: list[str] = []
    for branch in _branches(glossary, orphans):
        if all(glossary.terms[slug].auto_prune for slug in branch):
            remove.extend(branch)
    remove.sort()
    additional = [slug for slug in orphans if slug not in set(remove)]
    return PrunePlan(remove=remove, additional=additional)


def _branches(glossary: Glossary, orphans: list[str]) -> list[list[str]]:
    """
    Group `orphans` into connected components, ignoring link direction.

    Only orphan-to-orphan links join a component: a link to a term the
    roots still reach says nothing about the orphan's own fate, and no
    reachable term can link an orphan without making it reachable.
    """
    candidates = set(orphans)
    neighbours: dict[str, set[str]] = {slug: set() for slug in candidates}
    for slug in candidates:
        for target in glossary.terms[slug].link_slugs:
            if target in candidates and target != slug:
                neighbours[slug].add(target)
                neighbours[target].add(slug)

    seen: set[str] = set()
    components: list[list[str]] = []
    for slug in orphans:
        if slug in seen:
            continue
        component: list[str] = []
        queue = [slug]
        while queue:
            current = queue.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            queue.extend(neighbours[current] - seen)
        components.append(sorted(component))
    return components


def apply_prune(plan: PrunePlan, glossary: Glossary) -> list[Path]:
    """
    Delete the term files named by `plan.remove`.

    Returns
    -------
    The paths removed, in plan order.

    """
    removed: list[Path] = []
    for slug in plan.remove:
        path = glossary.terms[slug].path
        path.unlink()
        logger.debug("pruned term %s (%s)", slug, path)
        removed.append(path)
    return removed


def format_dry_run(plan: PrunePlan) -> str:
    """
    Describe a plan without acting on it.

    Names `--all-orphans` whenever the widened set is non-empty — that is
    what makes the flag discoverable instead of merely guessable.
    """
    lines: list[str] = []
    if plan.remove:
        lines.append(f"Would remove {len(plan.remove)} orphaned term(s):")
        lines.extend(f"  - {slug}" for slug in plan.remove)
    elif plan.additional:
        lines.append(
            "Nothing to remove: every orphaned branch holds a term that never "
            "consented."
        )
    else:
        lines.append("Nothing to remove: the glossary has no orphaned terms.")

    if plan.additional:
        lines.append("")
        lines.append(
            f"Orphaned without consent — run with `--all-orphans` to also "
            f"remove these {len(plan.additional)}:"
        )
        lines.extend(f"  - {slug}" for slug in plan.additional)

    return "\n".join(lines)
