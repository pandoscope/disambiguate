# Grilling question format — semantics reference

Consulted from SKILL.md when authoring session JSON. Machine-readable
authority is `render/decision-context.ts`; this file carries meaning
behind its fields.

## Slot semantics (`kind`)

- `usual` — what active preference set predicts user picks, iff active
  rules apply, named in `matches` (entries of session-level ordered
  `preferences` list) — never from vibes. One option may match several
  preferences; contradictory options may each match their own. Matches
  render as footnote refs anchored to ranked lineage entries — do not
  restate rules in prose. Rule match = rule's condition matches, NOT
  "this exact decision seen before" — never dodge a general rule by
  narrowing decision description.
- `pick` — agent's independent best, formed on merits, not preferences.
  No matching rule → slots 1/2 merge into cold `pick`; "no active rule
  applies" claim is recorded via `lineage.cold` (records carry injected
  preference set, so replay flags matching-but-uncited rules — false
  cold claim is a detectable provenance defect). Coincides with usual
  (common case) → one `usual-and-pick` slot; runner-up becomes plain
  `alternative`. May carry `proposedPreferences`: candidate rules agent
  formulates as inspiration, listed separately with option.
- `wildcard` — exploratory. Mandatory wildcards become filler, user
  stops reading slot, exploration channel dies.

## Tags and excluded combinations

Compact tags render from `kind`: `matches N`, `my pick`, `cold`,
`wildcard`, `alternative`, `free text` — every slot gets at least one.
Schema-enforced exclusions: `cold` × `matches N` (cold means no slot in
question may carry matches); `wildcard` × `matches N` (preference-backed
branch is not exploratory); `wildcard` × `my pick`/`cold`/`alternative`
and `my pick` × `alternative` (kind is single-valued); `cold` only ever
accompanies `my pick` (second prediction-role slot is rejected);
`free text` never combines.

## Scoring

Ranks in session-level `preferences` list (preference-file order,
earlier = higher priority) become weights via normalized 2^-i —
lexicographic: every rank outweighs all lower ranks combined, faithful
to set's earlier-rule-wins ordering. Order stays human-owned; outcomes
propose reorders, never apply them. Option's score = its matched
preference weights + `agentScore` (0..1) capped by top preference
weight, so agent judgment never outvotes user's highest-ranked
preference. Question-level `noneScore` (0..1) is agent's residual
estimate that none of listed options fit; it scores free-text slot
through same normalization. Display: percent of question total; hover
(page) or score line (markdown) shows which preference — or agent's
judgment — contributed how much.

## Citation rules (decision-memory format split)

Per agentic-engineering-template#163/#164:

- Cite per option, not only on prediction slot — `matches` maps to
  record's `options[].rules_cited`, which is what makes rule-vs-rule
  contests recordable (chosen option's cited rules beat declined
  options'). One rule per string.
- Cite the store line verbatim — whole line, punctuation included.
  Inject mechanically: `resolve-store.sh preferences` emits the active
  set as the JSON array to paste into `preferences`. Retyping loses a
  trailing period, extraction matches nothing, and the citation scores
  silently as zero. `check.sh` fails any entry that is not a verbatim
  line of the store's `preferences.txt`.
- Disconfirmed rules ("not relevant here" toggle,
  `disconfirmedPreferences`) are recorded distinctly — record-level
  `rules_disconfirmed` — counting as neither win nor loss.
- Invariants: exactly one prediction-role slot (validated);
  `prediction_stream` is `preference-driven` iff prediction slot cites
  rules; recommendations are never back-filled.

`preferenceDocs` (session-level) maps preference names to promotion
docs; lineage footnotes link them. Fill from store's `preferences.json`
provenance data (same verbatim-rule-text identity) — never by guessing
from rule line.

Interpreting returned answers — selection events, hit-rate streams,
score meaning — is [reading.md](reading.md), not this file.
