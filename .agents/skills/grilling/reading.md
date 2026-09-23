# Reading a returned grilling session — interpretation reference

Consulted when answers are in: what the returned JSON means, for
recording it and for answering questions about it. Authoring rules live
in [format.md](format.md); field contract in
`render/decision-context.ts`.

## What each answer says

Answer state per question: `chosen` (slot id), `freeText`,
`rejectionReasons`, `correction`, `disconfirmedPreferences`, `skipped`.
Read them as typed events, not as a preference score:

- **Picks slot 1** — weak confirmation. Preference-driven picks are the
  weakest evidence in the set: a rule that only ever "confirms" choices
  its own recommendation caused has no independent evidence behind it.
  Read the provenance before treating it as support.
- **Picks slot 2 over slot 1** — the cited rule lost to fresh judgment
  on this case. Load-bearing.
- **Picks a wildcard** — a gap in the preference model. Highest learning
  value in the set.
- **Picks free text** — a branch nobody listed. The listed options were
  the whole hypothesis space and it was wrong.
- **Correction** ("N, but actually because …") — the option is accepted
  and its stated reason replaced. The highest-signal event: prediction
  right, model wrong. Never read as a plain hit.
- **Skipped** — no ruling. Not a miss, not a hit, and not evidence
  either way.
- **`disconfirmedPreferences`** — rules the decider says do not apply
  here. Neither win nor loss; recorded distinctly so a rule is not
  punished for being cited where it was irrelevant.

Choosing a listed option confirms that option's if-clause as the
operative rejection reason — recorded verbatim, never inferred. The
non-chosen options' if-clauses are recorded presumed-false, and
confirmed in one line only when the record would otherwise be
ambiguous.

## Prediction vs recommendation

Two different claims, scored apart:

- **Prediction** = slot 1, what the preference set says the user picks.
  `preference-driven` when it cites rules, `cold` when no rule applied.
- **Recommendation** = the agent's honest best. Slot 2 when the two
  diverge; the divergence being visible is the point — it is the
  echo-chamber gauge.

Hit rates are reported in those two streams separately.
Preference-driven must beat cold or the preference memory is not
earning its context budget. A near-perfect preference-driven rate is a
smell — grilling gone soft, or an echo chamber — not success. Cold
misses score nothing against the preference model (there was none):
they are judgment calibration, and the best seeds for new rules.
Near-ties are never counted as misses.

## Scores

A displayed percent is a share of that question's total, not a
confidence. Its parts: matched preference weights (normalized 2^-i by
rank) plus the agent's own `agentScore`, capped so agent judgment never
outvotes the top-ranked preference. The free-text slot carries
`noneScore` — the agent's estimate that none of the listed options fit.
A high one that the answer confirms means the options were badly drawn,
which is a finding about the question, not about the user.
