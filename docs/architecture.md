# Architecture

A terse map of [Disambiguate](glossary/disambiguate.md). Read this before
touching code.

## Module layout

```text
src/disambiguate/
├── __init__.py
├── __main__.py              # python -m disambiguate
├── cli.py                   # argparse, command dispatch
├── logging_config.py        # stdlib logging setup
├── discovery.py             # find glossary, repo root, lint roots
├── parser.py                # parse one .md → (slug, name, body, links)
├── glossary.py              # load dir → {slug: Term}, build dep graph
├── resolver.py              # resolve(slugs) → ordered list of Terms
├── renderer.py              # ordered Terms → markdown stdout
├── from_mode.py             # extract glossary-shaped links from a doc
├── lint.py                  # all lint checks including reachability
├── mentions.py              # find term-mentions in prose (masked matching)
├── suppressions.py          # ignore-hints, config ignores, stale detection
├── baseline.py              # checked-in drift-baseline (grandfathering)
└── drift.py                 # drift-check engine behind --drift
```

The runtime imports nothing outside the standard library. `argparse`,
`graphlib`, `pathlib`, `re`, `glob`, `shlex`, `importlib.resources`,
`logging`. Dev-only tools — `pytest`, `python-semantic-release`, `build`,
`mypy`, `ruff` — live under `[dependency-groups].dev`.

## Pipeline

The core pipeline for a default invocation:

1. **Discover** the [glossary](glossary/glossary.md) — see [discovery.py](../src/disambiguate/discovery.py).
2. **Parse** each `.md` file into a `ParsedTerm` — see [parser.py](../src/disambiguate/parser.py).
3. **Load** the directory into a `Glossary` with the
   [dependency](glossary/dependency.md) graph — see [glossary.py](../src/disambiguate/glossary.py).
4. **Resolve** the closure of requested
   [slugs](glossary/slug.md) into [topological order](glossary/topological-order.md)
   — see [resolver.py](../src/disambiguate/resolver.py).
5. **Render** the ordered [terms](glossary/term.md) to stdout — see
   [renderer.py](../src/disambiguate/renderer.py).

## Per-command data flow

### Default: `disambiguate [SLUG ...]`

Discover → load → normalize direct CLI slug arguments → resolve(slugs) →
render. Empty slugs means "the entire glossary", served by the same
[resolver](glossary/resolver.md). Each requested slug must exist after
normalization; the resolver raises on unknown ones.

### `--from <doc>`

Discover → load → extract slugs from `doc` → resolve → render. Extraction
is in [from_mode.py](../src/disambiguate/from_mode.py); see
[from-mode](glossary/from-mode.md). A path of `-` (or no path) reads
stdin. Glossary-shaped links with broken slugs raise; non-glossary links
(URLs, image paths, non-`.md`) are silently ignored.

### `--explain [SLUG ...]`

Always renders Disambiguate's own bundled glossary, regardless of what
[glossary-format](glossary/glossary-format.md)-compatible glossary the user
might be in. Loads `disambiguate/_glossary/` via `importlib.resources`,
normalizes direct CLI slug arguments, prepends the agent-targeted preamble,
and runs the same resolver pipeline.

This is important and easy to get wrong: a downstream project running
`disambiguate --explain github-format` from a directory that has its own
`docs/glossary/` must still get Disambiguate's bundled spec, not whatever
the local glossary looks like.

### `--lint`

Discover → load → run the six checks in
[lint.py](../src/disambiguate/lint.py). See [lint](glossary/lint.md) for
the catalogue. Findings go to stderr; exit code 1 if any. Lint
findings are diagnostics, not the tool's primary output, so they are kept
separate from `print()`-to-stdout rendering.

### `--drift`

Discover → load → walk the corpus reachable from the lint roots → run the
[drift](glossary/drift.md) checks in
[drift.py](../src/disambiguate/drift.py) over every visited document.
[Term-mention](glossary/term-mention.md) matching lives in
[mentions.py](../src/disambiguate/mentions.py). Findings can be silenced
by [ignore-hints](glossary/ignore-hint.md) at config, file, or inline
scope — parsing, precedence, and stale-suppression detection live in
[suppressions.py](../src/disambiguate/suppressions.py). Findings go to
stderr with their [rule-code](glossary/rule-code.md); exit code 1 if any.
Findings recorded in the checked-in
[drift-baseline](glossary/drift-baseline.md)
([baseline.py](../src/disambiguate/baseline.py)) are non-fatal and
auto-pruned once fixed; `--drift --write-baseline` regenerates the file.
Drift-checks are deliberately separate from `--lint`: lint validates the
glossary, drift validates the prose that uses it.

