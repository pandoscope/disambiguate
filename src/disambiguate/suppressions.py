"""
Suppression surfaces for drift-checks.

Three ways to silence a drift finding, coarsest first:

- config-level ignore: a rule-code disabled repo-wide (optionally per
  path) under `[tool.disambiguate]`.
- file-level opt-out: an ignore-hint disabling a rule-code for the whole
  document, e.g. `<!-- d10e: ignore-file[unlinked-term] -->`.
- inline ignore-hint: an HTML comment on the finding's line or the line
  directly above, e.g. `<!-- d10e: ignore[unlinked-term] widget -->`.

Hints live inside HTML comments so they are invisible in rendered
markdown. The hint keyword is `d10e` (numeronym of `disambiguate`);
`disambiguate` is accepted as a long-form alias.

DECISION:IFACE — config schema is `drift-ignore` (list of rule-codes) and
`drift-ignore-paths` (glob -> rule-codes) under `[tool.disambiguate]`;
inline hints cover their own line and the one below; the stale finding's
rule-code is `stale-suppression`. None of these names were pinned by the
ticket.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from .parser import _FENCED_CODE_RE, _INLINE_CODE_RE

# One regex per hint form. The keyword is `d10e` or `disambiguate`; the
# rule-code is bracketed; an inline hint may carry a target term after the
# brackets.
_INLINE_HINT_RE = re.compile(
    r"<!--\s*(?:d10e|disambiguate):\s*ignore\[(?P<rule>[a-z0-9-]+)\]"
    r"(?:\s+(?P<target>[^>\s]+))?\s*-->"
)

_FILE_HINT_RE = re.compile(
    r"<!--\s*(?:d10e|disambiguate):\s*ignore-file\[(?P<rule>[a-z0-9-]+)\]\s*-->"
)


@dataclass(frozen=True)
class InlineHint:
    """
    One inline ignore-hint parsed from a document.

    line: 1-based line the hint sits on. The hint suppresses findings on
        this line and the line directly below (hint-above placement).
    rule_code: the rule-code the hint silences.
    target: term slug the hint is scoped to, or None for any term.
    """

    line: int
    rule_code: str
    target: str | None


def parse_inline_hints(text: str) -> list[InlineHint]:
    """
    Parse every inline ignore-hint in `text`, in document order.

    text: full markdown source of a document.

    Returns
    -------
    A list of InlineHint objects; empty list when the document carries no
    hints.

    """
    code_spans = _code_spans(text)
    hints: list[InlineHint] = []
    for match in _INLINE_HINT_RE.finditer(text):
        if _in_spans(match.start(), match.end(), code_spans):
            continue
        line = 1 + text.count("\n", 0, match.start())
        hints.append(
            InlineHint(
                line=line,
                rule_code=match.group("rule"),
                target=match.group("target"),
            )
        )
    return hints


def _code_spans(text: str) -> list[tuple[int, int]]:
    """Return spans of fenced code blocks and inline code spans in `text`."""
    spans: list[tuple[int, int]] = []
    for pattern in (_FENCED_CODE_RE, _INLINE_CODE_RE):
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end()))
    return spans


def _in_spans(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """Return True when [start, end) intersects any span."""
    return any(start < span_end and end > span_start for span_start, span_end in spans)


@dataclass(frozen=True)
class DriftConfig:
    """
    Config-level suppression settings from `[tool.disambiguate]`.

    ignore: rule-codes disabled repo-wide.
    ignore_paths: path glob (relative to `root`) -> rule-codes disabled
        under that glob.
    root: directory the globs are relative to (the pyproject.toml's
        directory); None when the config was built without one.
    """

    ignore: list[str] = field(default_factory=list)
    ignore_paths: dict[str, list[str]] = field(default_factory=dict)
    root: Path | None = None

    def covers(self, rule_code: str, path: Path) -> bool:
        """Return True when this config silences `rule_code` for `path`."""
        if rule_code in self.ignore:
            return True
        for pattern, rules in self.ignore_paths.items():
            if rule_code not in rules:
                continue
            if glob_covers(pattern, path, self.root):
                return True
        return False


def glob_covers(pattern: str, path: Path, root: Path | None) -> bool:
    """Match `path` against a config glob relative to `root` (or absolute)."""
    if root is not None:
        try:
            relative = path.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return fnmatch(relative.as_posix(), pattern)
    return fnmatch(path.as_posix(), pattern)


def load_drift_config(start: Path) -> DriftConfig | None:
    """
    Load `[tool.disambiguate]` from the nearest pyproject.toml.

    start: directory to walk up from.

    Returns
    -------
    A DriftConfig when a pyproject.toml with a `[tool.disambiguate]`
    section is found; None when no pyproject.toml exists on the walk-up
    path or the section is absent.

    """
    for directory in [start.resolve(), *start.resolve().parents]:
        pyproject = directory / "pyproject.toml"
        if not pyproject.is_file():
            continue
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
        section = data.get("tool", {}).get("disambiguate")
        if section is None:
            return None
        return DriftConfig(
            ignore=list(section.get("drift-ignore", [])),
            ignore_paths={
                pattern: list(rules)
                for pattern, rules in section.get("drift-ignore-paths", {}).items()
            },
            root=directory,
        )
    return None


@dataclass(frozen=True)
class FileHint:
    """
    One file-level opt-out parsed from a document.

    line: 1-based line the hint sits on (used only for reporting).
    rule_code: the rule-code disabled for the whole document.
    """

    line: int
    rule_code: str


def parse_file_hints(text: str) -> list[FileHint]:
    """
    Parse every file-level ignore-file hint in `text`, in document order.

    text: full markdown source of a document.

    Returns
    -------
    A list of FileHint objects; empty list when the document carries no
    file-level opt-outs.

    """
    code_spans = _code_spans(text)
    hints: list[FileHint] = []
    for match in _FILE_HINT_RE.finditer(text):
        if _in_spans(match.start(), match.end(), code_spans):
            continue
        line = 1 + text.count("\n", 0, match.start())
        hints.append(FileHint(line=line, rule_code=match.group("rule")))
    return hints


def inline_hint_covers(hint: InlineHint, rule_code: str, line: int, term: str) -> bool:
    """
    Return True when `hint` suppresses a finding of `rule_code` at `line`.

    A hint covers its own line and the line directly below it. A hint with
    a target only covers findings about that term.
    """
    if hint.rule_code != rule_code:
        return False
    if line not in (hint.line, hint.line + 1):
        return False
    return hint.target is None or hint.target == term
