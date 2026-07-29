"""
Term-mention matching: find occurrences of a term's name in prose.

A term-mention is an occurrence of a term's canonical name or slug (or an
avoided-term) in a document's prose. Matching is case-insensitive and
word-boundaried, where a hyphen counts as a word character: `term` does not
match inside `unlinked-term`, so a mention of a compound term never doubles
as a mention of its parts.

DECISION:SCOPE — "word boundary" is interpreted hyphen-aware; compound-term
mentions are not mentions of their parts (avoids false positives between
e.g. `drift` and `drift-check`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .parser import _FENCED_CODE_RE, _INLINE_CODE_RE

# Whole-link spans to exclude from mention matching: a mention inside an
# existing cross-reference (or any link's display text) is already linked
# prose, not drift. Images (`![...](...)`) are covered by the same pattern.
_MD_LINK_SPAN_RE = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
_WIKILINK_SPAN_RE = re.compile(r"!?\[\[[^\]]*\]\]")

# HTML comments carry ignore-hints (which name the very terms they
# silence) and are invisible in rendered markdown — never a term-mention.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class Mention:
    """
    One matched term-mention in a document.

    offset: 0-based character offset of the match start.
    line: 1-based line number of the match start.
    matched: the exact text as it appears in the document.
    """

    offset: int
    line: int
    matched: str


def _variant_pattern(variants: list[str]) -> re.Pattern[str]:
    """
    Compile a case-insensitive pattern matching any of `variants` whole.

    Boundaries treat `[A-Za-z0-9-]` as word characters, so a variant never
    matches inside a larger word or a larger hyphenated compound.
    """
    alternation = "|".join(
        re.escape(v) for v in sorted(variants, key=len, reverse=True)
    )
    return re.compile(
        rf"(?<![A-Za-z0-9-])(?:{alternation})(?![A-Za-z0-9-])",
        re.IGNORECASE,
    )


def masked_spans(text: str) -> list[tuple[int, int]]:
    """
    Return the (start, end) spans of `text` excluded from mention matching.

    Excluded regions: fenced code blocks, inline code spans, and whole
    links of either syntax (markdown and wiki-style), including their
    display text. Spans are in document order and may touch but not nest.
    """
    spans: list[tuple[int, int]] = []
    for pattern in (
        _FENCED_CODE_RE,
        _INLINE_CODE_RE,
        _MD_LINK_SPAN_RE,
        _WIKILINK_SPAN_RE,
        _HTML_COMMENT_RE,
    ):
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end()))
    return sorted(spans)


def _is_masked(offset: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """Return True when [offset, end) intersects any masked span."""
    return any(offset < span_end and end > span_start for span_start, span_end in spans)


def find_mentions(text: str, variants: list[str]) -> list[Mention]:
    """
    Find every prose mention of any variant in `text`, in document order.

    text: full markdown source of a document.
    variants: non-empty spellings to match (canonical name, slug, ...).

    Returns
    -------
    A list of Mention objects ordered by offset; empty list when nothing
    matches. Matches inside code fences, inline code spans, or links
    (either syntax, display text included) are excluded.

    """
    pattern = _variant_pattern([v for v in variants if v])
    spans = masked_spans(text)
    mentions: list[Mention] = []
    for match in pattern.finditer(text):
        if _is_masked(match.start(), match.end(), spans):
            continue
        line = 1 + text.count("\n", 0, match.start())
        mentions.append(
            Mention(offset=match.start(), line=line, matched=match.group(0))
        )
    return mentions
