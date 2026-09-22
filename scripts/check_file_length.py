#!/usr/bin/env python3
"""
Cap what a source file costs to read, over the files a commit touches.

Tickets #239 and #242.

The cap is an estimated token count — file bytes / 4, rounded up —
because tokens are what an agent pays for a Read: comments and blank
lines count, and the language's density stops mattering. Complexity is
measured independently (ruff carries it for Python); for bash, which
ruff cannot read, this hook also counts code lines — non-blank,
non-comment — because a long bash script is a rewrite-in-Python signal
and a total measure would punish exactly the comments that make bash
safer.

A file over a cap fails, naming the path and the measure, unless the
repo's own `.file-length-allowlist` names it — each entry carrying the
ticket that will bring the file back under, so the list shrinks rather
than becoming permanent. Three things make an entry leave the list, all
checked here: a ticket is missing, the file came back under every cap
that applies to it, or the file is gone.

Stdlib only, and no repo state beyond the paths it is handed: prek runs
this on every commit, on whatever `python3` the contributor has.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ALLOWLIST = ".file-length-allowlist"
DEFAULT_MAX_TOKENS = 10000
DEFAULT_SH_CODE_LINES = 150
DEFAULT_CODE_LINES = 500
SH_SUFFIXES = (".sh", ".bash")
CODE_SUFFIXES = (".py", ".mjs", ".cjs", ".js", ".jsx", ".ts", ".tsx")
# Line-based comment heuristics — all a hard limit needs. Python's is
# exact; the js family's misses code after a same-line block comment,
# which only ever under-counts.
COMMENT_MARKS = {".py": ("#",)}
for _suffix in (".mjs", ".cjs", ".js", ".jsx", ".ts", ".tsx"):
    COMMENT_MARKS[_suffix] = ("//", "/*", "*", "*/")

# `#123` or `owner/repo#123`, the same reference shape the ticket gate
# reads on a pull request body.
TICKET = re.compile(r"(?:[\w.-]+/[\w.-]+)?#\d+")


def parse_allowlist(text: str) -> tuple[dict[str, str], list[str]]:
    """
    Return `{path: ticket}` from the allowlist, and a problem per bad entry.

    One entry per line: the path, then the ticket that will close it,
    after a `#`. A line carrying no ticket buys a permanent exemption,
    which is the one thing the list must not be able to hold, so it is
    reported rather than parsed.
    """
    entries: dict[str, str] = {}
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        path, _, comment = stripped.partition("#")
        path = path.strip()
        ticket = TICKET.search(f"#{comment}")
        if not path or not ticket:
            problems.append(
                f"{ALLOWLIST}:{number}: {stripped!r} names no ticket — an entry "
                "reads `<path>  # owner/repo#123`, so the exemption ends when "
                "the ticket does"
            )
            continue
        entries[path] = ticket.group(0)
    return entries, problems


def measure(path: str) -> tuple[int, int | None, str | None] | None:
    """
    Return (estimated tokens, code lines, kind), or None for a non-text file.

    Tokens are bytes / 4 rounded up: dependency-free, monotone, close
    enough for a hard cap, and charged to every file a model reads —
    prose and config cost a Read what source costs. Code lines (neither
    blank nor comment) are counted for code files only: kind "sh" gets
    the bash limit, kind "code" the general one, None only the cap.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        text = data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    tokens = (len(data) + 3) // 4
    plain = path[: -len(".jinja")] if path.endswith(".jinja") else path
    suffix = "." + plain.rsplit(".", 1)[-1] if "." in plain else ""
    kind = (
        "sh" if suffix in SH_SUFFIXES else "code" if suffix in CODE_SUFFIXES else None
    )
    if kind is None:
        return tokens, None, None
    marks = COMMENT_MARKS.get(suffix, ("#",))
    code = sum(
        1
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith(marks)
    )
    return tokens, code, kind


def review(
    measures: dict[str, tuple[int, int | None, str | None]],
    token_limit: int,
    sh_limit: int,
    code_limit: int,
    allowlist: dict[str, str],
    missing: set[str],
) -> list[str]:
    """
    Return every problem this run found, as lines a reader can act on.

    `measures` holds only the files this run was handed, which is why an
    untouched overrun elsewhere is nobody's commit to block: the hook
    judges what the commit touched. `missing` names allowlisted paths
    that are no longer on disk.
    """
    problems = []
    for path in sorted(measures):
        if path in allowlist:
            continue
        tokens, code, kind = measures[path]
        if tokens > token_limit:
            problems.append(
                f"{path}: ~{tokens} tokens (bytes/4), over the {token_limit}-token "
                f"cap — split it, or add `{path}  # <ticket>` to {ALLOWLIST}"
            )
        if kind == "sh" and code is not None and code > sh_limit:
            problems.append(
                f"{path}: {code} code lines, over the {sh_limit}-line bash limit — "
                f"rewrite it in Python or split out a sourced library, or add "
                f"`{path}  # <ticket>` to {ALLOWLIST}"
            )
        elif kind == "code" and code is not None and code > code_limit:
            problems.append(
                f"{path}: {code} code lines, over the {code_limit}-line limit — "
                f"split it, or add `{path}  # <ticket>` to {ALLOWLIST}"
            )
    for path, ticket in sorted(allowlist.items()):
        if path in missing:
            problems.append(
                f"{ALLOWLIST}: {path} no longer exists — remove its line "
                f"(ticket {ticket})"
            )
        elif path in measures:
            tokens, code, kind = measures[path]
            limit = sh_limit if kind == "sh" else code_limit
            over = tokens > token_limit or (code is not None and code > limit)
            if not over:
                problems.append(
                    f"{ALLOWLIST}: {path} is back under every cap that applies "
                    f"to it — remove its line (ticket {ticket})"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    """Measure the paths given, judge them against the caps, exit 1 on a problem."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-tokens",
        dest="token_limit",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"estimated tokens a file may cost (default {DEFAULT_MAX_TOKENS})",
    )
    parser.add_argument(
        "--max-sh-code-lines",
        dest="sh_limit",
        type=int,
        default=DEFAULT_SH_CODE_LINES,
        help=(
            "non-blank non-comment lines a bash file may have "
            f"(default {DEFAULT_SH_CODE_LINES})"
        ),
    )
    parser.add_argument(
        "--max-code-lines",
        dest="code_limit",
        type=int,
        default=DEFAULT_CODE_LINES,
        help=(
            "non-blank non-comment lines a code file may have "
            f"(default {DEFAULT_CODE_LINES})"
        ),
    )
    parser.add_argument(
        "--allowlist",
        default=ALLOWLIST,
        help=f"the repo's exemption list (default {ALLOWLIST})",
    )
    parser.add_argument("paths", nargs="*", help="the files prek hands this hook")
    args = parser.parse_args(argv)

    allowlist: dict[str, str] = {}
    problems: list[str] = []
    if os.path.exists(args.allowlist):
        with open(args.allowlist, encoding="utf-8") as handle:
            allowlist, problems = parse_allowlist(handle.read())

    measures = {}
    for path in args.paths:
        measured = measure(path)
        if measured is not None:
            measures[path] = measured
    missing = {path for path in allowlist if not os.path.exists(path)}

    problems += review(
        measures, args.token_limit, args.sh_limit, args.code_limit, allowlist, missing
    )
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
