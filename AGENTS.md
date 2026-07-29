# Disambiguate — Agent Guidelines

Repo: <https://github.com/pandoscope/disambiguate>

## Project Specifics

### Terminology

Ubiquitous language is defined in docs/glossary/. Use

```bash
uvx disambiguate==0.3.0 <term>
```

to get a topologically ordered glossary disambiguating all relevant terms
to understand the given term.

Before working on a ticket, run:

```bash
uvx disambiguate==0.3.0 --from <ticket-file>
```

or for GitHub issues:

```bash
gh issue view <number> --json body -q .body | uvx disambiguate==0.3.0 --from -
```

to resolve all referenced terms at once.

### Architecture

Read [docs/architecture.md](docs/architecture.md) before touching any code.

### Introducing new terms

Follow the link-as-if-exists convention (see
[docs/glossary/cross-reference.md](docs/glossary/cross-reference.md)): a new
domain concept is introduced by cross-referencing its slug *as if the term
file already existed*, then creating `docs/glossary/<slug>.md`. Until the
file exists, `--lint` reports the link as a fatal broken cross-reference —
that is the enforcement, not a bug.

Tickets declare new vocabulary under an `Introduces:` list, one slug per
line, each linked as if it existed:

```markdown
## Introduces

- [drift-baseline](../blob/main/docs/glossary/drift-baseline.md) — checked-in record of grandfathered drift
```

The `Introduces:` list is the durable record of the vocabulary a ticket
intends to add; the linked term files are created by the ticket's
implementation.

## Rules

- Small, single-purpose files
- Readability over brevity — straightforward, easy-to-follow code. No compact "one-liners" stretching across multiple lines (e.g. nested ternaries). Stretching across multiple lines is only allowed if it aids readability.
- When removing a feature, erase every mention of it — docs, help text, comments, tests. Don't leave "no longer supported" notes: readers who never knew it existed pay to learn it did. State what is, not what stopped being. (Migration notes belong in the commit's `BREAKING CHANGE:` footer, which is where someone upgrading looks.)
- In prose, don't state facts maintained elsewhere — counts ("the seven examples above"), far positional references, restated section names. Link the target instead. Immediate-adjacency words ("the examples above", "the following table") are fine — they only break if adjacency breaks.
- All routes and non-trivial functions: docstring contracts (params, returns, errors)
- Test cases cover edge cases and every `@returns` line

### Errors

- Forward all errors with full detail + variable values, never swallow or catch, let exceptions propagate with their full traceback to make proper debugging possible
- Never catch exceptions if they are actual errors that can't be handled
- Include relevant variable values in error messages, e.g. for JS/TS:
  `"Failed to fetch peers for workspace_id=${workspace_id}: ${e}"`

### Avoid Duplication

Duplicated code, prose, or configuration drifts:
the copies start equal and diverge silently,
and reviewers cannot tell which copy is authoritative.
Every piece of knowledge gets ONE authoritative home;
everywhere else, reference it — in this preference order:

1. **Explicit reference (preferred):** machine-readable and resolvable —
   an import/include, a hyperlink,
   a repo path with section anchor (`docs/conventions.md#commit-types`).
   Tooling and agents can follow it; link rot is detectable.
2. **Semantic reference:** when no stable, resolvable target exists
   (content in another repo without a fixed URL, a section that may move,
   help text of a tool),
   a prose pointer that names where the authority lives and how to find it —
   e.g. "grammar authority: `docs/conventions.md` § Commit types"
   or "behavior doc: `record.py --help`".

Corollaries:

- **Managed duplication is exempt but must be declared.**
  Vendored copies, generated files, and template render output are allowed
  BECAUSE they have a single source and a mechanical update path —
  each copy must state its source and update mechanism (banner or comment).
  An undeclared copy is a defect.
- **Mirrored pairs that cannot reference each other**
  (e.g. a self-contained prompt mirroring a schema,
  a writer composing what a guard parses)
  must both name the pairing and the authoritative side,
  and change together in one PR.
- **Review stance:** a second copy of anything without a declared source
  is a finding, same severity as dead code.

## Skills

Live in `.agents/skills/`. Synced using `npx skills update -p -y` — don't edit skill files, add repo-local overrides in AGENTS.md
1% rule: if skill might apply, load it.

**Loading:** Use platform skill tool if available, else read `.agents/skills/<name>/SKILL.md` directly.

Each table is sorted alphabetically by skill — keep it sorted when adding entries.

| Skill                    | Trigger                                                                                            |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| `caveman`                | Compact wording when writing prose (issues description, PR description, comments on repo or code)  |
| `documenting-decisions`  | Any implementation task — place `DECISION:` markers                                                |
| `domain-modeling`        | Pinning down domain terminology (glossary in `docs/glossary/`) or recording decisions in design    |
| `grill-me`               | User asks to be grilled/interviewed about a plan or design before implementation                   |
| `grill-with-docs`        | Grilling session that also records ADRs and glossary entries as decisions are made                 |
| `grilling`               | Core interview loop used by `grill-me`/`grill-with-docs`; also on any 'grill' trigger phrase       |
| `to-spec`                | Turning the current conversation into a spec/PRD and publishing it to the tracker                  |
| `writing-adrs`           | Recording an architectural decision as an ADR in `docs/adr/`, or when another skill flags one      |

