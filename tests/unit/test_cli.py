"""Integration tests for the CLI dispatcher."""

from __future__ import annotations

import io
import os
import sys
import types
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from disambiguate import bundled
from disambiguate.cli import main
from disambiguate.glossary import load_glossary

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _setup_project(tmp_path: Path) -> Path:
    """Build a synthetic repo with a small docs/glossary/ tree."""
    (tmp_path / ".git").mkdir()
    glossary = tmp_path / "docs" / "glossary"
    glossary.mkdir(parents=True)
    (glossary / "a.md").write_text("## A\n\n[b](b.md)\n", encoding="utf-8")
    (glossary / "b.md").write_text("## B\n\n[c](c.md)\n", encoding="utf-8")
    (glossary / "c.md").write_text("## C\n\nbody\n", encoding="utf-8")
    (glossary / "topological-order.md").write_text(
        "## Topological Order\n\n[a](a.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "[topological-order](docs/glossary/topological-order.md)\n",
        encoding="utf-8",
    )
    return tmp_path


def _run(argv: list[str], cwd: Path) -> tuple[int, str, str]:
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


@pytest.fixture(autouse=True)
def _use_generated_terms_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide generated `_terms.py` data for source-tree CLI unit tests."""
    terms_module = types.ModuleType("disambiguate._terms")
    terms_module.__dict__["TERMS"] = ("basename-resolution", "term")
    monkeypatch.setitem(sys.modules, "disambiguate._terms", terms_module)


def _use_source_bundled_glossary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use source glossary docs as bundled data for source-tree CLI tests."""
    monkeypatch.setattr(
        bundled,
        "load_bundled_glossary",
        lambda: load_glossary(PROJECT_ROOT / "docs" / "glossary"),
    )


