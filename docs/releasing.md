# Releasing

A release is a version bump merged to `main`. The `Release` workflow
(`.github/workflows/release.yml`) then publishes:

1. **version gate** reads `project.version` from `pyproject.toml`.
   It verifies that `src/disambiguate/__init__.py` carries the same
   version (the lockstep test guards this on every PR).
   It skips everything when the tag `v<version>` already exists.
2. **publish to PyPI** runs `uv build && uv publish` through PyPI
   trusted publishing in the `pypi` environment. Required reviewers of
   that environment hold the upload until a human approves.
3. **tag + GitHub release** runs `gh release create v<version>` with
   generated notes, the wheel, the sdist and the Claude bundle.

Nothing pushes to `main`. The version bump arrives through a pull
request like any other change, so the [org](glossary/org.md)'s rulesets
apply to it in full.

## Bumping

In one pull request: set `project.version` in `pyproject.toml` and
`__version__` in `src/disambiguate/__init__.py` to the new version.
Run `uv lock` so the lockfile carries it. Merge.
Conventional commits decide the number by hand: `feat` bumps minor,
`fix` bumps patch, a breaking change bumps major.

## One-time registry configuration (principal)

PyPI authenticates the workflow itself through OIDC. The trusted
publisher on <https://pypi.org/manage/project/disambiguate/settings/publishing/>
names owner `pandoscope`, repository
[disambiguate](glossary/disambiguate.md), workflow `release.yml`,
environment `pypi`. The deployment rule of the `pypi` environment must
allow the `main` branch: the publish job runs before the tag exists.
