## Disambiguate

The CLI tool this [glossary](glossary.md) describes. Capitalized "Disambiguate" when
referring to the tool as a proper noun; lowercase only as the command-line
invocation `uvx disambiguate`.

Disambiguate takes a markdown [glossary](glossary.md), follows the
[dependency](dependency.md) edges between [terms](term.md), and emits the
selected closure in [topological order](topological-order.md). Three
operating modes:

- **Default**: render selected slugs (or the whole glossary) — the
  [resolver](resolver.md) is the engine.
- **`--from <doc>`**: extract the slugs implicitly used in a document and
  resolve those — see [from-mode](from-mode.md).
- **`--lint`**: validate the glossary's structural integrity — see
  [lint](lint.md).

Plus `--explain`, which always renders Disambiguate's own bundled glossary
<!-- d10e: ignore[wrong-alias] principal -->
(this very glossary) regardless of which user glossary is in scope. The
intended audience for `--explain` is an LLM agent that needs to understand
Disambiguate's vocabulary before generating glossary content of its own.

Disambiguate has no third-party runtime dependencies. The implementation
fits inside the Python standard library — `argparse`, `graphlib`,
`pathlib`, `re`, `glob`, `importlib.resources`, `logging`. Installable as a
single wheel; runnable via `uvx disambiguate` with no environment setup.
