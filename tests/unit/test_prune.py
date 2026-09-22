"""
Tests for disambiguate.prune.

Pruning removes terms nothing links. Consent is declared in the term
itself via the `auto-prune` annotation, so the orphan check keeps full
teeth instead of growing an exemption.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from disambiguate.glossary import Glossary, load_glossary
from disambiguate.prune import format_dry_run, plan_prune

CONSENT = "<!-- d10e: auto-prune -->"


def write_glossary(root: Path, terms: dict[str, str]) -> None:
    """Write `slug -> body` term files into a glossary directory."""
    root.mkdir(parents=True, exist_ok=True)
    for slug, body in terms.items():
        (root / f"{slug}.md").write_text(body, encoding="utf-8")


def build(
    tmp_path: Path, terms: dict[str, str], readme: str = ""
) -> tuple[Glossary, list[Path]]:
    """Return (glossary, roots) for a glossary plus a README root."""
    glossary_dir = tmp_path / "docs" / "glossary"
    write_glossary(glossary_dir, terms)
    readme_path = tmp_path / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    return load_glossary(glossary_dir), [readme_path]


def test_prune_removes_consenting_orphans_and_spares_linked_ones(
    tmp_path: Path,
) -> None:
    """
    Consent alone is not enough — a linked term is in use.

    The whole point is that a repo converges to exactly the terms it
    links, so consent plus orphanhood is the removal condition.
    """
    glossary, roots = build(
        tmp_path,
        {
            "linked": f"## Linked\n\n{CONSENT}\n\nIn use.\n",
            "unlinked": f"## Unlinked\n\n{CONSENT}\n\nNobody links this.\n",
        },
        readme="See [linked](docs/glossary/linked.md).\n",
    )

    plan = plan_prune(glossary, roots)

    assert plan.remove == ["unlinked"]
    assert plan.additional == []


def test_all_orphans_widens_scope_to_terms_that_never_consented(
    tmp_path: Path,
) -> None:
    """Without the flag, a non-consenting orphan is only reported."""
    glossary, roots = build(
        tmp_path,
        {
            "consenting": f"## Consenting\n\n{CONSENT}\n\nOpted in.\n",
            "silent": "## Silent\n\nNever opted in.\n",
        },
    )

    default = plan_prune(glossary, roots)
    assert default.remove == ["consenting"]
    assert default.additional == ["silent"]

    widened = plan_prune(glossary, roots, all_orphans=True)
    assert widened.remove == ["consenting", "silent"]
    assert widened.additional == []


def test_a_surviving_orphan_keeps_the_terms_it_links(tmp_path: Path) -> None:
    """
    A term linked by one that stays is in the same orphaned branch.

    `stays` never consented, so it is not going anywhere. Its link puts
    `goes` in the same branch, so `goes` stays too — removing it would
    break a term still on disk and delete the context someone needs to
    repair the missing inbound link. Both are reported: the branch is
    what has to be dealt with.
    """
    glossary, roots = build(
        tmp_path,
        {
            "goes": f"## Goes\n\n{CONSENT}\n\nLinked by a survivor.\n",
            "stays": "## Stays\n\nLinks [goes](goes.md), never consented.\n",
        },
    )

    plan = plan_prune(glossary, roots)

    assert plan.remove == []
    assert plan.additional == ["goes", "stays"]


def test_removing_orphans_cannot_orphan_a_surviving_term(tmp_path: Path) -> None:
    """
    The cascade #52 worried about cannot happen.

    Orphanhood is reachability from the roots, so a reachable term's
    whole path is reachable. `deep` is reachable via `hub`, and neither
    is touched even though `island` — which also links `deep` — goes.
    """
    glossary, roots = build(
        tmp_path,
        {
            "hub": "## Hub\n\nLinks [deep](deep.md).\n",
            "deep": "## Deep\n\nReachable through hub.\n",
            "island": f"## Island\n\n{CONSENT}\n\nAlso links [deep](deep.md).\n",
        },
        readme="See [hub](docs/glossary/hub.md).\n",
    )

    plan = plan_prune(glossary, roots)

    assert plan.remove == ["island"]


# --- The consent matrix ------------------------------------------------
#
# An orphaned branch is pruned only when EVERY term in it consents. One
# non-consenting term anywhere keeps the whole branch: the
# non-consenting term is a real finding, and the terms around it are the
# context someone needs to fix the missing link. Deleting that context
# to tidy the report would destroy the evidence.

CHAIN_SLUGS = ("a", "b", "c")


def chain(consents: tuple[bool, ...]) -> dict[str, str]:
    """Build an orphaned chain a -> b -> ... with per-term consent."""
    slugs = CHAIN_SLUGS[: len(consents)]
    terms: dict[str, str] = {}
    for index, (slug, consenting) in enumerate(zip(slugs, consents, strict=True)):
        marker = f"{CONSENT}\n\n" if consenting else ""
        if index + 1 < len(slugs):
            target = slugs[index + 1]
            tail = f"Links [{target}]({target}.md).\n"
        else:
            tail = "End of chain.\n"
        terms[slug] = f"## {slug.upper()}\n\n{marker}{tail}"
    return terms


@pytest.mark.parametrize(
    ("consents", "pruned"),
    [
        ((False, False), False),
        ((True, False), False),
        ((False, True), False),
        ((True, True), True),
        ((False, True, True), False),
        ((True, False, True), False),
        ((True, True, False), False),
        ((True, True, True), True),
    ],
    ids=[
        "nc-nc",
        "c-nc",
        "nc-c",
        "c-c",
        "nc-c-c",
        "c-nc-c",
        "c-c-nc",
        "c-c-c",
    ],
)
def test_default_prunes_a_branch_only_when_every_term_consents(
    tmp_path: Path, consents: tuple[bool, ...], pruned: bool
) -> None:
    """One non-consenting term anywhere keeps the whole branch."""
    slugs = list(CHAIN_SLUGS[: len(consents)])
    glossary, roots = build(tmp_path, chain(consents))

    plan = plan_prune(glossary, roots)

    if pruned:
        assert plan.remove == slugs
        assert plan.additional == []
    else:
        assert plan.remove == []
        assert plan.additional == slugs


@pytest.mark.parametrize(
    "consents",
    [(False, False), (True, False), (False, True), (True, True)],
    ids=["nc-nc", "c-nc", "nc-c", "c-c"],
)
def test_all_orphans_removes_every_orphan_regardless_of_consent(
    tmp_path: Path, consents: tuple[bool, ...]
) -> None:
    """The widened scope ignores consent entirely."""
    slugs = list(CHAIN_SLUGS[: len(consents)])
    glossary, roots = build(tmp_path, chain(consents))

    plan = plan_prune(glossary, roots, all_orphans=True)

    assert plan.remove == slugs
    assert plan.additional == []


def test_dry_run_distinguishes_no_orphans_from_protected_orphans(
    tmp_path: Path,
) -> None:
    """
    "Nothing to remove" has two causes and they read differently.

    A clean glossary and one whose orphans are all held by a
    non-consenting neighbour are not the same situation, and the second
    one still needs acting on.
    """
    clean, clean_roots = build(
        tmp_path / "clean",
        {"used": "## Used\n\nLinked.\n"},
        readme="See [used](docs/glossary/used.md).\n",
    )
    assert "no orphaned terms" in format_dry_run(plan_prune(clean, clean_roots))

    held, held_roots = build(tmp_path / "held", chain((True, False)))
    message = format_dry_run(plan_prune(held, held_roots))
    assert "no orphaned terms" not in message
    assert "--all-orphans" in message


def test_used_terms_count_as_roots_and_keep_what_they_link(tmp_path: Path) -> None:
    """
    A term some file links is in use, and so is what it links.

    disambiguate#84: reachability from the roots was the only form of
    use, so a vendored term agent docs link but the roots never reach
    was pruned. A used slug joins the roots of the walk.
    """
    glossary, roots = build(
        tmp_path,
        {
            "linked": f"## Linked\n\n{CONSENT}\n\nSee [child](child.md).\n",
            "child": f"## Child\n\n{CONSENT}\n\nLinked only from linked.\n",
            "silent": f"## Silent\n\n{CONSENT}\n\nNobody links this.\n",
        },
    )

    plan = plan_prune(glossary, roots, used={"linked"})

    assert plan.remove == ["silent"]
    assert plan.additional == []
