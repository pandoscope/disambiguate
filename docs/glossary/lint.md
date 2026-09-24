## Lint

The `--lint` mode validates a [glossary](glossary.md) against six
constraints. Any violation is fatal — the command exits non-zero with the
problem reported to stderr.

Checks:

- **Cycles** in the [dependency](dependency.md) graph. A cycle makes
  topological ordering impossible.
- **Broken cross-references**: a [cross-reference](cross-reference.md) whose
  basename does not match any term in the glossary.
- **Duplicate slugs**: two term files sharing a basename.
- **Missing H2 heading**: a term file with no H2 (`##`) heading on any line. The
  H2 is the canonical name; without it the term has no identity.
- **Invalid [slug](slug.md) format**: a slug that does not match the canonical
  format `^[a-z0-9]+(?:-[a-z0-9]+)*$` — lowercase letters, digits, and single
  hyphens between segments.
- **Reachability orphans**: terms that no configured root document can reach
  by following markdown links. Roots default to the repository's
  `README.md`; override with `--roots` or `DISAMBIGUATE_ROOTS`.

Reachability uses a visited-set walk over both glossary terms and external
markdown documents. Cycles in external documents are tolerated — the walk
does not topo-sort, it just collects everything visitable.

The orphan check exists to keep the glossary honest. If a term is not
linked from anywhere a reader is likely to start, it is dead vocabulary,
and the lint says so.
