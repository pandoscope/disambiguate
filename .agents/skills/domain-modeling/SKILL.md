---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when the user wants to pin down domain terminology or a ubiquitous language, record an architectural decision, or when another skill needs to maintain the domain model.
metadata.derived-from: https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/domain-modeling/SKILL.md
metadata.derivation-note: Glossary output retargeted from a root CONTEXT.md to docs/glossary/ (one file per term, `uvx disambiguate` format); CONTEXT.md/CONTEXT-MAP.md file-structure section dropped; ADR mechanics delegated to the writing-adrs skill.
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the *active* discipline — challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallise. (Merely *reading* the glossary for vocabulary is not this skill — that's a one-line habit any skill can do. This skill is for when you're changing the model, not just consuming it.)

The domain model lives in two places:

- **Glossary** — `docs/glossary/`, one markdown file per term, in the format `uvx disambiguate` expects (see below). Never a root `CONTEXT.md`.
- **Decisions** — ADRs in `docs/adr/`, per the `writing-adrs` skill.

Glossary entries, ADRs, docs: written and checked with the `writing-prose` skill if available, surface `markdown` — precision and understandability must not suffer.

Create files lazily — only when you have something to write. If `docs/glossary/` doesn't exist, create it when the first term is resolved.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `docs/glossary/`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Update the glossary inline

When a term is resolved, write its glossary file right there. Don't batch these up — capture them as they happen.

Glossary entries must be totally devoid of implementation details. The glossary is not a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer to create an ADR when the three-part bar in the `writing-adrs` skill is met (hard to reverse, surprising without context, the result of a real trade-off). Format, numbering, and location also come from `writing-adrs`.

## Glossary entry format

One file per term in `docs/glossary/`, consumable by `uvx disambiguate`:

- **Filename is the slug**: lowercase letters, digits, single hyphens (`order-line.md` → slug `order-line`). Slugs must be unique.
- **First H2 is the canonical name** (mandatory): `## Order Line`.
- **Body is free-form markdown**: one or two tight sentences defining what the term IS, not what it does. When multiple words exist for the same concept, pick the best one and list the others under `_Avoid_:`.
- **Cross-reference related terms** with standard markdown links by basename (`[Customer](customer.md)`) or wiki-style (`[[customer]]`). These links form the dependency graph `disambiguate` renders in topological order — a term that builds on another must link it.

Example `docs/glossary/invoice.md`:

```md
## Invoice

A request for payment sent to a [Customer](customer.md) after delivery.

_Avoid_: Bill, payment request
```

Rules:

- **Be opinionated.** One canonical term per concept; competing words go under `_Avoid_`.
- **Only include terms specific to this project's context.** General programming concepts (timeouts, error types, utility patterns) don't belong even if the project uses them extensively.
- Validate with `uvx disambiguate --lint` after editing.
