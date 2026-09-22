"""The release workflow: a merged version bump is the release (docs/releasing.md)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
RELEASE_WORKFLOW = WORKFLOWS / "release.yml"


def test_release_runs_on_pushes_to_main_only() -> None:
    """A version bump merged to main is the trigger; tags trigger nothing."""
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "branches: [main]" in workflow
    assert "tags:" not in workflow
    assert "workflow_run" not in workflow


def test_gate_skips_a_version_that_is_already_tagged() -> None:
    """The gate compares pyproject's version against the pushed tags."""
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert '["project"]["version"]' in workflow
    assert 'git ls-remote --exit-code --tags origin "refs/tags/v$version"' in workflow
    assert "publish=false" in workflow


def test_nothing_pushes_to_main() -> None:
    """No bot commit ever meets the main rulesets (meta#155)."""
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "git push" not in workflow
    assert "semantic-release" not in workflow
    assert "create-github-app-token" not in workflow


def test_pypi_job_publishes_through_the_gated_environment_with_oidc() -> None:
    """The upload waits for the pypi environment's reviewers and uses OIDC."""
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "environment: pypi" in workflow
    assert "id-token: write" in workflow
    assert "uv publish --check-url https://pypi.org/simple/disambiguate/" in workflow


def test_release_job_builds_the_bundle_before_creating_the_release() -> None:
    """The GitHub release carries the wheel, the sdist and the Claude bundle."""
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    bundle_index = workflow.index("claude-bundle.zip")
    release_index = workflow.index("gh release create")

    assert bundle_index < release_index
    assert "--generate-notes" in workflow
    assert "dist/*.whl" in workflow
    assert "dist/*.tar.gz" in workflow


def test_semantic_release_is_gone() -> None:
    """No config, no changelog, no separate publish workflow remain."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "semantic_release" not in pyproject
    assert "python-semantic-release" not in pyproject
    assert not (ROOT / "CHANGELOG.md").exists()
    assert not (WORKFLOWS / "publish.yml").exists()


def test_release_job_provisions_python_before_building_the_bundle() -> None:
    """
    The release job sets Python 3.12 up before the bundle build.

    The bundle script calls `python3.12 -m pip download`; the runner image
    guarantees neither (spec-fidelity review of pr87).
    """
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    release_job = workflow[workflow.index("  release:") :]

    setup_index = release_job.index("actions/setup-python")
    bundle_index = release_job.index("claude-bundle.zip")

    assert setup_index < bundle_index
    assert 'python-version: "3.12"' in release_job[setup_index:bundle_index]
