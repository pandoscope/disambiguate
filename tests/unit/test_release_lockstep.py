"""Every release surface carries one version (docs/releasing.md)."""

import tomllib
from pathlib import Path

from disambiguate import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_and_module_carry_the_same_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == __version__
