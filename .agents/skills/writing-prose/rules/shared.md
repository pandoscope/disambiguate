# Shared rules

These rules hold on every surface.
SKILL.md defines the tier in brackets.
Each rules file names its surfaces in its opening line, and `check.sh --rules` holds the same mapping, so the two change together.

## Register

- `filler` [F] Cut filler words: "just", "really", "basically", "actually", "simply".
- `pleasantry` [F] Cut pleasantries such as "sure", "certainly", "of course" and "happy to help".
- `hedging` [H] Cut hedging, signposting and meta-commentary.
- `not-just` [H] Say what a thing is, without the "not just X but Y" escalation.
- `ai-pattern` [H] State a claim directly, without an antithetical pair, a "not because X but because Y", a strawman opener or a kicker sentence.
- `impression` [M] Let content land without asserting its depth or over-explaining its mechanism.
- `precise-word` [M] Use the shortest word that loses no meaning and the established term over an explanation, never a vaguer word to save tokens.
- `abbreviation` [H] Abbreviate established terms only.
- `code-exact` [F] Keep terms, code and quoted errors exact, so a rewrite leaves every code block byte-identical.
- `flat` [M] Compress by cutting words, never by nesting clauses.
- `clarity-exempt` [M] Write security warnings, irreversible actions and ordered steps in full, without compression.

## Checked elsewhere

The project's own checks may cover glossary links, avoided spellings, term casing, ticket keywords and reference style in chat.
Where they run, their verdict stands and this skill does not repeat it.
