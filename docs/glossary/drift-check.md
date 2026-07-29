## Drift-check

One named, coded rule detecting a class of [drift](drift.md). Every
drift-check has a stable [rule-code](rule-code.md), reports offending
[term-mentions](term-mention.md) as fatal findings, and exits the `--drift`
run non-zero when any finding survives.

Shipped drift-checks:

- `unlinked-term`: a document mentions a [term](term.md) in plain prose but
  never links it. Linking the term once anywhere in the document satisfies
  the rule for every mention in that document — first-occurrence linking is
  the convention, later plain mentions are fine. A term used with a
  non-glossary (colloquial) meaning is intentionally the same finding: an
  unlinked mention either should be linked or should be reworded.
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
