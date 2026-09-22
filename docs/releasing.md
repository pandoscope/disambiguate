# Releasing

A release is a version bump merged to `main`. The `Release` workflow
(`.github/workflows/release.yml`) then publishes automatically:

1. **version gate** — reads `project.version` from `pyproject.toml`,
   re-verifies that `src/disambiguate/__init__.py` carries the same
   version (the lockstep test guards this on every PR), and skips
   everything when the tag `v<version>` already exists.
2. **publish to PyPI** — `uv build && uv publish` via PyPI trusted
   publishing, in the `pypi` environment, whose required reviewers
   hold the upload until a human approves.
3. **tag + GitHub release** — `gh release create v<version>` with
   generated notes, the wheel, the sdist and the Claude bundle.

Nothing pushes to `main`. The version bump arrives through a pull
request like any other change, so the org's rulesets apply to it in
full.

## Bumping

In one pull request: set `project.version` in `pyproject.toml` and
`__version__` in `src/disambiguate/__init__.py` to the new version,
run `uv lock` so the lockfile carries it, and merge. Conventional
commits decide the number by hand: a `feat` bumps minor, a `fix`
bumps patch, a breaking change bumps major.

## One-time registry configuration (principal)

PyPI authenticates the workflow itself via OIDC. The trusted publisher
on <https://pypi.org/manage/project/disambiguate/settings/publishing/>
names owner `pandoscope`, repository `disambiguate`, workflow
`release.yml`, environment `pypi`. The `pypi` environment's deployment
rule must allow the `main` branch, since the publish job runs before
the tag exists.
