"""Tests for the build-time PyPI readme link rewriting configuration."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

GITHUB_BLOB_PREFIX = "https://github.com/pandoscope/disambiguate/blob/main/"


def _pyproject() -> dict[str, Any]:
    """Return the parsed pyproject.toml."""
    parsed: dict[str, Any] = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    return parsed


def _readme_hook_config() -> dict[str, Any]:
    """Return the hatch-fancy-pypi-readme metadata hook config."""
    hooks = (
        _pyproject()
        .get("tool", {})
        .get("hatch", {})
        .get("metadata", {})
        .get("hooks", {})
    )
    config: dict[str, Any] | None = hooks.get("fancy-pypi-readme")
    assert config is not None, "hatch-fancy-pypi-readme metadata hook not configured"
    return config


def _apply_substitutions(text: str) -> str:
    """Apply the configured substitutions the way hatch-fancy-pypi-readme does."""
    for substitution in _readme_hook_config()["substitutions"]:
        text = re.sub(substitution["pattern"], substitution["replacement"], text)
    return text


def test_readme_is_declared_dynamic() -> None:
    project = _pyproject()["project"]
    assert "readme" in project.get("dynamic", [])
    assert "readme" not in project


def test_build_requires_fancy_pypi_readme() -> None:
    requires = _pyproject()["build-system"]["requires"]
    assert any(
        requirement.startswith("hatch-fancy-pypi-readme") for requirement in requires
    ), f"hatch-fancy-pypi-readme missing from build-system requires: {requires}"


def test_hook_sources_readme_as_markdown() -> None:
    config = _readme_hook_config()
    assert config["content-type"] == "text/markdown"
    assert [fragment["path"] for fragment in config["fragments"]] == ["README.md"]


def test_relative_readme_links_are_rewritten_to_absolute() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    rewritten = _apply_substitutions(readme)
    assert f"({GITHUB_BLOB_PREFIX}docs/glossary/term.md)" in rewritten
    assert f"({GITHUB_BLOB_PREFIX}CONTRIBUTING.md)" in rewritten
    assert "](docs/" not in rewritten
    assert "](CONTRIBUTING.md)" not in rewritten


def test_absolute_urls_in_readme_are_untouched() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    rewritten = _apply_substitutions(readme)
    assert GITHUB_BLOB_PREFIX + "http" not in rewritten
    absolute_urls = re.findall(r"https?://\S+", readme)
    for url in absolute_urls:
        assert url in rewritten, f"absolute URL was mangled: {url}"


def test_badge_image_targets_are_untouched() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    badge_urls = re.findall(r'<img src="([^"]+)"', readme)
    assert badge_urls, "expected badge images in README.md"
    rewritten = _apply_substitutions(readme)
    for url in badge_urls:
        assert f'<img src="{url}"' in rewritten, f"badge image was mangled: {url}"


def test_relative_markdown_link_is_rewritten() -> None:
    rewritten = _apply_substitutions("See [the term](docs/glossary/term.md) here.")
    assert (
        rewritten == f"See [the term]({GITHUB_BLOB_PREFIX}docs/glossary/term.md) here."
    )


def test_absolute_markdown_link_is_untouched() -> None:
    text = "See [example](https://example.com/docs/page.md) here."
    assert _apply_substitutions(text) == text


def test_anchor_link_is_untouched() -> None:
    text = "Jump to [usage](#usage)."
    assert _apply_substitutions(text) == text


def test_mailto_link_is_untouched() -> None:
    text = "Contact [us](mailto:creator@frankify.app)."
    assert _apply_substitutions(text) == text
