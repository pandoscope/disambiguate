## Avoided-term

A forbidden synonym for a canonical [term](term.md), declared on the term
file's `_Avoid_:` line — a single line of comma-separated aliases:

```markdown
_Avoid_: gadget, doohickey
```

Using an avoided-term in prose where the canonical term is meant is
[drift](drift.md): the `wrong-alias` drift detection rule reports it and
names the canonical term to use instead. The `_Avoid_:` line is the single
source of truth — it is rendered to readers and parsed by the checker
alike (ADR 0001).
