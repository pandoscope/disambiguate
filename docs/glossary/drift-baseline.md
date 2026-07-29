## Drift-baseline

A generated, checked-in record of pre-existing [drift](drift.md), so
fatal drift-checks can land on an already-drifted repo without a wall of
suppressions. Findings recorded in the baseline are downgraded to
non-fatal; findings absent from it fail the run.

`disambiguate --drift --write-baseline` regenerates the file
(`.drift-baseline.json`, next to the active `pyproject.toml`, else at the
repo root). Entries are keyed by file, [rule-code](rule-code.md), and
[term](term.md) — never by line number — so they survive unrelated edits
to the same file. On a normal run, entries whose finding no longer occurs
are pruned automatically: the baseline only ever shrinks, and fixing
grandfathered drift never leaves a stale entry behind.
