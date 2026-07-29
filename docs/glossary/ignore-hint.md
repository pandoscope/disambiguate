## Ignore-hint

An author annotation that suppresses a [drift](drift.md) finding at a
location. Hints live in HTML comments, invisible in rendered markdown, and
carry the [rule-code](rule-code.md) they silence. Three surfaces exist,
coarsest first:

- config-level: a `drift-ignore` list under `[tool.disambiguate]` in
  `pyproject.toml` disables a rule-code repo-wide; `drift-ignore-paths`
  scopes it to path globs.
- file-level: `<!-- d10e: ignore-file[unlinked-term] -->` anywhere in a
  document disables the rule-code for the whole file.
- inline: `<!-- d10e: ignore[unlinked-term] widget -->` on the finding's
  line or the line directly above silences that finding only.

The hint keyword `d10e` is a numeronym of `disambiguate`, which is
accepted as a long-form alias. Precedence is config, then file, then
inline — the coarsest matching suppression wins.

A suppression that matches no finding is itself reported as a fatal
`stale-suppression` finding, keeping the ignore-set honest. Stale
detection is shadowing-aware: an inline hint that matches nothing but sits
under a file-level or config suppression of the same rule-code is not
reported stale.
