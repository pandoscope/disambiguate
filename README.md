# Disambiguate
<!-- markdownlint-disable MD033 -->

<p align="center">
  <a href="https://github.com/frankify-app/disambiguate/actions/workflows/ci.yml?query=branch%3Amain">
    <img src="https://img.shields.io/github/actions/workflow/status/frankify-app/disambiguate/ci.yml?branch=main&label=CI&logo=github&style=flat-square" alt="CI Status" >
  </a>
  <a href="https://codecov.io/gh/frankify-app/disambiguate">
    <img src="https://img.shields.io/codecov/c/github/frankify-app/disambiguate.svg?logo=codecov&logoColor=fff&style=flat-square" alt="Test coverage percentage">
  </a>
</p>
<p align="center">
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff">
  </a>
  <a href="https://github.com/j178/prek">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json" alt="prek">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/disambiguate/">
    <img src="https://img.shields.io/pypi/v/disambiguate.svg?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/disambiguate.svg?style=flat-square&logo=python&amp;logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/disambiguate.svg?style=flat-square" alt="License">
</p>

---

**Source Code**: <a href="https://github.com/frankify-app/disambiguate" target="_blank">https://github.com/frankify-app/disambiguate </a>

---

Disambiguate resolves markdown glossary terms and their transitive
dependencies in topological order. Point it at a directory of `*.md` term
files in either [GitHub format](docs/glossary/github-format.md) or
[Obsidian format](docs/glossary/obsidian-format.md), ask for a slug or two,
and get back a self-contained markdown document where every term is
defined before it is referenced.

The vendored skills use one org term: [grilling](docs/glossary/grilling.md).

## Quickstart

```bash
uvx disambiguate                       # render the entire glossary
uvx disambiguate topological-order     # render one term and its dependency closure
uvx disambiguate --from notes.md       # extract glossary-shaped links from a doc
uvx disambiguate --explain             # render Disambiguate's own bundled spec
uvx disambiguate --lint                # validate the glossary
uvx disambiguate --drift               # detect prose drifting from the glossary
uvx disambiguate prune                 # remove terms no file links
```

The runtime is stdlib-only — `pip install disambiguate` brings in nothing
else. `uvx` works without an explicit install.

## Installation

```bash
pip install disambiguate
```

## How it works

[Prune](docs/glossary/prune.md) removes terms no file in the repository
links. It serves repos that acquire a shared term set and use only part of
it. A term consents by carrying an
[auto-prune](docs/glossary/auto-prune.md) annotation.

The pipeline parses each [term](docs/glossary/term.md) into a body plus a
list of [cross-references](docs/glossary/cross-reference.md), builds a
[dependency](docs/glossary/dependency.md) graph from those references, then
runs the [resolver](docs/glossary/resolver.md) to produce
[topological order](docs/glossary/topological-order.md). The same pipeline
backs [from-mode](docs/glossary/from-mode.md) and `--explain`.

`--drift` detects [drift](docs/glossary/drift.md) — prose that uses the
vocabulary without following it: terms mentioned but never linked, and (as
the checks grow) forbidden synonyms and wrong casing. Each
[drift-check](docs/glossary/drift-check.md) reports fatal findings named by
a stable [rule-code](docs/glossary/rule-code.md); false positives are
silenced precisely with [ignore-hints](docs/glossary/ignore-hint.md), and
already-drifted repos adopt incrementally through a checked-in
[drift-baseline](docs/glossary/drift-baseline.md).

For the architectural map, see [docs/architecture.md](docs/architecture.md).
For the full vocabulary, see the
[bundled glossary](docs/glossary/disambiguate.md) — Disambiguate's own
dogfood.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Conventional commits required.
A release is a version bump merged to `main` ([docs/releasing.md](docs/releasing.md)).

## Org glossary

Org-genome terms stamped in by the
[template](https://github.com/pandoscope/agentic-engineering-template)
(rooted here so `disambiguate --lint` can reach them):
[org](docs/glossary/org.md),
[org genome](docs/glossary/org-genome.md),
[pando](docs/glossary/pando.md),
[pando cell](docs/glossary/pando-cell.md),
[reinset](docs/glossary/reinset.md),
[principal](docs/glossary/principal.md),
[agent session](docs/glossary/agent-session.md),
[memory repo](docs/glossary/memory-repo.md),
[decision-memory](docs/glossary/decision-memory.md),
[evidence-memory](docs/glossary/evidence-memory.md),
[session-memory](docs/glossary/session-memory.md),
[pandoscope template](docs/glossary/pandoscope-template.md),
[template stamp](docs/glossary/template-stamp.md).
