---
name: writing-prose
description: >
  Prose rules per surface, and the loop that writes, rewrites and reviews
  prose against them. Use when writing or rewriting docs, code comments,
  commit messages, tickets, pull request bodies, review comments, skill
  files or CLAUDE.md, or when reviewing any of them for prose.
---

# Writing Prose

Rules live in `rules/`, one sentence each, with an id and a tier:

- **F**: `check.sh` decides, and a finding is final.
- **H**: `check.sh` prints a candidate, and you confirm or dismiss it.
- **M**: you judge the rule by reading.

## Surfaces

Name the surface first: `chat`, `ticket`, `tracker` (pull request bodies and comments), `markdown`, `skill`, `primed` (files loaded into every session), `comment` (code comments and help text) or `commit`.
`check.sh --rules <surface>` names the rules files the surface reads.

## Loop

1. Read the surface's rules files.
2. Draft.
   To rewrite, read the old block, draft it fresh from the rules, then cut.
   Never patch the old sentences.
3. Run `check.sh <surface> <file>`.
   A rewrite adds `--before <old-file>`; `-` as file reads stdin.
   Fix every F finding.
   Confirm or dismiss every H candidate, and fix the confirmed ones.
4. Judge every M rule the run lists at its end.
5. Repeat steps 3 and 4.
   From the second round on, fix findings in place.
6. Layout comes last on the surfaces that read the layout rules.
   Once the content passes, place the semantic line breaks and run step 3 once more.
   A rewrap of lines the content work left alone is a reflow and goes in a style commit of its own, checked with `--style`.
   When a request puts layout before a content review, tell the principal that the order breaks this step and ask before you start.

A text passes when `check.sh` exits 0, every H candidate is settled and no M rule is broken.
M findings still open after round two go to the principal as a report, not into a third round.

## Who reviews

- F and H rules: `check.sh`, on every surface, whenever you write.
- M rules on tickets, tracker text and pull request bodies: a subagent reviews them before you post.
  It sees only the text, the surface and the rules.
  Your own context misses audience drift and takes compliance claims at face value.
  Without subagents, review it yourself and say so.
- M rules on repository files in a pull request: the project's prose review pass.
  Without one, the subagent reviews them.

Chat takes no subagent.
Apply its rules as you write.
