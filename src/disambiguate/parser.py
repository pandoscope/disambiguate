"""
Parse a single glossary term file.

A term is a markdown file. The first H2 heading is the canonical name; the
file basename (with `.md` stripped) is the slug; the full text is the body;
markdown and wikilink cross-references resolve to slugs by basename.

Code blocks (fenced ``` or ~~~) and inline code spans (single backticks) are
stripped before link extraction so that example link syntax in code never
counts as a real cross-reference.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedTerm:
    """
    The result of parsing a single term file.

    slug: stable identifier (file basename without `.md`).
    canonical_name: text of the first H2 heading, or None if no H2 found.
    body: the full original markdown text, returned verbatim for rendering.
    link_slugs: cross-reference targets, in document order, duplicates preserved.
        External URLs, non-`.md` links, and links inside any kind of code are
        excluded.
    auto_prune: the term declares that it may be removed once nothing
        links it. Absent marker means no consent.
    """

    slug: str
    canonical_name: str | None
    body: str
    link_slugs: list[str]
    auto_prune: bool = False


_FENCED_CODE_RE = re.compile(
    r"^(?P<fence>```+|~~~+)[^\n]*\n.*?^(?P=fence)\s*$",
    re.MULTILINE | re.DOTALL,
)

# Inline code: a run of one-or-more backticks, then content, then the same
# count of backticks. Match shortest content. Does not span multiple lines —
# fenced blocks handle that.
_INLINE_CODE_RE = re.compile(r"(?P<ticks>`+)(?!`).*?(?P=ticks)")

_H2_RE = re.compile(r"^##\s+(?P<name>.+?)\s*$", re.MULTILINE)

# The `d10e` annotation surface: an HTML comment carrying a
# comma-separated list of annotations for the term it sits in. Invisible
# in rendered markdown, and outside the H2-first invariant the lint and
# the MD041 override rely on.
_D10E_ANNOTATION_RE = re.compile(r"<!--\s*d10e:\s*(?P<annotations>[^>]*?)\s*-->")

AUTO_PRUNE = "auto-prune"

# Avoided-terms line (ADR 0001): literal `_Avoid_:` prefix, then
# comma-separated aliases on the same line.
_AVOID_LINE_RE = re.compile(r"^_Avoid_:\s*(?P<aliases>.+?)\s*$", re.MULTILINE)

# Standard markdown link to an .md file: [text](path/to/foo.md), with an
# optional #fragment after the path — the fragment is stripped, only the
# path is captured. `#` is excluded from path characters so the greedy path
# match can never swallow a fragment that itself ends in `.md`.
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s#]+\.md)(?:#[^)\s]*)?(?:\s+\"[^\"]*\")?\)")

# Wikilink: [[slug]], [[slug|display text]], [[slug#fragment]], or any
# combination (no spaces inside the slug, conservative). A `#fragment`
# (heading or ^block target, spaces allowed) is stripped — only the slug
# resolves. Everything after the first pipe is display text — Obsidian
# treats it as resolver-irrelevant even when empty or containing more pipes,
# so the lenient tail `[^\[\]]*` matches [[slug|]] and [[a|b|c]] too. An
# empty target ([[|text]]) never matches. Lint flags malformed pipe forms.
_WIKILINK_RE = re.compile(r"\[\[([^\[\]|\s#]+)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")

# Any bracketed [[...]] span containing a pipe, well-formed or not. Used to
# detect malformed pipe forms for lint; validation happens in code, not in
# the regex.
_PIPED_WIKILINK_RE = re.compile(r"\[\[([^\[\]]*\|[^\[\]]*)\]\]")


def _strip_code(text: str) -> str:
    """
    Remove fenced code blocks and inline code spans from `text`.

    Fenced code blocks are removed first (they may contain backticks); inline
    code spans afterwards. The returned string is not valid markdown — its
    only purpose is link extraction.
    """
    without_fenced = _FENCED_CODE_RE.sub("", text)
    return _INLINE_CODE_RE.sub("", without_fenced)


def _extract_canonical_name(text: str) -> str | None:
    """Return the text of the first H2 heading, or None if no H2 is present."""
    match = _H2_RE.search(text)
    if match is None:
        return None
    return match.group("name").strip()


def _is_url(path: str) -> bool:
    """A markdown link path is a URL if it contains a scheme separator `://`."""
    return "://" in path


def _path_basename_slug(path: str) -> str:
    """Strip directory components and the `.md` suffix from a markdown link path."""
    basename = path.rsplit("/", 1)[-1]
    return basename[: -len(".md")]


def extract_md_link_paths(text: str) -> list[str]:
    """
    Return the raw `.md` paths from standard markdown links, in document order.

    Code blocks and inline code spans are excluded. URLs are excluded as well
    — a `https://example.com/foo.md` link is a web reference, not a glossary
    cross-reference. Paths are returned verbatim; basename resolution is the
    caller's job.
    """
    code_stripped = _strip_code(text)
    return [
        match.group(1)
        for match in _MD_LINK_RE.finditer(code_stripped)
        if not _is_url(match.group(1))
    ]


def extract_wikilink_slugs(text: str) -> list[str]:
    """
    Return the slugs of every wiki-style `[[slug]]` link in document order.

    Code blocks and inline code spans are excluded.
    """
    code_stripped = _strip_code(text)
    return [match.group(1) for match in _WIKILINK_RE.finditer(code_stripped)]


def extract_malformed_wikilinks(text: str) -> list[str]:
    """
    Return the raw text of every malformed piped wikilink, in document order.

    A piped wikilink is malformed when its target (before the first pipe,
    fragment stripped) is empty, its display text is empty, or it contains
    more than one pipe. Such links still resolve leniently on their first
    segment (Obsidian semantics); this function only reports them so lint
    can flag sloppy authoring. Code blocks and inline code spans are excluded.
    """
    code_stripped = _strip_code(text)
    malformed: list[str] = []
    for match in _PIPED_WIKILINK_RE.finditer(code_stripped):
        target, *display = match.group(1).split("|")
        target = target.split("#", 1)[0]
        if target == "" or len(display) != 1 or display[0] == "":
            malformed.append(match.group(0))
    return malformed


def extract_all_link_refs(text: str) -> list[tuple[str, str | None]]:
    """
    Return every cross-reference in document order as (slug, path) pairs.

    Both standard markdown links to `.md` files (basename-resolved) and
    wiki-style `[[slug]]` links are collected. URLs and code-block contents
    are excluded. Duplicates are preserved — callers de-duplicate where
    they need to.

    Returns
    -------
    Pairs of (slug, raw link path). The path is the verbatim markdown link
    target for standard links, and None for wikilinks — wikilinks address
    terms by slug and carry no filesystem path.

    """
    code_stripped = _strip_code(text)

    # Walk both regexes and interleave by document position so duplicates
    # from the two syntaxes appear in source order.
    matches: list[tuple[int, str, str | None]] = []
    for match in _MD_LINK_RE.finditer(code_stripped):
        path = match.group(1)
        if _is_url(path):
            continue
        matches.append((match.start(), _path_basename_slug(path), path))
    for match in _WIKILINK_RE.finditer(code_stripped):
        matches.append((match.start(), match.group(1), None))

    matches.sort(key=lambda triple: triple[0])
    return [(slug, path) for _, slug, path in matches]


def extract_all_link_slugs(text: str) -> list[str]:
    """
    Return the slugs of every cross-reference in document order.

    Path-free view of `extract_all_link_refs` — same extraction, same
    ordering and duplicate semantics.
    """
    return [slug for slug, _ in extract_all_link_refs(text)]


def extract_d10e_annotations(text: str) -> set[str]:
    """
    Return every `d10e` annotation declared in `text`.

    Annotations live in HTML comments of the form
    `<!-- d10e: one, two -->`, so they stay invisible in rendered
    markdown. Multiple comments accumulate; unknown names are returned
    as-is for callers to ignore. Code blocks and inline code spans are
    excluded, so a comment shown as an example never counts.
    """
    code_stripped = _strip_code(text)
    annotations: set[str] = set()
    for match in _D10E_ANNOTATION_RE.finditer(code_stripped):
        for name in match.group("annotations").split(","):
            if name.strip():
                annotations.add(name.strip())
    return annotations


def parse_term_text(slug: str, text: str) -> ParsedTerm:
    """
    Parse the contents of a single term file.

    slug: stable identifier, supplied by the caller (typically the file basename).
    text: raw markdown contents.

    Returns
    -------
    ParsedTerm with canonical_name, body, and link_slugs populated.
    canonical_name is None if no H2 heading is found — the lint reports that as
    a fatal error elsewhere; the parser does not raise.

    """
    canonical_name = _extract_canonical_name(text)
    link_slugs = extract_all_link_slugs(text)
    return ParsedTerm(
        slug=slug,
        canonical_name=canonical_name,
        body=text,
        link_slugs=link_slugs,
        auto_prune=AUTO_PRUNE in extract_d10e_annotations(text),
    )


def extract_avoided_terms(text: str) -> list[str]:
    """
    Return the avoided-terms declared on a term file's `_Avoid_:` line.

    The grammar (ADR 0001): a single line starting with the literal
    `_Avoid_:` prefix, followed by comma-separated aliases.

    text: raw markdown contents of a term file.

    Returns
    -------
    The aliases in declaration order; empty list when no `_Avoid_:` line
    is present.

    """
    match = _AVOID_LINE_RE.search(text)
    if match is None:
        return []
    return [
        alias.strip() for alias in match.group("aliases").split(",") if alias.strip()
    ]