def test_default_no_args_renders_full_glossary(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    code, stdout, _ = _run([], project)
    assert code == 0
    assert "## A" in stdout
    assert "## B" in stdout
    assert "## C" in stdout
    assert stdout.index("## C") < stdout.index("## B") < stdout.index("## A")


def test_default_renders_requested_slug_and_deps(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    code, stdout, _ = _run(["a"], project)
    assert code == 0
    assert "## A" in stdout
    assert stdout.index("## C") < stdout.index("## B") < stdout.index("## A")


def test_default_unknown_slug_fails(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    code, _, stderr = _run(["unknown"], project)
    assert code == 1
    assert "unknown" in stderr.lower()


def test_default_phrase_argument_resolves_slug(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    code, stdout, _ = _run(["Topological Order"], project)
    assert code == 0
    assert "## Topological Order" in stdout
    assert "## A" in stdout


def test_default_non_slug_characters_normalize_to_single_dashes(
    tmp_path: Path,
) -> None:
    project = _setup_project(tmp_path)
    code, stdout, _ = _run(["Topological___@@@Order"], project)
    assert code == 0
    assert "## Topological Order" in stdout


def test_default_unknown_phrase_fails_with_normalized_slug(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    code, _, stderr = _run(["No Such Term"], project)
    assert code == 1
    assert "no-such-term" in stderr


def test_default_exact_whitespace_slug_normalizes_before_lookup(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    glossary = project / "docs" / "glossary"
    (glossary / "Legacy Term.md").write_text("## Legacy Term\n\n", encoding="utf-8")
    code, _, stderr = _run(["Legacy Term"], project)
    assert code == 1
    assert "legacy-term" in stderr


def test_lint_passes_clean_glossary(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    code, _, _ = _run(["--lint"], project)
    assert code == 0


def test_lint_reports_orphans(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    (tmp_path / "README.md").write_text("nothing here\n", encoding="utf-8")
    code, _, stderr = _run(["--lint"], project)
    assert code == 1
    assert "Orphan" in stderr or "orphan" in stderr


def test_lint_uses_roots_flag(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    other = tmp_path / "other.md"
    other.write_text(
        "[topological-order](docs/glossary/topological-order.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("nothing here\n", encoding="utf-8")
    code, _, _ = _run(["--lint", "--roots", str(other)], project)
    assert code == 0


def test_lint_uses_roots_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _setup_project(tmp_path)
    other = tmp_path / "other.md"
    other.write_text(
        "[topological-order](docs/glossary/topological-order.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("nothing here\n", encoding="utf-8")
    monkeypatch.setenv("DISAMBIGUATE_ROOTS", str(other))
    code, _, _ = _run(["--lint"], project)
    assert code == 0


def test_lint_roots_glob(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    docs_dir = tmp_path / "extra"
    docs_dir.mkdir()
    (docs_dir / "x.md").write_text(
        "[topological-order](../docs/glossary/topological-order.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("nothing here\n", encoding="utf-8")
    code, _, _ = _run(["--lint", "--roots", str(docs_dir / "*.md")], project)
    assert code == 0


def test_lint_missing_root_fails(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    code, _, stderr = _run(
        ["--lint", "--roots", str(tmp_path / "no-such-file.md")], project
    )
    assert code == 1
    assert "not found" in stderr.lower() or "missing" in stderr.lower()


def test_lint_no_git_root_fails(tmp_path: Path) -> None:
    glossary = tmp_path / "docs" / "glossary"
    glossary.mkdir(parents=True)
    (glossary / "a.md").write_text("## A\n\n", encoding="utf-8")
    code, _, stderr = _run(["--lint"], tmp_path)
    assert code == 1
    assert ".git" in stderr or "repo" in stderr.lower()


def test_explain_no_args_prints_preamble_and_full_glossary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _setup_project(tmp_path)
    _use_source_bundled_glossary(monkeypatch)
    code, stdout, _ = _run(["--explain"], project)
    assert code == 0
    assert "topological order" in stdout.lower()
    assert "disambiguate`" in stdout
    # Bundled glossary terms appear regardless of user glossary.
    assert "## Term" in stdout
    assert "## Disambiguate" in stdout


def test_explain_with_term_renders_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _setup_project(tmp_path)
    _use_source_bundled_glossary(monkeypatch)
    code, stdout, _ = _run(["--explain", "github-format"], project)
    assert code == 0
    assert "## Github format" in stdout or "## GitHub format" in stdout
    assert "disambiguate github-format`" in stdout


def test_explain_with_phrase_renders_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _setup_project(tmp_path)
    _use_source_bundled_glossary(monkeypatch)
    code, stdout, _ = _run(["--explain", "topological order"], project)
    assert code == 0
    assert "## Topological order" in stdout
    assert "disambiguate topological-order`" in stdout


def test_explain_unknown_phrase_fails_with_normalized_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _setup_project(tmp_path)
    _use_source_bundled_glossary(monkeypatch)
    code, _, stderr = _run(["--explain", "No Such Term"], project)
    assert code == 1
    assert "no-such-term" in stderr


def test_explain_ignores_user_glossary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _setup_project(tmp_path)
    _use_source_bundled_glossary(monkeypatch)
    # User glossary has terms a, b, c — bundled glossary has different terms.
    code, stdout, _ = _run(["--explain", "term"], project)
    assert code == 0
    assert "atomic unit" in stdout  # text from bundled term.md


def test_from_mode_reads_path(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("see [a](docs/glossary/a.md) and [[b]]\n", encoding="utf-8")
    code, stdout, _ = _run(["--from", str(note)], project)
    assert code == 0
    assert "## A" in stdout
    assert "## B" in stdout


def test_from_mode_reads_stdin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _setup_project(tmp_path)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("see [a](docs/glossary/a.md) and [[b]]\n"),
    )
    code, stdout, _ = _run(["--from", "-"], project)
    assert code == 0
    assert "## A" in stdout
    assert "## B" in stdout


def test_from_mode_no_arg_reads_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _setup_project(tmp_path)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("see [[b]]\n"),
    )
    code, stdout, _ = _run(["--from"], project)
    assert code == 0
    assert "## B" in stdout


def test_from_mode_broken_link_fails(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("[ghost](ghost.md)\n", encoding="utf-8")
    code, _, stderr = _run(["--from", str(note)], project)
    assert code == 1
    assert "ghost" in stderr


def test_from_mode_ignores_external_urls(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    note = tmp_path / "note.md"
    note.write_text(
        "see [home](https://example.com) and [a](docs/glossary/a.md)\n",
        encoding="utf-8",
    )
    code, stdout, _ = _run(["--from", str(note)], project)
    assert code == 0
    assert "## A" in stdout


def test_help_lists_bundled_terms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _setup_project(tmp_path)
    out = io.StringIO()
    err = io.StringIO()
    cwd = Path.cwd()
    try:
        os.chdir(project)
        with redirect_stdout(out), redirect_stderr(err), pytest.raises(SystemExit):
            main(["--help"])
    finally:
        os.chdir(cwd)
    help_text = out.getvalue()
    assert "terms (use with --explain):" in help_text
    assert "* basename-resolution" in help_text
    assert "* term" in help_text


def test_glossary_flag_overrides_discovery(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    other_glossary = tmp_path / "other_glossary"
    other_glossary.mkdir()
    (other_glossary / "z.md").write_text("## Z\n\nspecial\n", encoding="utf-8")
    code, stdout, _ = _run(["--glossary", str(other_glossary), "z"], project)
    assert code == 0
    assert "## Z" in stdout


def test_env_glossary_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _setup_project(tmp_path)
    other_glossary = tmp_path / "other_glossary"
    other_glossary.mkdir()
    (other_glossary / "z.md").write_text("## Z\n\nspecial\n", encoding="utf-8")
    monkeypatch.setenv("DISAMBIGUATE_GLOSSARY", str(other_glossary))
    code, stdout, _ = _run(["z"], project)
    assert code == 0
    assert "## Z" in stdout


def test_dogfood_lint_passes_against_project_glossary() -> None:
    """The bundled glossary lints clean against the project README."""
    project_root = Path(__file__).resolve().parents[2]
    code, _, stderr = _run(["--lint"], project_root)
    assert code == 0, f"dogfood lint failed: {stderr}"


def test_from_file_ignores_links_to_existing_non_glossary_docs(
    tmp_path: Path,
) -> None:
    """
    Kata for #45 at the CLI layer: `--from` passes the source path.

    Doc-to-doc links (README → CHANGELOG.md) must be classified as document
    links, not broken glossary references.
    """
    project = _setup_project(tmp_path)
    (project / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    readme = project / "README.md"
    readme.write_text(
        "[a](docs/glossary/a.md) and [changes](CHANGELOG.md)\n",
        encoding="utf-8",
    )
    code, out, err = _run(["--from", "README.md"], cwd=project)
    assert code == 0, err
    assert "## A" in out


def test_drift_reports_unlinked_term_and_fails(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    (tmp_path / "README.md").write_text(
        "[topological-order](docs/glossary/topological-order.md) [guide](guide.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "guide.md").write_text(
        "Sort in topological order.\n",
        encoding="utf-8",
    )
    code, _, stderr = _run(["--drift"], project)
    assert code == 1
    assert "unlinked-term" in stderr
    assert "guide.md:1" in stderr
    assert "topological-order" in stderr


def test_drift_clean_corpus_exits_zero(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    code, _, stderr = _run(["--drift"], project)
    assert code == 0
    assert stderr == ""


def test_drift_output_prints_suppression_hint_syntax(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    (tmp_path / "README.md").write_text(
        "[topological-order](docs/glossary/topological-order.md) [guide](guide.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "guide.md").write_text(
        "Sort in topological order.\n",
        encoding="utf-8",
    )
    code, _, stderr = _run(["--drift"], project)
    assert code == 1
    assert "<!-- d10e: ignore[unlinked-term] topological-order -->" in stderr


def _drifted_project(tmp_path: Path) -> Path:
    project = _setup_project(tmp_path)
    (tmp_path / "README.md").write_text(
        "[topological-order](docs/glossary/topological-order.md) [guide](guide.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "guide.md").write_text(
        "Sort in topological order.\n",
        encoding="utf-8",
    )
    return project


def test_write_baseline_then_clean_run(tmp_path: Path) -> None:
    project = _drifted_project(tmp_path)
    code, _, _ = _run(["--drift", "--write-baseline"], project)
    assert code == 0
    assert (tmp_path / ".drift-baseline.json").is_file()
    code, _, stderr = _run(["--drift"], project)
    assert code == 0
    assert "unlinked-term" not in stderr


def test_new_drift_not_in_baseline_fails(tmp_path: Path) -> None:
    project = _drifted_project(tmp_path)
    _run(["--drift", "--write-baseline"], project)
    (tmp_path / "README.md").write_text(
        "[topological-order](docs/glossary/topological-order.md) "
        "[guide](guide.md) [extra](extra.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "extra.md").write_text(
        "Sort in topological order.\n",
        encoding="utf-8",
    )
    code, _, stderr = _run(["--drift"], project)
    assert code == 1
    assert "extra.md" in stderr
    assert "guide.md" not in stderr


def test_baseline_auto_prunes_fixed_findings(tmp_path: Path) -> None:
    project = _drifted_project(tmp_path)
    _run(["--drift", "--write-baseline"], project)
    (tmp_path / "guide.md").write_text(
        "Sort in [topological order](docs/glossary/topological-order.md).\n",
        encoding="utf-8",
    )
    code, _, _ = _run(["--drift"], project)
    assert code == 0
    baseline_text = (tmp_path / ".drift-baseline.json").read_text(encoding="utf-8")
    assert "guide.md" not in baseline_text
