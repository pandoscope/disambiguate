"""
Development CLI for running Disambiguate from a source checkout.

This file is intentionally outside `src/` so built distributions only expose
the packaged argparse CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from disambiguate import __version__
from disambiguate.cli import (
    _normalize_requested_slugs,
    _resolve_lint_roots,
    _run_default,
    _run_drift,
    _run_from,
    _run_lint,
    _user_glossary_path,
)
from disambiguate.glossary import load_glossary
from disambiguate.renderer import build_explain_preamble, render_terms
from disambiguate.resolver import resolve

app = typer.Typer(add_completion=False)
ROOT = Path(__file__).resolve().parent
SOURCE_GLOSSARY = ROOT / "docs" / "glossary"


def _print_version(value: bool) -> None:
    """Print the package version and exit when `--version` is passed."""
    if value:
        typer.echo(f"disambiguate {__version__}")
        raise typer.Exit()


@app.command()
def main(
    slugs: Annotated[
        list[str] | None,
        typer.Argument(
            help="Canonical names or slugs to render. Empty = render whole glossary."
        ),
    ] = None,
    glossary: Annotated[
        Path | None,
        typer.Option(
            "--glossary",
            help="Override glossary directory for normal and --from modes.",
        ),
    ] = None,
    from_doc: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Extract glossary-shaped links from DOC. Use '-' to read stdin.",
        ),
    ] = None,
    explain: Annotated[
        bool,
        typer.Option(
            "--explain",
            help="Render the source checkout's docs/glossary specification.",
        ),
    ] = False,
    lint: Annotated[
        bool,
        typer.Option("--lint", help="Validate the active glossary."),
    ] = False,
    drift: Annotated[
        bool,
        typer.Option("--drift", help="Detect prose drifting from the glossary."),
    ] = False,
    write_baseline: Annotated[
        bool,
        typer.Option(
            "--write-baseline",
            help="With --drift: regenerate the drift-baseline file.",
        ),
    ] = False,
    roots: Annotated[
        list[str] | None,
        typer.Option("--roots", help="Lint roots: paths and globs measured from."),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Run Disambiguate in a source checkout with Typer-friendly debugging."""
    active_slugs = slugs or []
    selected_modes = sum(
        mode_is_selected
        for mode_is_selected in (from_doc is not None, explain, lint, drift)
    )
    if selected_modes > 1:
        raise typer.BadParameter(
            "Use only one of --from, --explain, --lint, or --drift."
        )
    if write_baseline and not drift:
        raise typer.BadParameter("--write-baseline requires --drift.")

    if explain:
        glossary_obj = load_glossary(SOURCE_GLOSSARY)
        normalized_slugs = _normalize_requested_slugs(active_slugs)
        terms = resolve(glossary_obj, normalized_slugs)
        preamble = build_explain_preamble(normalized_slugs)
        typer.echo(render_terms(terms, preamble=preamble), nl=False)
        return

    glossary_arg = str(glossary) if glossary else None
    glossary_obj = load_glossary(_user_glossary_path(glossary_arg))
    if lint:
        raise typer.Exit(_run_lint(glossary_obj, _resolve_lint_roots(roots)))
    if drift:
        raise typer.Exit(
            _run_drift(glossary_obj, _resolve_lint_roots(roots), write_baseline)
        )
    if from_doc is not None:
        raise typer.Exit(_run_from(glossary_obj, from_doc))
    raise typer.Exit(_run_default(glossary_obj, active_slugs))


def _normalize_from_option(argv: list[str]) -> list[str]:
    """Translate bare `--from` into `--from -` for argparse parity."""
    normalized = list(argv)
    for index, value in enumerate(normalized):
        next_is_value = index + 1 < len(normalized) and not normalized[
            index + 1
        ].startswith("-")
        if value == "--from" and not next_is_value:
            normalized.insert(index + 1, "-")
            break
    return normalized


if __name__ == "__main__":
    sys.argv[1:] = _normalize_from_option(sys.argv[1:])
    app()
