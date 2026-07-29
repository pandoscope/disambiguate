## Term-mention

An occurrence of a [term](term.md)'s canonical name or [slug](slug.md) —
or of one of its [avoided-terms](avoided-term.md) — in a document's prose.
Term-mentions are what [drift](drift.md) detection matches against.

Matching is case-insensitive and word-boundaried, where a hyphen counts as
a word character: `term` never matches inside `unlinked-term`, so a mention
of a compound term is not a mention of its parts. Text inside fenced code
blocks, inline code spans, or links of either syntax (display text
included) is never a term-mention.
