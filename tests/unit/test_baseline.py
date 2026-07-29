"""Tests for disambiguate.baseline — grandfathering known drift."""

from __future__ import annotations

from pathlib import Path

from disambiguate.drift import DriftFinding


def _finding(path: Path, term: str = "widget", line: int = 1) -> DriftFinding:
    return DriftFinding(
        rule_code="unlinked-term",
        path=path,
        line=line,
        term=term,
        message="msg",
    )


def test_baseline_roundtrip_and_grandfathering(tmp_path: Path) -> None:
    from disambiguate.baseline import apply_baseline, load_baseline, save_baseline

    doc = tmp_path / "guide.md"
    baseline_path = tmp_path / ".drift-baseline.json"
    save_baseline(baseline_path, [_finding(doc)])
    baseline = load_baseline(baseline_path)
    assert baseline is not None

    fresh, stale_keys = apply_baseline([_finding(doc, line=7)], baseline)
    assert fresh == []
    assert stale_keys == []


def test_new_finding_not_in_baseline_stays_fatal(tmp_path: Path) -> None:
    from disambiguate.baseline import apply_baseline, load_baseline, save_baseline

    doc = tmp_path / "guide.md"
    other = tmp_path / "other.md"
    baseline_path = tmp_path / ".drift-baseline.json"
    save_baseline(baseline_path, [_finding(doc)])
    baseline = load_baseline(baseline_path)
    assert baseline is not None

    fresh, _ = apply_baseline([_finding(doc), _finding(other)], baseline)
    assert [f.path for f in fresh] == [other]


def test_fixed_finding_reports_stale_baseline_key(tmp_path: Path) -> None:
    from disambiguate.baseline import apply_baseline, load_baseline, save_baseline

    doc = tmp_path / "guide.md"
    baseline_path = tmp_path / ".drift-baseline.json"
    save_baseline(baseline_path, [_finding(doc)])
    baseline = load_baseline(baseline_path)
    assert baseline is not None

    fresh, stale_keys = apply_baseline([], baseline)
    assert fresh == []
    assert len(stale_keys) == 1


def test_baseline_keys_survive_line_moves(tmp_path: Path) -> None:
    from disambiguate.baseline import apply_baseline, load_baseline, save_baseline

    doc = tmp_path / "guide.md"
    baseline_path = tmp_path / ".drift-baseline.json"
    save_baseline(baseline_path, [_finding(doc, line=3)])
    baseline = load_baseline(baseline_path)
    assert baseline is not None

    fresh, stale_keys = apply_baseline([_finding(doc, line=42)], baseline)
    assert fresh == []
    assert stale_keys == []
