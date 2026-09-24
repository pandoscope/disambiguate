## Resolver

The component that, given a set of requested [term](term.md) [slugs](slug.md), returns
the full [dependency](dependency.md) closure of those terms in
[topological order](topological-order.md).

Behaviour:

- Input: zero or more slugs. Zero slugs means "the whole glossary".
- Each requested slug must exist; an unknown slug is an error.
- Each slug pulls in everything it transitively depends on.
- The output is a flat list of [terms](term.md), each appearing exactly once,
  ordered so that dependencies come before dependents.

The resolver is the core of the default `disambiguate` invocation. It is
also the engine behind from-mode: once the slugs have been extracted from
the source document, resolution proceeds identically.
