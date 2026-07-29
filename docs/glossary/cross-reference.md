## Cross-reference

A link from one [term](term.md) to another. Cross-references come in two
syntactic forms, both supported:

- Standard markdown: `[Alias](foo.md)` — resolves to the term whose slug
  matches the link's basename, regardless of path, so
  `[Alias](path/to/foo.md)` also resolves to `foo`. A `#fragment` after
  the path is ignored: `[Alias](foo.md#heading)` resolves to `foo`.
- Wiki-style: `[[foo]]` — resolves directly to the term with slug `foo`.
  Display text is presentation-only: `[[foo|Alias]]` and
  `[[foo|multi word alias]]` resolve to `foo`. `#fragment` targets are
  stripped: `[[foo#heading]]` and `[[foo#heading|Alias]]` resolve to
  `foo`. Embeds resolve like links: `![[foo]]` resolves to `foo`. An
  empty display text (`[[foo|]]`) still resolves to `foo` but is flagged
  by the malformed-wikilink lint check.

Targets match by exact slug — no case folding, no whitespace tolerance.
`[[FOO]]` extracts the slug `FOO`, which matches no canonical
[slug](slug.md) and is reported as a broken cross-reference by lint
rather than resolving to `foo`. A padded target (`[[ foo ]]`) is not
link syntax at all and creates no edge.

Cross-references are the edges of the dependency graph. A term that
cross-references another depends on it: when rendered, the referenced term
must come first.

Cross-references inside fenced code blocks or inline code spans are
ignored — code samples that happen to contain link-shaped text do not
create edges.

## Link-as-if-exists

A new domain concept is introduced by writing a cross-reference to its
[slug](slug.md) *as if the term file already existed*. Until the file
lands, the broken-cross-reference check of `--lint` reports the link as
a precise, fatal finding — "a new term was used but never defined" needs no
heuristics. Creating the term file is what registers the concept and turns
the finding off.

Tickets declare their new vocabulary the same way: an `Introduces:` list
naming each new term as a slug, each linked as if it existed. The list is
the durable record of the vocabulary a ticket intends to add.