Code-specific skills:

| Skill                    | Trigger                                                                                            |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| `requesting-code-review` | After completing implementation                                                                    |
| `tdd`                    | Test-driven-development for any implementation                                                     |
| `to-tickets`             | Splitting approved work into tracer-bullet issues with blocking edges (reproducible-spec rules)    |

### Repo-Local Skill Overrides

- `grilling`: present questions via the platform's native question dialog (e.g. `AskUserQuestion` in Claude Code) when the platform provides one; fall back to plain text otherwise. (The multiple-choice question format itself is part of the skill — this override only covers presentation.)

### Skill Environment Variables

- `DECISION_MEMORY_URL` — FULL git URL of the decision-memory repo the `grilling` skill records decisions to. A full URL rather than an owner/repo slug, so the hosting stays swappable. Recording requires this env var in the agent's execution environment; the recorder and the skill read exactly this name (shared contract — renaming either side breaks recording silently). Never hardcode, commit, or echo the value into artifacts. Unset → grilling still works, skips recording, and says so. Where to set it: local sessions → shell profile / user-level agent settings; remote or cloud sessions → the environment's configuration; CI → a repository secret. `scripts/doctor.sh` warns when it's unset and checks reachability when set.

  To record, use the recorder in the decision-memory repo — clone it fresh per session and run the copy that arrives with it, which operates on its own checkout:

  ```bash
  git clone "$DECISION_MEMORY_URL" <dir>
  python <dir>/tools/record.py open      # behavior doc: record.py --help
  ```

  A fresh clone is clean and on the store's default branch, which keeps a session's PR to that session's own records. Each record is pushed as it lands, so the clone is disposable.

## Git

- Branch: `<agent>/<issue-number>-<desc>` (e.g. `hermes/42-fix-auth`, `claude/42-fix-auth`)
- Never push to `main`
- Create PR immediately on branch creation
- Commits: conventional commits
- Document unexpected encounters and design decisions in commit message as well as PR/Issue

### Tracker Content Formatting

Tracker bodies (issue bodies, PR descriptions, comments) do NOT render
like committed `.md` files: APIs/sanitizers silently strip angle-bracket
tokens as HTML, and single newlines render as hard line breaks rather
than collapsing as in standard Markdown. Both silently corrupt
tracker-posted content. The rules below cover tracker-posted content
only — files committed to the repo (like this one) keep angle brackets
and follow "Prose in Repo Files" below.

Placeholder syntax:

- In ALL tracker-posted content, write placeholders with guillemets:
  `«` and `»` — e.g. `decisions/«id».json`, `«timestamp»-«slug»`.
  Never `<placeholder>` — it is stripped on programmatic reads and
  edits.
- Guillemets are for tracker-posted content ONLY. In code (source
  files, comments, error messages, help text) use plain
  `<angle-bracket>` placeholders — committed files never pass through
  a tracker sanitizer, and guillemets are alien there.

Line wrapping:

- Never hard-wrap tracker-posted markdown. Write one paragraph or list
  item per line and let the renderer wrap; a fixed-column wrap breaks
  the rendered text at random places, because each single newline
  becomes a hard break.

Repairing violations (applies to both rules):

- If an EXISTING ticket violates them, ask the user whether it should
  be fixed — don't rewrite it unprompted.
- If a violation occurs in content you are about to post anyway as a
  normal message (no explicit edit of an existing ticket needed — e.g.
  a new ticket, comment, or quoted text), fix it proactively and tell
  the user you did.

### Prose in Repo Files

Fixed-column wrapping of prose makes diffs explode:
inserting a few words into a wrapped paragraph reflows every following line,
so a one-word change renders as a whole-paragraph diff.
These rules cover prose in repo FILES (Markdown files, code comments) only;
tracker-posted content follows "Tracker Content Formatting" above.

- **Semantic line breaks for Markdown prose:** in repo `.md` files,
  break lines at sentence or clause boundaries
  (one sentence or clause per line, per the sembr convention)
  instead of wrapping at a fixed column.
  Single newlines collapse when rendered, so output is identical;
  diffs stay localized to the sentence actually edited.
  Applies to NEW or REWRITTEN prose —
  do not mass-reformat existing files just to comply.
- **Never reflow untouched lines:** when editing an existing wrapped
  paragraph (Markdown or code comments), change only the lines the edit
  actually touches, even if the block ends up ragged.
  If an insertion does not fit,
  break the line at the insertion point rather than re-justifying the
  paragraph.
- **Deliberate mass reflows** (rare) go in an isolated `style:`-type
  commit and are listed in `.git-blame-ignore-revs`.

### Agentic Engineering Workflow

Use `gh` for all repository interaction. `ghx` and `tea` are disabled — calling them tells you to use `gh` instead (enforced via shims in `scripts/agent-shims/`, on PATH in agent sessions only; tracker access through MCP tools is not gated by the shims).

#### Available `gh` verbs

