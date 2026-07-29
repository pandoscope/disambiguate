"""
Command-line entry point.

Argparse-driven dispatch with five operating modes:

- default: render selected slugs (or whole glossary) using the user's glossary
- `--from <doc>`: extract slugs from a document, then render
- `--explain`: render Disambiguate's own bundled glossary, with preamble
- `--lint`: validate the user's glossary
- `--drift`: detect prose drifting from the glossary

Plus one verb, dispatched before the parser: `prune`, which removes
terms nothing links.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, bundled
from .baseline import (
    BASELINE_FILENAME,
    apply_baseline,
    load_baseline,
    prune_baseline,
    save_baseline,
)
from .discovery import (
    GlossaryNotFoundError,
    RepoRootNotFoundError,
    RootFileMissingError,
    expand_root_specs,
    find_glossary,
    find_repo_root,
    resolve_default_root,
)
from .drift import run_drift_checks
from .from_mode import BrokenFromLinkError, extract_slugs
from .glossary import DuplicateSlugError, Glossary, load_glossary
from .lint import lint_glossary
from .logging_config import DEBUG_LEVEL, configure_logging
from .prune import apply_prune, format_dry_run, plan_prune
from .renderer import build_explain_preamble, render_terms
from .resolver import CycleError, UnknownSlugError, resolve
from .suppressions import load_drift_config

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2

# Dispatched before the main parser, which takes free-form slugs.
PRUNE_VERB = "prune"

# Canonical slug alphabet: lowercase ASCII letters, digits, and hyphen.
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9-]")
_DASH_RUN = re.compile(r"-+")


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser, including the bundled-term epilog list."""
    epilog_lines = ["terms (use with --explain):"] + [
        f"  * {t}" for t in bundled.bundled_term_slugs()
    ]
    parser = argparse.ArgumentParser(
        prog="disambiguate",
        description=(
            "Resolve markdown glossary terms and their transitive "
            "dependencies in topological order."
        ),
        epilog="\n".join(epilog_lines),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "slugs",
        nargs="*",
        help="Canonical names or slugs to render. Empty = render whole glossary.",
    )
    parser.add_argument(
        "--glossary",
        metavar="DIR",
        help=(
            "Override glossary directory (default: auto-discover "
            "`docs/glossary/` or `glossary/` walking up from cwd; "
            "env var DISAMBIGUATE_GLOSSARY)."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--from",
        dest="from_doc",
        metavar="DOC",
        help=(
            "Extract glossary-shaped links from DOC and resolve them. "
            "Use `-` or omit to read stdin."
        ),
        nargs="?",
        const="-",
    )
    mode.add_argument(
        "--explain",
        dest="explain",
        action="store_true",
        help=(
            "Render Disambiguate's format spec for one or more TERMs. "
            "With no TERM, render the entire bundled glossary. "
            "Available terms are listed below."
        ),
    )
    mode.add_argument(
        "--lint",
        dest="lint",
        action="store_true",
        help="Validate the glossary against six fatal checks.",
    )
    mode.add_argument(
        "--drift",
        dest="drift",
        action="store_true",
        help=(
            "Detect prose drifting from the glossary (fatal drift-checks "
            "over the corpus reachable from the lint roots)."
        ),
    )
    parser.add_argument(
        "--write-baseline",
        dest="write_baseline",
        action="store_true",
        help=(
            "With --drift: write the drift-baseline file grandfathering "
            "every current finding, instead of failing on them."
        ),
    )
    parser.add_argument(
        "--roots",
        metavar="PATH",
        nargs="+",
        help=(
            "Lint roots: paths and globs reachability is measured from. "
            "Default: <repo-root>/README.md. "
            "Env var DISAMBIGUATE_ROOTS (space-separated)."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (-v=INFO, -vv=DEBUG).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"disambiguate {__version__}",
    )
    return parser


def _build_prune_parser() -> argparse.ArgumentParser:
    """
    Build the parser for the `prune` verb.

    A separate parser rather than a subparser: the main parser takes
    free-form `slugs` positionally, and argparse cannot offer an
    optional subcommand alongside that without making `prune` ambiguous
    with a term of the same name.
    """
    parser = argparse.ArgumentParser(
        prog="disambiguate prune",
        description=(
            "Remove glossary terms nothing links. A term consents by "
            "carrying a `<!-- d10e: auto-prune -->` annotation."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed and exit without deleting anything.",
    )
    parser.add_argument(
        "--all-orphans",
        action="store_true",
        help="Also remove orphaned terms that never declared consent.",
    )
    parser.add_argument(
        "--glossary",
        metavar="DIR",
        help="Override glossary directory (default: auto-discover).",
    )
    parser.add_argument(
        "--roots",
        metavar="PATH",
        nargs="+",
        help="Roots reachability is measured from. Default: <repo-root>/README.md.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (-v=INFO, -vv=DEBUG).",
    )
    return parser


def _run_prune(argv: list[str]) -> int:
    """Plan and, unless `--dry-run`, carry out a prune."""
    args = _build_prune_parser().parse_args(argv)
    configure_logging(args.verbose)

    glossary = load_glossary(_user_glossary_path(args.glossary))
    roots = _resolve_lint_roots(args.roots)
    plan = plan_prune(glossary, roots, all_orphans=args.all_orphans)

    if args.dry_run:
        print(format_dry_run(plan))
        return EXIT_OK

    removed = apply_prune(plan, glossary)
    if not removed:
        print("Nothing to prune: no orphaned term consents to removal.")
        return EXIT_OK

    print(f"Pruned {len(removed)} orphaned term(s):")
    for slug in plan.remove:
        print(f"  - {slug}")
    return EXIT_OK


def _user_glossary_path(arg_value: str | None) -> Path:
    """
    Resolve the active user-glossary directory.

    Precedence: `--glossary` flag > `DISAMBIGUATE_GLOSSARY` env > auto-discovery.
    """
    if arg_value is not None:
        return Path(arg_value).resolve()
    env_value = os.environ.get("DISAMBIGUATE_GLOSSARY")
    if env_value:
        return Path(env_value).resolve()
    return find_glossary(start=Path.cwd())


def _resolve_lint_roots(arg_roots: list[str] | None) -> list[Path]:
    """
    Resolve the lint roots from flag, env, or default.

    Precedence: `--roots` flag > `DISAMBIGUATE_ROOTS` env (space-separated)
    > `<repo-root>/README.md`.
    """
    if arg_roots is not None:
        return expand_root_specs(arg_roots)
    env_value = os.environ.get("DISAMBIGUATE_ROOTS")
    if env_value:
        # Space-separated. Documented constraint: paths cannot contain
        # spaces. We expand globs ourselves so the env var can carry
        # patterns regardless of shell expansion.
        return expand_root_specs(shlex.split(env_value))
    return resolve_default_root(start=Path.cwd())


def _read_from_doc(path_arg: str) -> str:
    """Read the source document for `--from`. `-` means stdin."""
    if path_arg == "-":
        return sys.stdin.read()
    return Path(path_arg).read_text(encoding="utf-8")


def _normalize_requested_slug(slug: str) -> str:
    """
    Normalize one direct CLI slug argument.

    slug: raw positional CLI argument.

    Returns
    -------
    A lowercase slug where every character outside `a-z`, `0-9`, and `-`
    is replaced with `-`, and consecutive dashes are collapsed.

    """
    normalized = _NON_SLUG_CHARS.sub("-", slug.lower())
    return _DASH_RUN.sub("-", normalized)


def _normalize_requested_slugs(slugs: list[str]) -> list[str]:
    """
    Normalize direct CLI slug arguments before resolver lookup.

    slugs: raw positional CLI arguments.

    Returns
    -------
    Slugs suitable for lookup. Phrase arguments like "topological order" and
    punctuation-heavy arguments like "topological___order" become
    "topological-order".

    """
    # DECISION:IFACE — Direct CLI requests now accept phrase-shaped terms by
    # normalizing every character outside the canonical slug alphabet.
    return [_normalize_requested_slug(slug) for slug in slugs]


def _run_lint(glossary: Glossary, roots: list[Path]) -> int:
    """Run lint and report findings to stderr; return exit code."""
    findings = lint_glossary(glossary, roots=roots)
    if not findings:
        return EXIT_OK
    for finding in findings:
        # Lint findings go to stderr — they are diagnostics for the user,
        # not the tool's primary output, and stderr keeps stdout clean for
        # composing with pipes.
        print(f"{finding.kind}: {finding.message}", file=sys.stderr)
    return EXIT_FAILURE


def _baseline_location(config_root: Path | None) -> Path:
    """
    Resolve where the drift-baseline file lives.

    config_root: directory of the active pyproject.toml, or None.

    Returns
    -------
    `<config_root>/.drift-baseline.json` when a config was found, else the
    repo root's, else the cwd's.

    """
    if config_root is not None:
        return config_root / BASELINE_FILENAME
    try:
        return find_repo_root(Path.cwd()) / BASELINE_FILENAME
    except RepoRootNotFoundError:
        return Path.cwd() / BASELINE_FILENAME


def _run_drift(glossary: Glossary, roots: list[Path], write_baseline: bool) -> int:
    """
    Run the drift-checks and report findings to stderr; return exit code.

    glossary: loaded glossary.
    roots: corpus roots.
    write_baseline: True regenerates the drift-baseline from the current
        findings and exits 0 instead of failing on them.

    Returns
    -------
    EXIT_OK when no fresh finding remains (baselined findings are
    non-fatal; stale baseline entries are auto-pruned), else EXIT_FAILURE.

    """
    config = load_drift_config(Path.cwd())
    findings = run_drift_checks(glossary, roots=roots, config=config)
    baseline_path = _baseline_location(config.root if config else None)

    if write_baseline:
        save_baseline(baseline_path, findings)
        print(
            f"wrote {baseline_path} grandfathering {len(findings)} finding(s)",
            file=sys.stderr,
        )
        return EXIT_OK

    baseline = load_baseline(baseline_path)
    if baseline is not None:
        findings, stale_keys = apply_baseline(findings, baseline)
        if stale_keys:
            # Fixed findings must not leave permanently stale baseline
            # entries; the baseline only ever shrinks on a normal run.
            prune_baseline(baseline, stale_keys)
            print(
                f"pruned {len(stale_keys)} fixed finding(s) from {baseline.path}",
                file=sys.stderr,
            )

    if not findings:
        return EXIT_OK
    for finding in findings:
        # Like lint findings, drift findings are diagnostics: stderr keeps
        # stdout clean for composing with pipes.
        print(
            f"{finding.path}:{finding.line}: {finding.rule_code}: {finding.message}",
            file=sys.stderr,
        )
    return EXIT_FAILURE


def _run_default(glossary: Glossary, slugs: list[str]) -> int:
    """Resolve the requested slugs and print to stdout."""
    terms = resolve(glossary, _normalize_requested_slugs(slugs))
    print(render_terms(terms), end="")
    return EXIT_OK


def _run_from(glossary: Glossary, from_doc: str) -> int:
    """Extract slugs from a document and resolve them."""
    text = _read_from_doc(from_doc)
    # A real file gets resolve-then-classify for its document links;
    # stdin (`-`) has no base path, so classification stays basename-only.
    source_path = None if from_doc == "-" else Path(from_doc)
    slugs = extract_slugs(text, glossary, source_path=source_path)
    terms = resolve(glossary, slugs)
    print(render_terms(terms), end="")
    return EXIT_OK


def _run_explain(slugs: list[str]) -> int:
    """Render the bundled glossary with the agent-targeted preamble."""
    glossary = bundled.load_bundled_glossary()
    # `--explain` ignores --glossary and DISAMBIGUATE_GLOSSARY by design:
    # the user wants Disambiguate's own spec, not whatever local glossary
    # might be in scope.
    normalized_slugs = _normalize_requested_slugs(slugs)
    terms = resolve(glossary, normalized_slugs)
    preamble = build_explain_preamble(normalized_slugs)
    print(render_terms(terms, preamble=preamble), end="")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """
    CLI entry point.

    argv: argument list (excluding program name). Defaults to `sys.argv[1:]`.

    Returns
    -------
    Exit code: 0 success, 1 failure (broken term, lint error, etc.), 2 usage
    error. Exceptions are caught at the boundary and converted to exit 1;
    tracebacks only surface with `-vv`.

    """
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv and raw_argv[0] == PRUNE_VERB:
        try:
            return _run_prune(raw_argv[1:])
        except (
            DuplicateSlugError,
            GlossaryNotFoundError,
            RepoRootNotFoundError,
            RootFileMissingError,
            FileNotFoundError,
        ) as e:
            logger.error("%s", e)
            return EXIT_FAILURE

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.write_baseline and not args.drift:
        parser.error("--write-baseline requires --drift")
    effective_level = configure_logging(args.verbose)

    try:
        if args.explain:
            return _run_explain(list(args.slugs))

        if args.lint:
            glossary = load_glossary(_user_glossary_path(args.glossary))
            roots = _resolve_lint_roots(args.roots)
            return _run_lint(glossary, roots)

        if args.drift:
            glossary = load_glossary(_user_glossary_path(args.glossary))
            roots = _resolve_lint_roots(args.roots)
            return _run_drift(glossary, roots, args.write_baseline)

        if args.from_doc is not None:
            glossary = load_glossary(_user_glossary_path(args.glossary))
            return _run_from(glossary, args.from_doc)

        glossary = load_glossary(_user_glossary_path(args.glossary))
        return _run_default(glossary, list(args.slugs))
    except (
        UnknownSlugError,
        CycleError,
        BrokenFromLinkError,
        DuplicateSlugError,
        GlossaryNotFoundError,
        RepoRootNotFoundError,
        RootFileMissingError,
        FileNotFoundError,
    ) as e:
        # Tracebacks would be noise here. With -vv we re-raise to let the
        # debugger / shell see the full traceback.
        if effective_level <= DEBUG_LEVEL:
            raise
        logger.error("%s", e)
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
