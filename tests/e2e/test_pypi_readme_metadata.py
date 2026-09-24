"""End-to-end tests: built package metadata carries absolute README links."""

from __future__ import annotations

import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

GITHUB_BLOB_PREFIX = "https://github.com/pandoscope/disambiguate/blob/main/"


def _run(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    """Run a command from the repo root and return its completed process."""
    return subprocess.run(  # noqa: S603 - commands are controlled test data.
        command,
        check=True,
        capture_output=True,
        cwd=cwd,
        text=True,
    )


def _assert_links_are_absolute(metadata: str) -> None:
    """Assert a long description carries rewritten, absolute README links."""
    assert f"({GITHUB_BLOB_PREFIX}docs/glossary/term.md)" in metadata
    assert f"({GITHUB_BLOB_PREFIX}CONTRIBUTING.md)" in metadata
    assert "](docs/" not in metadata
    assert "](CONTRIBUTING.md)" not in metadata
    assert "img.shields.io" in metadata, "badge images should survive rewriting"


def test_built_long_descriptions_use_absolute_github_links(tmp_path: Path) -> None:
    """`uv build` produces wheel METADATA and sdist PKG-INFO with absolute links."""
    _run(["uv", "build", "--out-dir", str(tmp_path)])

    [wheel] = tmp_path.glob("*.whl")
    with zipfile.ZipFile(wheel) as wheel_archive:
        [metadata_name] = [
            name
            for name in wheel_archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        _assert_links_are_absolute(wheel_archive.read(metadata_name).decode("utf-8"))

    [sdist] = tmp_path.glob("*.tar.gz")
    with tarfile.open(sdist) as sdist_archive:
        [pkg_info_name] = [
            name for name in sdist_archive.getnames() if name.endswith("/PKG-INFO")
        ]
        pkg_info_file = sdist_archive.extractfile(pkg_info_name)
        assert pkg_info_file is not None, f"unreadable member: {pkg_info_name}"
        _assert_links_are_absolute(pkg_info_file.read().decode("utf-8"))
