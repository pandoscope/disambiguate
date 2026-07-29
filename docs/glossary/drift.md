## Drift

Divergence between prose usage of a [term](term.md) and the
[glossary](glossary.md)'s canonical form: mentioning a term without ever
linking it, using a forbidden synonym in place of the canonical name, or
writing a term with the wrong casing.

Drift is detected by drift-checks run through the CLI's `--drift` mode.
Drift-checks are fatal by default and are kept separate from the
deterministic [lint](lint.md) checks: lint validates the glossary itself,
drift validates the prose that uses it. The corpus examined is the same
set of documents the reachability lint check walks (roots from `--roots` /
`DISAMBIGUATE_ROOTS`, default `README.md`).
