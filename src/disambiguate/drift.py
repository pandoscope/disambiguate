"""
Drift-check engine: detect prose drifting from the glossary.

Drift-checks walk the same reachable corpus as the reachability lint and
report, per rule-code, places where prose usage diverges from the
glossary's canonical form. They are fatal by default and surfaced through
the CLI's `--drift` mode, kept separate from the deterministic `--lint`
checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .glossary import Glossary, Term
from .lint import walk_reachable
from .mentions import find_mentions
from .parser import extract_all_link_slugs, extract_avoided_terms
from .suppressions import (
    DriftConfig,
    FileHint,
    InlineHint,
    glob_covers,
    inline_hint_covers,
    parse_file_hints,
    parse_inline_hints,
)


@dataclass(frozen=True)
class DriftFinding:
    """
    A single drift violation.

    rule_code: stable identifier of the drift-check, e.g. "unlinked-term".
    path: document the drift occurs in.
    line: 1-based line of the offending term-mention.
    term: slug of the glossary term the finding is about.
    message: human-readable description, used directly in error output.
    """

    rule_code: str
    path: Path
    line: int
    term: str
    message: str


def _term_variants(term: Term) -> list[str]:
    """Return the spellings that count as a mention of `term`."""
    variants = [term.slug]
    if term.canonical_name is not None:
        variants.append(term.canonical_name)
    return variants


def _check_unlinked_terms(
    glossary: Glossary, corpus: dict[Path, str]
) -> list[DriftFinding]:
    """
    Report each (document, term) pair mentioned in prose but never linked.

    A single link to the term anywhere in the document satisfies the rule
    for every mention in that document. A term is never checked against its
    own defining file — a definition necessarily names itself.

    DECISION:SCOPE — self-file exemption is not in the ticket; without it
    every term file flags itself for naming its own term.
    """
    findings: list[DriftFinding] = []
    for path in sorted(corpus):
        text = corpus[path]
        linked_slugs = set(extract_all_link_slugs(text))
        for slug in sorted(glossary.terms):
            term = glossary.terms[slug]
            if path == term.path.resolve():
                continue
            if slug in linked_slugs:
                continue
            mentions = find_mentions(text, _term_variants(term))
            if not mentions:
                continue
            first = mentions[0]
            findings.append(
                DriftFinding(
                    rule_code="unlinked-term",
                    path=path,
                    line=first.line,
                    term=slug,
                    message=(
                        f"{first.matched!r} is mentioned but never linked in "
                        f"this document; link the term once, e.g. "
                        f"[{first.matched}]({slug}.md), or suppress with "
                        f"<!-- d10e: ignore[unlinked-term] {slug} -->"
                    ),
                )
            )
    return findings


def _check_wrong_aliases(
    glossary: Glossary, corpus: dict[Path, str]
) -> list[DriftFinding]:
    """
    Report avoided-term uses where the canonical term is meant.

    One finding per (document, term) at the first avoided-term mention,
    naming the matched alias and the canonical term to use instead. A term
    is never checked against its own defining file — the `_Avoid_:` line
    itself names the aliases it forbids.
    """
    findings: list[DriftFinding] = []
    for path in sorted(corpus):
        text = corpus[path]
        for slug in sorted(glossary.terms):
            term = glossary.terms[slug]
            if path == term.path.resolve():
                continue
            avoided = extract_avoided_terms(term.body)
            if not avoided:
                continue
            mentions = find_mentions(text, avoided)
            if not mentions:
                continue
            first = mentions[0]
            canonical = term.canonical_name or slug
            findings.append(
                DriftFinding(
                    rule_code="wrong-alias",
                    path=path,
                    line=first.line,
                    term=slug,
                    message=(
                        f"{first.matched!r} is an avoided-term for "
                        f"'{canonical}'; use [{canonical}]({slug}.md) "
                        f"instead, or suppress with "
                        f"<!-- d10e: ignore[wrong-alias] {slug} -->"
                    ),
                )
            )
    return findings


def _is_proper_noun(name: str) -> bool:
    """
    Derive proper-noun-ness from a term's H2 canonical name.

    A name is proper when any word carries a capital beyond the heading
    convention: an internal capital ("GitHub") or a capitalized non-first
    word ("Term Case"). A single leading capital on the first word is
    heading style, not evidence ("Widget" stays a common noun).

    DECISION:SCOPE — the ticket's "Title-Cased H2 implies proper noun" is
    undecidable for single-word H2s (every H2 here capitalizes its first
    letter), so single-leading-capital derives as common noun. Known
    misclassification: "Disambiguate". Escape hatches: suppression,
    baseline, backlog B2 override.
    """
    words = name.split()
    for index, word in enumerate(words):
        if any(ch.isupper() for ch in word[1:]):
            return True
        if index > 0 and word[:1].isupper():
            return True
    return False


def _expected_prose_forms(term: Term) -> set[str]:
    """
    Return the spellings of `term` accepted in mid-sentence prose.

    Common nouns expect the H2 name with its heading capital lowered;
    proper nouns expect the H2 name verbatim. The hyphenated slug is also
    accepted when it is not merely a case-variant of the name (an
    identifier-shaped reference like `github-format` reads deliberately;
    a bare lowercase `github` for proper-noun "GitHub" does not).
    """
    name = term.canonical_name or term.slug
    forms: set[str] = set()
    if _is_proper_noun(name):
        forms.add(name)
        if term.slug.lower() != name.lower():
            forms.add(term.slug)
    else:
        first, _, rest = name.partition(" ")
        lowered = first.lower() + (" " + rest if rest else "")
        forms.add(lowered)
        forms.add(term.slug)
    return forms


_SENTENCE_ENDERS = set(".!?:;")
_MARKDOWN_MARKERS = set("-*+>#|")


def _is_sentence_initial(text: str, offset: int) -> bool:
    """
    Return True when the mention at `offset` starts a sentence or a line.

    A capital there is grammar, not drift. Sentence-initial means: start
    of text, after sentence-ending punctuation, or first word after a
    markdown structural marker (list bullet, blockquote, heading, table
    pipe) or an empty line.
    """
    index = offset - 1
    while index >= 0 and text[index] in " \t":
        index -= 1
    if index < 0 or text[index] == "\n":
        return True
    previous = text[index]
    return previous in _SENTENCE_ENDERS or previous in _MARKDOWN_MARKERS


def _check_term_case(glossary: Glossary, corpus: dict[Path, str]) -> list[DriftFinding]:
    """
    Report mid-sentence term-mentions whose casing disagrees with the H2.

    One finding per (document, term) at the first offending mention.
    Sentence-initial mentions are skipped entirely. A term is never
    checked against its own defining file.
    """
    findings: list[DriftFinding] = []
    for path in sorted(corpus):
        text = corpus[path]
        for slug in sorted(glossary.terms):
            term = glossary.terms[slug]
            if path == term.path.resolve():
                continue
            expected = _expected_prose_forms(term)
            offending = [
                mention
                for mention in find_mentions(text, _term_variants(term))
                if mention.matched not in expected
                and not _is_sentence_initial(text, mention.offset)
            ]
            if not offending:
                continue
            first = offending[0]
            options = " or ".join(sorted(f"'{form}'" for form in expected))
            findings.append(
                DriftFinding(
                    rule_code="term-case",
                    path=path,
                    line=first.line,
                    term=slug,
                    message=(
                        f"{first.matched!r} disagrees with the casing "
                        f"derived from the term's heading; write {options} "
                        f"mid-sentence, or suppress with "
                        f"<!-- d10e: ignore[term-case] {slug} -->"
                    ),
                )
            )
    return findings


def _read_corpus(glossary: Glossary, roots: list[Path]) -> dict[Path, str]:
    """Read every document reachable from `roots` into memory, keyed by path."""
    corpus: dict[Path, str] = {}
    for path in walk_reachable(roots, glossary):
        corpus[path] = path.read_text(encoding="utf-8")
    return corpus


def run_drift_checks(
    glossary: Glossary,
    roots: list[Path],
    config: DriftConfig | None = None,
) -> list[DriftFinding]:
    """
    Run every drift-check over the corpus reachable from `roots`.

    glossary: loaded glossary.
    roots: documents from which the corpus walk starts.
    config: config-level suppression settings, or None for none.

    Returns
    -------
    A list of DriftFinding objects; empty list means no drift. Order is
    deterministic: by document path, then rule-code order per document.

    """
    corpus = _read_corpus(glossary, roots)
    raw_findings = _check_unlinked_terms(glossary, corpus)
    raw_findings.extend(_check_wrong_aliases(glossary, corpus))
    raw_findings.extend(_check_term_case(glossary, corpus))
    return _apply_suppressions(raw_findings, corpus, config)


def _apply_suppressions(
    findings: list[DriftFinding],
    corpus: dict[Path, str],
    config: DriftConfig | None = None,
) -> list[DriftFinding]:
    """
    Drop findings covered by a suppression; report stale suppressions.

    Precedence is config, then file, then inline — coarsest wins. A
    suppression that covers no raw finding is itself reported as a fatal
    `stale-suppression` finding, unless a coarser suppression of the same
    rule-code shadows it (an inline hint under a file-level opt-out, or
    either under a config ignore, must not be reported stale).
    """
    inline_by_path = {path: parse_inline_hints(text) for path, text in corpus.items()}
    file_hints_by_path = {path: parse_file_hints(text) for path, text in corpus.items()}
    kept: list[DriftFinding] = []
    for finding in findings:
        file_rules = {hint.rule_code for hint in file_hints_by_path[finding.path]}
        if config is not None and config.covers(finding.rule_code, finding.path):
            continue
        if finding.rule_code in file_rules:
            continue
        hints = inline_by_path[finding.path]
        if any(
            inline_hint_covers(hint, finding.rule_code, finding.line, finding.term)
            for hint in hints
        ):
            continue
        kept.append(finding)

    kept.extend(
        _stale_suppression_findings(
            findings, inline_by_path, file_hints_by_path, config
        )
    )
    return kept


def _stale_suppression_findings(
    raw_findings: list[DriftFinding],
    inline_by_path: dict[Path, list[InlineHint]],
    file_hints_by_path: dict[Path, list[FileHint]],
    config: DriftConfig | None,
) -> list[DriftFinding]:
    """
    Report each suppression that matches no raw finding and is unshadowed.

    Matching is computed against the raw (pre-suppression) findings so a
    hint is "used" even when a coarser surface also covers its finding.
    """
    stale: list[DriftFinding] = []

    def config_covers(rule_code: str, path: Path) -> bool:
        return config is not None and config.covers(rule_code, path)

    for path in sorted(file_hints_by_path):
        raw_here = [f for f in raw_findings if f.path == path]
        file_rules = {hint.rule_code for hint in file_hints_by_path[path]}

        for hint in file_hints_by_path[path]:
            matches = any(f.rule_code == hint.rule_code for f in raw_here)
            shadowed = config_covers(hint.rule_code, path)
            if not matches and not shadowed:
                stale.append(
                    DriftFinding(
                        rule_code="stale-suppression",
                        path=path,
                        line=hint.line,
                        term="",
                        message=(
                            f"ignore-file[{hint.rule_code}] opt-out matches "
                            f"no finding in this document; remove it"
                        ),
                    )
                )

        for inline in inline_by_path[path]:
            matches = any(
                inline_hint_covers(inline, f.rule_code, f.line, f.term)
                for f in raw_here
            )
            shadowed = inline.rule_code in file_rules or config_covers(
                inline.rule_code, path
            )
            if not matches and not shadowed:
                stale.append(
                    DriftFinding(
                        rule_code="stale-suppression",
                        path=path,
                        line=inline.line,
                        term=inline.target or "",
                        message=(
                            f"ignore[{inline.rule_code}] hint matches no "
                            f"finding on its line or the line below; "
                            f"remove it"
                        ),
                    )
                )

    if config is not None:
        config_path = (
            config.root / "pyproject.toml" if config.root else Path("pyproject.toml")
        )
        for rule_code in config.ignore:
            if not any(f.rule_code == rule_code for f in raw_findings):
                stale.append(
                    DriftFinding(
                        rule_code="stale-suppression",
                        path=config_path,
                        line=1,
                        term="",
                        message=(
                            f"config drift-ignore entry {rule_code!r} "
                            f"matches no finding in the corpus; remove it"
                        ),
                    )
                )
        for pattern, rules in config.ignore_paths.items():
            for rule_code in rules:
                if not any(
                    f.rule_code == rule_code
                    and glob_covers(pattern, f.path, config.root)
                    for f in raw_findings
                ):
                    stale.append(
                        DriftFinding(
                            rule_code="stale-suppression",
                            path=config_path,
                            line=1,
                            term="",
                            message=(
                                f"config drift-ignore-paths entry "
                                f"{pattern!r}: {rule_code!r} matches no "
                                f"finding in the corpus; remove it"
                            ),
                        )
                    )
    return stale
