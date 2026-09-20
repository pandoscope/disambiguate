"""Usage by mention: a term the repository names anywhere is in use (#84)."""

from __future__ import annotations

from pathlib import Path

from disambiguate.glossary import Glossary


def mentioned_slugs(glossary: Glossary, repo_root: Path) -> set[str]:
    """Return the slugs of every term some file under `repo_root` mentions."""
    return set()
