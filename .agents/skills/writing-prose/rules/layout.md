# Layout rules

These rules hold for text kept in files, where a reflow pollutes diffs: Markdown, skill files, primed files and code comments.

- `sembr` [H] Break new or rewritten prose at sentence or clause boundaries, one per line.
- `reflow` [F] Never reflow untouched lines, and put a deliberate mass reflow in its own style commit listed in the blame-ignore file.
- `long-line` [H] Split a sentence too long to break at a clause, or keep it on one line, and never break it at a fixed width.
