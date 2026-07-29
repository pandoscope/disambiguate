"""Tests for disambiguate.lint."""

from __future__ import annotations

from pathlib import Path

from disambiguate.glossary import load_glossary
from disambiguate.lint import LintFinding, lint_glossary


def _write(directory: Path, slug: str, body: str) -> None:
    (directory / f"{slug}.md").write_text(body, encoding="utf-8")


def _setup_glossary(tmp_path: Path) -> Path:
    glossary_dir = tmp_path / "glossary"
    glossary_dir.mkdir()
    return glossary_dir


def test_lint_clean_glossary(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "term", "## Term\n\nbody\n")
    _write(glossary_dir, "slug", "## Slug\n\n[term](term.md)\n")
    root = tmp_path / "README.md"
    root.write_text("[t](glossary/term.md) and [[slug]]\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert findings == []


def test_lint_detects_cycle(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "a", "## A\n\n[b](b.md)\n")
    _write(glossary_dir, "b", "## B\n\n[a](a.md)\n")
    root = tmp_path / "README.md"
    root.write_text("[a](glossary/a.md) [b](glossary/b.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert any(f.kind == "cycle" for f in findings)


def test_lint_detects_broken_cross_reference(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "a", "## A\n\n[ghost](ghost.md)\n")
    root = tmp_path / "README.md"
    root.write_text("[a](glossary/a.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert any(f.kind == "broken-link" and "ghost" in f.message for f in findings)


def test_lint_detects_missing_h2(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "a", "no heading here\n")
    root = tmp_path / "README.md"
    root.write_text("[a](glossary/a.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert any(f.kind == "missing-h2" for f in findings)


def test_lint_detects_malformed_pipe_wikilinks_in_term_files(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "term", "## Term\n\nbody\n")
    _write(
        glossary_dir,
        "a",
        "## A\n\n[[term|]] and [[term|x|y]] and [[|just text]]\n",
    )
    root = tmp_path / "README.md"
    root.write_text("[a](glossary/a.md) [t](glossary/term.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    malformed = [f for f in findings if f.kind == "malformed-wikilink"]
    assert len(malformed) == 3
    assert all("a" in f.message for f in malformed)
    assert any("[[term|]]" in f.message for f in malformed)
    assert any("[[term|x|y]]" in f.message for f in malformed)
    assert any("[[|just text]]" in f.message for f in malformed)


def test_lint_ignores_malformed_wikilinks_in_external_docs(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "term", "## Term\n\nbody\n")
    root = tmp_path / "README.md"
    root.write_text("[[term|]] and [t](glossary/term.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert findings == []


def test_lint_detects_invalid_slug_uppercase(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "MyTerm", "## My Term\n\n")
    root = tmp_path / "README.md"
    root.write_text("[m](glossary/MyTerm.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert any(f.kind == "invalid-slug" and "MyTerm" in f.message for f in findings)


def test_lint_detects_invalid_slug_underscore(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "my_term", "## My Term\n\n")
    root = tmp_path / "README.md"
    root.write_text("[m](glossary/my_term.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert any(f.kind == "invalid-slug" and "my_term" in f.message for f in findings)


def test_lint_detects_invalid_slug_consecutive_dashes(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "my--term", "## My Term\n\n")
    root = tmp_path / "README.md"
    root.write_text("[m](glossary/my--term.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert any(f.kind == "invalid-slug" and "my--term" in f.message for f in findings)


def test_lint_detects_invalid_slug_leading_or_trailing_dash(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "-term", "## Term\n\n")
    _write(glossary_dir, "term-", "## Term\n\n")
    root = tmp_path / "README.md"
    root.write_text(
        "[a](glossary/-term.md)\n[b](glossary/term-.md)\n",
        encoding="utf-8",
    )
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    invalid = [f for f in findings if f.kind == "invalid-slug"]
    assert any("-term" in f.message for f in invalid)
    assert any("term-" in f.message for f in invalid)


def test_lint_accepts_canonical_slugs(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "topological-order", "## Topological Order\n\n")
    _write(glossary_dir, "term2", "## Term 2\n\n")
    _write(glossary_dir, "a", "## A\n\n")
    root = tmp_path / "README.md"
    root.write_text(
        "[t](glossary/topological-order.md) [t2](glossary/term2.md) "
        "[a](glossary/a.md)\n",
        encoding="utf-8",
    )
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert not any(f.kind == "invalid-slug" for f in findings)


def test_lint_detects_orphans(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "linked", "## Linked\n\nbody\n")
    _write(glossary_dir, "orphan", "## Orphan\n\nbody\n")
    root = tmp_path / "README.md"
    root.write_text("[linked](glossary/linked.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    orphan_findings = [f for f in findings if f.kind == "orphan"]
    assert len(orphan_findings) == 1
    assert "orphan" in orphan_findings[0].message


def test_lint_orphan_message_lists_all_orphans(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "a", "## A\n\n")
    _write(glossary_dir, "b", "## B\n\n")
    _write(glossary_dir, "c", "## C\n\n")
    root = tmp_path / "README.md"
    root.write_text("[a](glossary/a.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    orphan_message = next(f.message for f in findings if f.kind == "orphan")
    assert "b" in orphan_message
    assert "c" in orphan_message


def test_lint_reachability_through_external_doc(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "a", "## A\n\nbody\n")
    arch = tmp_path / "architecture.md"
    arch.write_text("[a](glossary/a.md)\n", encoding="utf-8")
    root = tmp_path / "README.md"
    root.write_text("[arch](architecture.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert findings == []


def test_lint_reachability_tolerates_external_cycles(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "a", "## A\n\nbody\n")
    arch = tmp_path / "architecture.md"
    other = tmp_path / "other.md"
    arch.write_text("[other](other.md) [a](glossary/a.md)\n", encoding="utf-8")
    other.write_text("[arch](architecture.md)\n", encoding="utf-8")
    root = tmp_path / "README.md"
    root.write_text("[arch](architecture.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert findings == []


def test_lint_reachability_through_chain_in_glossary(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "a", "## A\n\n[b](b.md)\n")
    _write(glossary_dir, "b", "## B\n\n[c](c.md)\n")
    _write(glossary_dir, "c", "## C\n\nbody\n")
    root = tmp_path / "README.md"
    root.write_text("[a](glossary/a.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert findings == []


def test_lint_orphan_message_includes_override_hint(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "orphan", "## Orphan\n\n")
    root = tmp_path / "README.md"
    root.write_text("nothing here\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    orphan = next(f for f in findings if f.kind == "orphan")
    assert "--roots" in orphan.message
    assert "DISAMBIGUATE_ROOTS" in orphan.message


def test_finding_has_kind_and_message() -> None:
    finding = LintFinding(kind="cycle", message="x")
    assert finding.kind == "cycle"
    assert finding.message == "x"


def test_lint_reachability_through_display_text_wikilink(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "a", "## A\n\nbody\n")
    root = tmp_path / "README.md"
    root.write_text("[[a|the A term]]\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert not any(f.kind == "orphan" for f in findings)


def test_auto_prune_marker_does_not_disturb_lint_or_the_h2(tmp_path: Path) -> None:
    """
    A consenting term is an ordinary term to every other check.

    The marker sits in an HTML comment so it stays invisible in rendered
    markdown, keeps the H2 first, and produces no finding of its own.
    Acceptance criterion from frankify-app/disambiguate#52.
    """
    glossary_dir = _setup_glossary(tmp_path)
    _write(
        glossary_dir,
        "marked",
        "## Marked\n\n<!-- d10e: auto-prune -->\n\nLinks [plain](plain.md).\n",
    )
    _write(glossary_dir, "plain", "## Plain\n\nbody\n")
    root = tmp_path / "README.md"
    root.write_text("[m](glossary/marked.md)\n", encoding="utf-8")

    glossary = load_glossary(glossary_dir)

    assert glossary.terms["marked"].canonical_name == "Marked"
    assert glossary.terms["marked"].auto_prune is True
    assert lint_glossary(glossary, roots=[root]) == []


def test_link_as_if_exists_is_caught_as_broken_link(tmp_path: Path) -> None:
    """
    Pin the link-as-if-exists convention (#35).

    A new concept is introduced by cross-referencing its slug as if the
    term file already existed. Until the file lands, the existing
    broken-link check reports it fatally — "used but never defined" needs
    no extra checker.
    """
    glossary_dir = _setup_glossary(tmp_path)
    _write(
        glossary_dir,
        "a",
        "## A\n\nUses the [not-yet-defined](not-yet-defined.md) concept.\n",
    )
    root = tmp_path / "README.md"
    root.write_text("[a](glossary/a.md)\n", encoding="utf-8")
    glossary = load_glossary(glossary_dir)
    findings = lint_glossary(glossary, roots=[root])
    assert any(
        f.kind == "broken-link" and "not-yet-defined" in f.message for f in findings
    )