- **issues:** `issue create`, `issue view` (`--comments`), `issue list`, `issue comment`, `issue edit`
- **pull requests:** `pr create`, `pr view` (`--comments`), `pr list`, `pr comment`, `pr edit`, `pr review` (`--body`, repeatable `--code-comment path:line:text`), `pr checks`, `pr status`
- **CI:** `run list`, `run view`

Use `run list` / `run view` for workflow-run detail; use `pr checks` / `pr status` for a PR's check rollup.

The modes below are the kinds of work the user will ask for. **Each runs in its own session — possibly a different model or agent** (Review especially). Follow the named skills at each step.

#### Plan

- Explore the codebase. Flag `DECISION:SCOPE` when resolving ambiguities. Use the `documenting-decisions` skill (refs: `pre-approval-gate.md`, `scope-interpretation.md`).
- Write an issue → `gh issue create`
- Set issue metadata → `gh issue edit` (labels/assignees/milestone)

#### Implement

- Read the given issue and comments → `gh issue view --comments`
- Do Test-Driven Development per the `tdd` skill.
- Implement the minimal code to pass tests, then the remaining code per the ticket spec. Place `DECISION:` markers per the `documenting-decisions` skill (refs: `decision-markers.md`, `marker-examples.md`).
- Commit discipline:
  - One test → one commit → one implementation for that test → one commit
  - `prek` must pass on every commit (lint/format hooks only — prek never runs unit tests). Enforce it, don't assume it: after **every** commit run `prek run --all-files` and require exit 0 with a clean tree — an auto-fixer modifying files counts as failure; amend the fix into the commit that introduced it (per the `tdd` skill's commit protocol). The SessionStart hook (`scripts/ensure-prek.sh`) installs the git hook so dirty commits are blocked even in fresh clones; a missing prek is a `scripts/doctor.sh --install` failure, not a license to skip.
  - TDD red-step commits are expected and required — red on **tests only**: lint, format, and type checks still pass. A test needing a not-yet-existing API surface gets a signature-only `chore(stub):` commit first (see the `tdd` skill). **CI evaluates at PR HEAD, not per-commit**, so a red-step commit does not constitute a CI failure — do not treat it as one.
  - Don't fix lint manually — run the formatter. Only touch code directly if the tools can't resolve it.
- Push → `git push` *(plain git; git is not routed through `gh`)*
- Create the PR if not already present, and link it to the issue both ways → `gh pr create` (start with `Closes #<number>` in description), then `gh issue edit` if a back-reference is needed. **If a PR already exists for this branch, do not create or re-link it** — skip to CI.
  PR body must include:
  - `Closes #<number>`.
  - Any obstacles that diverged from the initial plan, and — in the rare event spec deviation was unavoidable — what deviated and why.
  - All `DECISION:` markers present in the diff, rendered per the `documenting-decisions` skill format.
- Check CI → `gh run list` / `gh run view` (or `gh pr checks` once the PR exists).
- If CI fails, fix it by re-entering this **Implement** workflow.

#### Review

- Read the given issue and comments → `gh issue view --comments`
- Review the PR and give Critical / Important feedback per the `requesting-code-review` skill.
- Submit it as a single review → `gh pr review`:
  - PR-level summary feedback → `--body "..."`
  - Feedback tied to specific lines → repeatable `--code-comment path:line:text`
  - Put both in the same `gh pr review` call; don't split a review across `pr review` and `pr comment`.

#### Apply Review Comments

- Read the given issue and comments → `gh issue view --comments`
- Read PR comments and code comments → `gh pr view --comments`
- If the review uncovers inconsistencies in the issue, **comment** on it freely → `gh issue comment`
- Only **edit** issue content when the user explicitly requests it → `gh issue edit`. Editing is gated on explicit request because it can overwrite human-authored intent; commenting is always safe, editing is not.
- Then re-enter the **Implement** workflow.

## Commands

`make <cmd>`: `check`, `test`, `unit-test`, `lint`, `mypy`, `auto-format`, `install`, `main`, `run`, `help`

## Dependencies

Add packages using the package manager only — `uv add <package>` in this repo — never edit requirements/dependencies directly (since your knowledge cut-off prevents you from knowing the latest version of the packages).

## Documentation

- All non-trivial functions must have contracts in the function doc string
- Document all params, return shapes, and every possible error response
- Test cases must cover edge cases for inputs and every @returns line in the contract
- Non-trivial decisions or behavior should be documented via inline comments

## Failures Become Rules

When something fails that automation or an instruction could have prevented — a lint run nobody made, a tool nobody installed, a convention discovered only in review — the fix is incomplete until the prevention is encoded: a hook, a doctor check, or a rule in the template repo's AGENTS.md/skills (preferred, so every generated repo inherits it); [docs/conventions.md](docs/conventions.md) only when it is genuinely repo-local. File the ticket on the owning repo in the same session the failure surfaced. Fixing only the instance guarantees a repeat.

## Project Conventions

Repo-specific rules live in [docs/conventions.md](docs/conventions.md). Copier seeds that file once and never overwrites it — put rich local conventions there, not in this template-owned file.
