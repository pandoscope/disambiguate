"""
End-to-end tests for the `prune` verb.

`prune` is the only command that deletes files, so these exercise it
through `main` against a real tree rather than at the planning layer.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import types
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from disambiguate.cli import main

CONSENT = "<!-- d10e: auto-prune -->"
# Resolved once: the fixtures need a real repo, and a resolved path is
# what the bandit rule on partial executable paths asks for.
GIT = shutil.which("git") or "git"


@pytest.fixture(autouse=True)
def _use_generated_terms_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide generated `_terms.py` data for source-tree CLI unit tests."""
    terms_module = types.ModuleType("disambiguate._terms")
    terms_module.__dict__["TERMS"] = ("basename-resolution", "term")
    monkeypatch.setitem(sys.modules, "disambiguate._terms", terms_module)


def run(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run cli.main with cwd and return (exit_code, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    original_cwd = Path.cwd()
    try:
        os.chdir(cwd)
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
    finally:
        os.chdir(original_cwd)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A repo whose README links one of three terms."""
    (tmp_path / ".git").mkdir()
    glossary = tmp_path / "docs" / "glossary"
    glossary.mkdir(parents=True)
    (glossary / "kept.md").write_text(
        f"## Kept\n\n{CONSENT}\n\nLinked from the README.\n", encoding="utf-8"
    )
    (glossary / "vendored.md").write_text(
        f"## Vendored\n\n{CONSENT}\n\nArrived unlinked.\n", encoding="utf-8"
    )
    (glossary / "local.md").write_text(
        "## Local\n\nRepo-owned, never consented.\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "See [kept](docs/glossary/kept.md).\n", encoding="utf-8"
    )
    return tmp_path


def test_prune_deletes_consenting_orphans_only(project: Path) -> None:
    """The default run removes what consented and nothing else."""
    code, _, _ = run(["prune"], project)

    glossary = project / "docs" / "glossary"
    assert code == 0
    assert (glossary / "kept.md").exists()
    assert not (glossary / "vendored.md").exists()
    assert (glossary / "local.md").exists()


def test_prune_dry_run_deletes_nothing_and_names_the_widening_flag(
    project: Path,
) -> None:
    """--dry-run lists both sets and makes --all-orphans discoverable."""
    code, stdout, _ = run(["prune", "--dry-run"], project)

    glossary = project / "docs" / "glossary"
    assert code == 0
    assert (glossary / "vendored.md").exists(), "--dry-run must not delete"
    assert "vendored" in stdout
    assert "local" in stdout
    assert "--all-orphans" in stdout


def test_prune_all_orphans_also_removes_terms_that_never_consented(
    project: Path,
) -> None:
    code, _, _ = run(["prune", "--all-orphans"], project)

    glossary = project / "docs" / "glossary"
    assert code == 0
    assert (glossary / "kept.md").exists()
    assert not (glossary / "vendored.md").exists()
    assert not (glossary / "local.md").exists()


def test_prune_leaves_the_glossary_lint_clean(project: Path) -> None:
    """The point of the feature: --lint passes after pruning."""
    assert run(["--lint"], project)[0] == 1

    run(["prune", "--all-orphans"], project)

    assert run(["--lint"], project)[0] == 0


CHAIN_SLUGS = ("a", "b", "c")


def chain_project(tmp_path: Path, consents: tuple[bool, ...]) -> Path:
    """A repo whose whole glossary is one orphaned chain a -> b -> ..."""
    (tmp_path / ".git").mkdir()
    glossary = tmp_path / "docs" / "glossary"
    glossary.mkdir(parents=True)
    slugs = CHAIN_SLUGS[: len(consents)]
    for index, (slug, consenting) in enumerate(zip(slugs, consents, strict=True)):
        marker = f"{CONSENT}\n\n" if consenting else ""
        if index + 1 < len(slugs):
            target = slugs[index + 1]
            tail = f"Links [{target}]({target}.md).\n"
        else:
            tail = "End of chain.\n"
        (glossary / f"{slug}.md").write_text(
            f"## {slug.upper()}\n\n{marker}{tail}", encoding="utf-8"
        )
    (tmp_path / "README.md").write_text("Nothing linked.\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "consents",
    [(False, False), (True, False), (False, True), (True, True)],
    ids=["nc-nc", "c-nc", "nc-c", "c-c"],
)
def test_dry_run_never_deletes_whatever_the_consent_mix(
    tmp_path: Path, consents: tuple[bool, ...]
) -> None:
    """--dry-run is inert, including the case the default run would take."""
    project = chain_project(tmp_path, consents)
    glossary = project / "docs" / "glossary"

    code, _, _ = run(["prune", "--dry-run"], project)

    assert code == 0
    for slug in CHAIN_SLUGS[: len(consents)]:
        assert (glossary / f"{slug}.md").exists(), f"{slug} must survive --dry-run"


@pytest.mark.parametrize(
    "consents",
    [(False, False), (True, False), (False, True), (True, True)],
    ids=["nc-nc", "c-nc", "nc-c", "c-c"],
)
def test_all_orphans_deletes_the_whole_chain(
    tmp_path: Path, consents: tuple[bool, ...]
) -> None:
    """The widened scope clears an orphaned chain regardless of consent."""
    project = chain_project(tmp_path, consents)
    glossary = project / "docs" / "glossary"

    code, _, _ = run(["prune", "--all-orphans"], project)

    assert code == 0
    for slug in CHAIN_SLUGS[: len(consents)]:
        assert not (glossary / f"{slug}.md").exists()


@pytest.mark.parametrize(
    ("consents", "pruned"),
    [
        ((False, False), False),
        ((True, False), False),
        ((False, True), False),
        ((True, True), True),
    ],
    ids=["nc-nc", "c-nc", "nc-c", "c-c"],
)
def test_default_run_deletes_a_chain_only_when_all_of_it_consents(
    tmp_path: Path, consents: tuple[bool, ...], pruned: bool
) -> None:
    """One non-consenting term anywhere keeps the files on disk."""
    project = chain_project(tmp_path, consents)
    glossary = project / "docs" / "glossary"

    code, _, _ = run(["prune"], project)

    assert code == 0
    for slug in CHAIN_SLUGS[: len(consents)]:
        assert (glossary / f"{slug}.md").exists() is not pruned


@pytest.mark.xfail(strict=True, reason="red: use by link (disambiguate#84)")
def test_prune_keeps_terms_any_file_links_and_drops_bare_mentions(
    tmp_path: Path,
) -> None:
    """
    disambiguate#84: the fresh-stamp case.

    Agent docs and scripts link vendored terms the README never links.
    A term a script only names is not in use: the same spelling may
    mean something else, and the unlinked mention is drift's finding.
    Before the first commit, so every file is untracked.
    """
    subprocess.run(  # noqa: S603 - args are controlled test data.
        [GIT, "init", "-q"], cwd=tmp_path, check=True
    )
    glossary = tmp_path / "docs" / "glossary"
    glossary.mkdir(parents=True)
    for slug, name in (
        ("principal", "Principal"),
        ("decision-memory", "Decision-memory"),
        ("grilling", "Grilling"),
        ("agent-session", "Agent session"),
        ("only-named", "Only named"),
        ("never-named", "Never named"),
    ):
        (glossary / f"{slug}.md").write_text(
            f"## {name}\n\n{CONSENT}\n\nVendored.\n", encoding="utf-8"
        )
    (tmp_path / "README.md").write_text("# Fresh\n\nNo links yet.\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(
        "The [principal](docs/glossary/principal.md) rules. "
        "[[grilling]] records to [the store](docs/glossary/decision-memory.md).\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run.sh").write_text(
        "# one [agent session](../docs/glossary/agent-session.md) per ticket\n"
        "echo 'only named here, never linked'\n",
        encoding="utf-8",
    )

    code, stdout, _ = run(["prune"], tmp_path)

    assert code == 0
    assert (glossary / "principal.md").exists()
    assert (glossary / "decision-memory.md").exists()
    assert (glossary / "grilling.md").exists()
    assert (glossary / "agent-session.md").exists()
    assert not (glossary / "only-named.md").exists()
    assert not (glossary / "never-named.md").exists()
    assert "only-named" in stdout
