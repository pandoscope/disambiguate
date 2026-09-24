## Drift-check

One named, coded rule detecting a class of [drift](drift.md). Every
drift-check has a stable [rule-code](rule-code.md), reports offending
[term-mentions](term-mention.md) as fatal findings, and exits the `--drift`
run non-zero when any finding survives.

Shipped drift-checks:

- `unlinked-term`: the first prose mention of a [term](term.md) in a document is not its link.
  The finding points at that first plain mention.
  Later plain mentions after the link are fine.
  A link after a plain mention does not count,
  and a link in a heading counts only when the heading comes before every prose mention.
  A **term** that carries a non-glossary (colloquial) meaning is intentionally the same finding:
  an unlinked mention either should be linked or should be reworded.
- `wrong-alias`: prose uses an [avoided-term](avoided-term.md) — a
  forbidden synonym — where the canonical term is meant. The finding names
  the canonical term to use instead.
- `term-case`: a mid-sentence term-mention written with casing that
  disagrees with the term's H2 heading. Expected casing is derived from
  the heading: an internal capital (`GitHub`) or a capitalized non-first
  word (`Term Case`) marks a proper noun kept verbatim; otherwise the
  heading capital is heading style and prose expects lowercase.
  Sentence-initial mentions are always skipped — a capital there is
  grammar, not drift. Single-word proper nouns whose only capital is the
  first letter (`Disambiguate`) are indistinguishable from heading style
  and derive as common nouns; the per-term override planned in backlog
  B2 (#41) is the escape hatch beyond suppression.
