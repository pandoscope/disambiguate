## Prune

The `prune` command removes [terms](term.md) that are [orphans](lint.md) —
not reachable from any root document —
so a [glossary](glossary.md) converges to exactly the terms it uses.

A [term-mention](term-mention.md) anywhere in the repository counts as use:
a term whose canonical name or [slug](slug.md) occurs in any text file
the repository carries, the glossary directory itself excluded,
joins the roots of the reachability walk,
so it stays and so does everything it links.
Only `prune` widens use this way; `--lint` keeps measuring reachability.

Removal is consent-based.
A term opts in by carrying an [auto-prune](auto-prune.md) annotation;
`prune` removes only orphans that consent.
`--all-orphans` widens the scope to orphans that never opted in,
and `--dry-run` reports both sets without deleting anything.

Consent is decided per orphaned branch, not per term.
A branch — the connected group of orphans that reference each other,
in either direction — is removed only when every term in it consents.
One non-consenting term anywhere keeps all of it.

That last rule is a deliberate judgement rather than a necessity,
and the reasoning lives with the code that depends on it:
the `DECISION` marker on `plan_prune` in `src/disambiguate/prune.py`.
It is recorded there because that is where getting it wrong does damage —
a per-term rule silently deletes terms a surviving term still needs.

The alternative would be exempting unlinked terms from the orphan check,
which makes "unlinked" a legitimate state and blunts the check for everyone.
Removing what is unused keeps the check's teeth.
