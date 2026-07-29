# Avoided-terms live in the `_Avoid_:` prose line

The `wrong-alias` drift-check needs a per-term list of forbidden synonyms.
Decision: formalize the `_Avoid_:` prose line in term files — literal
`_Avoid_: alias one, alias two` prefix, comma-separated on one line —
instead of adding a separate structured metadata field. One source of
truth, already rendered to readers; the grammar is now load-bearing (the
parser reads it), so changing it means touching every adopting term file.
Resolved on ticket #38.