## Glossary auto-discovery

[discovery.py](../src/disambiguate/discovery.py) walks up from cwd looking
for `docs/glossary/` or `glossary/`, in that order. Precedence:

1. `--glossary <dir>` flag.
2. `DISAMBIGUATE_GLOSSARY` env var.
3. Auto-discovery via cwd walk-up.

There is no fallback to the bundled glossary for normal commands —
`--explain` is the only path that touches the bundle.

## Link resolution

A [cross-reference](glossary/cross-reference.md) inside a glossary file
resolves by [basename](glossary/basename-resolution.md), regardless of
directory components or whether the link uses standard markdown
(`[t](path/to/foo.md)`) or wiki-style (`[[foo]]`).

Wiki-style links may carry display text (`[[foo|shown text]]`) and either
syntax may carry a `#fragment` (`[[foo#heading]]`, `[t](foo.md#section)`);
the display text and fragment are stripped, only the slug resolves.
Malformed pipe forms resolve leniently on the first segment
(Obsidian semantics), but [lint](glossary/lint.md) reports them as fatal
in glossary term files.

The parser ignores links inside fenced code blocks (```` ``` ```` or `~~~`)
and inline code spans (single backticks). URLs (anything containing `://`)
are also ignored. Non-`.md` links and image references are not parsed at all.

## Bundled glossary

`disambiguate/_glossary/` ships inside the wheel. It is generated at build
time by [hatch_build.py](../hatch_build.py) by copying
[docs/glossary/](glossary/) into Hatch's build directory and force-including
the staged files into the artifact. The `_terms.py` file — holding the
alphabetical slug list used by `--help`'s epilog — is generated in the same
staged package data. The source tree is not mutated by builds; the source of
truth is `docs/glossary/`.

`--explain` reads the bundle via `importlib.resources`, which means it
works whether the package is unzipped on disk, in a wheel, or in an
editable install. The packaged CLI assumes generated bundle data is present;
source-checkout debugging uses the root-level `dev_cli.py`, which reads
`docs/glossary/` dynamically and is excluded from distributions.

## Lint reachability model

The lint walks one directed graph over markdown files (
[github-format](glossary/github-format.md) terms and external docs both,
likewise [obsidian-format](glossary/obsidian-format.md)). Edges are
`[t](path.md)` and `[[slug]]` links wherever they appear. Walks start from
the configured roots; everything reachable is fine. A term whose path is
not in the visited set is an orphan.

Roots, precedence:

1. `--roots <paths-and-globs>` flag.
2. `DISAMBIGUATE_ROOTS` env var (space-separated).
3. `<repo-root>/README.md`, where repo root is the directory containing
   `.git/`.

Globs are expanded by Disambiguate itself via `glob.glob`, so the env var
form works regardless of shell expansion. Paths that do not resolve to any
existing file are an error — there is no silent fallback.

The walk uses a visited-set, not a topological sort, so cycles in external
documents are tolerated. External-doc-to-external-doc edges are followed
because that is how the architecture doc reaches every term: README → here
→ each glossary file.

## Logging strategy

`logger = logging.getLogger(__name__)` in every module; configured once in
[cli.py](../src/disambiguate/cli.py) via
[logging_config.py](../src/disambiguate/logging_config.py).

- Default: `WARNING` to stderr.
- `-v`: `INFO`.
- `-vv`: `DEBUG`.

The split between logger output and tool output is firm: rendered markdown
and lint findings go through `print()` (stdout for output, stderr for lint
diagnostics). Logger output ("loaded N terms", "walking from root X",
"skipping non-md link") never composes with the tool's primary output.

## Errors and exit codes

- `0` — success.
- `1` — runtime failure (broken term, lint failure, broken `--from` link).
- `2` — usage error (argparse default).

CLI-level exceptions are caught at the dispatch boundary in
[cli.py](../src/disambiguate/cli.py) and converted to exit code 1 with the
exception text logged via `logger.error()`. With `-vv` the boundary
re-raises so the traceback is visible.
