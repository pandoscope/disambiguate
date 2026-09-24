# Docs rules

These rules hold for every surface except chat: files, comments, commit messages and tracker text.

## Sentence shape

- `articles` [M] Omit articles only where the sentence still reads naturally and every referent resolves.
- `one-fact` [H] Put one fact in each clause, since more sentences are fine and denser ones are not.
- `actor-subject` [H] Make the actor the subject, and keep config, fields and files as objects.
- `verb-distance` [H] Bring the verb within four words of its subject, with no clause between verb and complement.
- `relative-clause` [H] Open a relative clause with "that" or "which", or give it a sentence of its own.
- `referent` [M] Make every "the X" and "its" point to something named in the current or previous sentence.
- `known-new` [M] Open each sentence with what the previous one named, then add the news.
- `event-noun` [H] Write an event as a verb, never as a noun.
- `skimmable` [M] Let a skimming reader stop after any sentence and have understood it.

## Content

- `present-tense` [H] State the present, and leave history to commit messages.
- `removed-mention` [H] Erase every mention of a removed feature, and put migration notes in the commit's BREAKING CHANGE footer.
- `non-requirement` [H] State no non-requirement unless saying it simplifies the solution.
- `reader-scope` [M] Cut text the reader decides nothing with: rationale they cannot use and rejected alternatives.
- `pitch` [H] Cut pitch and value words.
- `store-id` [F] Name no private record id in public text, and state the reason in plain words instead.
- `shared-contract` [M] State a contract several things share once, then give each instance only its deltas.

## References

- `consistent-term` [M] Give one thing one name throughout a text, and never use that name for a second thing.
- `drifting-ref` [H] Link a fact maintained elsewhere instead of restating it as a count, a far position or a section name, while adjacency words stay fine.
- `one-home` [M] Keep each fact in one place and reference it from everywhere else, and let a declared copy name its source and update path.
- `glossary-vocab` [M] Use the project's glossary terms in titles, test names and interfaces.
- `ignore-hint` [M] Reword or link before suppressing a glossary finding, because a suppression is the last resort.

## Examples

Not: "The hook, between ensure-repos and the composer,
switches each clone the order's `checkouts:` block names to its ref,
leaves a clone with local changes alone,
and never touches the waybill clone itself."

Yes: "Hook runs between ensure-repos and composer.
It reads the `checkouts:` block of the order.
For each repository named there, it switches that clone to the listed ref.
It skips a clone with local changes and says so.
It never touches the waybill clone."

Not: "The waybill order is the only receiver.
A fire of the waybill repository from an order branch carries it."

Yes: "The waybill order is the only receiver.
It arrives when the Routine fires from an order branch of the waybill repository."

The first version of each turns an event into a noun, hangs prepositional phrases on it, and holds the subject apart from its verb.
