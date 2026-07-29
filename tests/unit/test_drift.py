"""Tests for disambiguate.drift — the drift-check engine."""

from __future__ import annotations

from pathlib import Path

from disambiguate.drift import run_drift_checks
from disambiguate.glossary import load_glossary


def _write(directory: Path, name: str, body: str) -> Path:
    path = directory / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    return path


def _setup_glossary(tmp_path: Path) -> Path:
    glossary_dir = tmp_path / "glossary"
    glossary_dir.mkdir()
    return glossary_dir


def test_unlinked_mention_produces_one_finding(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    root = _write(
        tmp_path,
        "README",
        "[w](glossary/widget.md)\n",
    )
    doc = _write(
        tmp_path,
        "guide",
        "The widget spins. Later the widget stops.\n",
    )
    root.write_text(
        "[w](glossary/widget.md) [guide](guide.md)\n",
        encoding="utf-8",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    unlinked = [f for f in findings if f.rule_code == "unlinked-term"]
    assert len(unlinked) == 1
    assert unlinked[0].term == "widget"
    assert unlinked[0].path == doc
    assert unlinked[0].line == 1


def test_linked_once_silences_later_plain_mentions(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    root = _write(
        tmp_path,
        "README",
        "A [widget](glossary/widget.md) spins. Later the widget stops.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_mention_inside_inline_code_span_is_not_drift(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    root = _write(
        tmp_path,
        "README",
        "[w](glossary/widget.md) [g](guide.md)\n",
    )
    _write(tmp_path, "guide", "Run the `widget` command.\n")
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_mention_inside_code_fence_is_not_drift(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    root = _write(
        tmp_path,
        "README",
        "[w](glossary/widget.md) [g](guide.md)\n",
    )
    _write(tmp_path, "guide", "Example:\n\n```\nwidget --help\n```\n")
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_mention_inside_markdown_link_display_text_is_not_drift(
    tmp_path: Path,
) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    root = _write(
        tmp_path,
        "README",
        "[w](glossary/widget.md) [g](guide.md)\n",
    )
    _write(tmp_path, "guide", "See the [widget docs](https://example.com).\n")
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_mention_inside_wikilink_display_text_is_not_drift(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    _write(glossary_dir, "factory", "## Factory\n\nA factory.\n")
    root = _write(
        tmp_path,
        "README",
        "[w](glossary/widget.md) [f](glossary/factory.md) [g](guide.md)\n",
    )
    _write(tmp_path, "guide", "See [[factory|the widget factory]].\n")
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_matching_is_case_insensitive(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    root = _write(tmp_path, "README", "[w](glossary/widget.md) [g](guide.md)\n")
    _write(tmp_path, "guide", "The WIDGET spins.\n")
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f.term for f in findings if f.rule_code == "unlinked-term"] == ["widget"]


def test_matching_is_word_boundaried(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    root = _write(tmp_path, "README", "[w](glossary/widget.md) [g](guide.md)\n")
    _write(tmp_path, "guide", "Many widgets and midwidget things.\n")
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_compound_term_mention_is_not_a_mention_of_its_parts(tmp_path: Path) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    _write(glossary_dir, "widget-factory", "## Widget factory\n\n[[widget]] maker.\n")
    root = _write(
        tmp_path,
        "README",
        "[w](glossary/widget.md) [wf](glossary/widget-factory.md) [g](guide.md)\n",
    )
    _write(
        tmp_path,
        "guide",
        "A [widget-factory](glossary/widget-factory.md) runs; "
        "the widget-factory hums.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def _widget_project(tmp_path: Path, guide_text: str) -> tuple[Path, Path]:
    """Glossary with `widget` + README root linking guide.md with `guide_text`."""
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    root = _write(tmp_path, "README", "[w](glossary/widget.md) [g](guide.md)\n")
    _write(tmp_path, "guide", guide_text)
    return glossary_dir, root


def test_inline_ignore_hint_on_same_line_silences_finding(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "The widget spins. <!-- d10e: ignore[unlinked-term] widget -->\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_inline_ignore_hint_on_line_above_silences_finding(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "<!-- d10e: ignore[unlinked-term] widget -->\nThe widget spins.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_inline_ignore_hint_far_away_does_not_silence(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "The widget spins.\n\n\nText.\n<!-- d10e: ignore[unlinked-term] widget -->\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f.term for f in findings if f.rule_code == "unlinked-term"] == ["widget"]


def test_file_level_opt_out_silences_rule_across_file(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "<!-- d10e: ignore-file[unlinked-term] -->\n\nText.\n\nThe widget spins.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_long_form_disambiguate_keyword_is_accepted(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "The widget spins. <!-- disambiguate: ignore[unlinked-term] widget -->\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_config_ignore_silences_rule_repo_wide(tmp_path: Path) -> None:
    from disambiguate.suppressions import DriftConfig

    glossary_dir, root = _widget_project(tmp_path, "The widget spins.\n")
    glossary = load_glossary(glossary_dir)
    config = DriftConfig(ignore=["unlinked-term"], ignore_paths={})
    findings = run_drift_checks(glossary, roots=[root], config=config)
    assert [f for f in findings if f.rule_code == "unlinked-term"] == []


def test_config_ignore_paths_scopes_by_glob(tmp_path: Path) -> None:
    from disambiguate.suppressions import DriftConfig

    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "widget", "## Widget\n\nA widget.\n")
    root = _write(
        tmp_path,
        "README",
        "[w](glossary/widget.md) [g](guide.md) [o](other.md)\n",
    )
    _write(tmp_path, "guide", "The widget spins.\n")
    _write(tmp_path, "other", "The widget hums.\n")
    glossary = load_glossary(glossary_dir)
    config = DriftConfig(
        ignore=[],
        ignore_paths={"guide.md": ["unlinked-term"]},
        root=tmp_path,
    )
    findings = run_drift_checks(glossary, roots=[root], config=config)
    flagged = sorted(f.path.name for f in findings if f.rule_code == "unlinked-term")
    assert flagged == ["other.md"]


def test_load_drift_config_reads_pyproject(tmp_path: Path) -> None:
    from disambiguate.suppressions import load_drift_config

    (tmp_path / "pyproject.toml").write_text(
        "[tool.disambiguate]\n"
        'drift-ignore = ["unlinked-term"]\n'
        "[tool.disambiguate.drift-ignore-paths]\n"
        '"docs/*.md" = ["term-case"]\n',
        encoding="utf-8",
    )
    config = load_drift_config(tmp_path)
    assert config is not None
    assert config.ignore == ["unlinked-term"]
    assert config.ignore_paths == {"docs/*.md": ["term-case"]}


def test_stale_inline_hint_is_fatal_finding(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "All [widget](glossary/widget.md) uses linked.\n"
        "<!-- d10e: ignore[unlinked-term] widget -->\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    stale = [f for f in findings if f.rule_code == "stale-suppression"]
    assert len(stale) == 1
    assert stale[0].line == 2


def test_stale_file_opt_out_is_fatal_finding(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "<!-- d10e: ignore-file[unlinked-term] -->\nNothing drifting here.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f.rule_code for f in findings] == ["stale-suppression"]


def test_stale_config_ignore_is_fatal_finding(tmp_path: Path) -> None:
    from disambiguate.suppressions import DriftConfig

    glossary_dir, root = _widget_project(
        tmp_path,
        "All [widget](glossary/widget.md) uses linked.\n",
    )
    glossary = load_glossary(glossary_dir)
    config = DriftConfig(ignore=["unlinked-term"], ignore_paths={}, root=tmp_path)
    findings = run_drift_checks(glossary, roots=[root], config=config)
    assert [f.rule_code for f in findings] == ["stale-suppression"]


def test_inline_hint_shadowed_by_file_opt_out_is_not_stale(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "<!-- d10e: ignore-file[unlinked-term] -->\n"
        "The widget spins.\n"
        "Fixed prose, hint below now points at nothing.\n"
        "<!-- d10e: ignore[unlinked-term] widget -->\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "stale-suppression"] == []


def test_inline_hint_shadowed_by_config_is_not_stale(tmp_path: Path) -> None:
    from disambiguate.suppressions import DriftConfig

    glossary_dir, root = _widget_project(
        tmp_path,
        "The widget spins.\n"
        "Fixed prose, hint below now points at nothing.\n"
        "<!-- d10e: ignore[unlinked-term] widget -->\n",
    )
    glossary = load_glossary(glossary_dir)
    config = DriftConfig(ignore=["unlinked-term"], ignore_paths={}, root=tmp_path)
    findings = run_drift_checks(glossary, roots=[root], config=config)
    assert findings == []


def _aliased_project(tmp_path: Path, guide_text: str) -> tuple[Path, Path]:
    """Glossary where `widget` forbids the synonym `gadget`."""
    glossary_dir = _setup_glossary(tmp_path)
    _write(
        glossary_dir,
        "widget",
        "## Widget\n\nA widget.\n\n_Avoid_: gadget, doohickey\n",
    )
    root = _write(tmp_path, "README", "[w](glossary/widget.md) [g](guide.md)\n")
    _write(tmp_path, "guide", guide_text)
    return glossary_dir, root


def test_avoided_term_use_produces_wrong_alias_finding(tmp_path: Path) -> None:
    glossary_dir, root = _aliased_project(
        tmp_path,
        "See the [widget](glossary/widget.md). The gadget spins.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    wrong = [f for f in findings if f.rule_code == "wrong-alias"]
    assert len(wrong) == 1
    assert wrong[0].term == "widget"
    assert "gadget" in wrong[0].message
    assert "widget" in wrong[0].message


def test_avoided_term_in_code_or_link_is_not_drift(tmp_path: Path) -> None:
    glossary_dir, root = _aliased_project(
        tmp_path,
        "See the [widget](glossary/widget.md). Run `gadget --help` and\n"
        "read the [gadget docs](https://example.com).\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "wrong-alias"] == []


def test_wrong_alias_is_suppressible_inline(tmp_path: Path) -> None:
    glossary_dir, root = _aliased_project(
        tmp_path,
        "See the [widget](glossary/widget.md).\n"
        "The gadget spins. <!-- d10e: ignore[wrong-alias] widget -->\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "wrong-alias"] == []


def test_wrong_alias_is_suppressible_via_file_and_config(tmp_path: Path) -> None:
    from disambiguate.suppressions import DriftConfig

    glossary_dir, root = _aliased_project(
        tmp_path,
        "<!-- d10e: ignore-file[wrong-alias] -->\n"
        "See the [widget](glossary/widget.md). The gadget spins.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "wrong-alias"] == []

    config = DriftConfig(ignore=["wrong-alias"], ignore_paths={}, root=tmp_path)
    findings = run_drift_checks(glossary, roots=[root], config=config)
    assert [f for f in findings if f.rule_code == "wrong-alias"] == []


def test_wrong_alias_participates_in_baseline(tmp_path: Path) -> None:
    from disambiguate.baseline import apply_baseline, load_baseline, save_baseline

    glossary_dir, root = _aliased_project(
        tmp_path,
        "See the [widget](glossary/widget.md). The gadget spins.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f.rule_code for f in findings] == ["wrong-alias"]

    baseline_path = tmp_path / ".drift-baseline.json"
    save_baseline(baseline_path, findings)
    baseline = load_baseline(baseline_path)
    assert baseline is not None
    fresh, stale_keys = apply_baseline(findings, baseline)
    assert fresh == []
    assert stale_keys == []


def test_common_noun_title_cased_mid_sentence_is_term_case_drift(
    tmp_path: Path,
) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "See the [widget](glossary/widget.md). Then the Widget spins.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    case = [f for f in findings if f.rule_code == "term-case"]
    assert len(case) == 1
    assert case[0].term == "widget"
    assert "Widget" in case[0].message


def test_sentence_initial_capital_is_not_term_case_drift(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "See the [widget](glossary/widget.md). Widget spins here.\n"
        "Widget also starts this line.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "term-case"] == []


def test_proper_noun_lowercased_mid_sentence_is_term_case_drift(
    tmp_path: Path,
) -> None:
    glossary_dir = _setup_glossary(tmp_path)
    _write(glossary_dir, "github", "## GitHub\n\nThe forge.\n")
    root = _write(
        tmp_path,
        "README",
        "See [GitHub](glossary/github.md). Hosted on github today.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    case = [f for f in findings if f.rule_code == "term-case"]
    assert len(case) == 1
    assert case[0].term == "github"


def test_correct_casing_produces_no_term_case_finding(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "See the [widget](glossary/widget.md). Then the widget spins.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "term-case"] == []


def test_term_case_skips_code_and_links(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "See the [widget](glossary/widget.md). Run `the Widget` and read\n"
        "the [Widget guide](https://example.com).\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "term-case"] == []


def test_term_case_is_suppressible_and_baselined(tmp_path: Path) -> None:
    from disambiguate.baseline import apply_baseline, load_baseline, save_baseline
    from disambiguate.suppressions import DriftConfig

    glossary_dir, root = _widget_project(
        tmp_path,
        "<!-- d10e: ignore[term-case] widget -->\n"
        "See the [widget](glossary/widget.md). Then the Widget spins.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f for f in findings if f.rule_code == "term-case"] == []

    hintless = tmp_path / "guide.md"
    hintless.write_text(
        "See the [widget](glossary/widget.md). Then the Widget spins.\n",
        encoding="utf-8",
    )
    config = DriftConfig(ignore=["term-case"], ignore_paths={}, root=tmp_path)
    findings = run_drift_checks(glossary, roots=[root], config=config)
    assert [f for f in findings if f.rule_code == "term-case"] == []

    findings = run_drift_checks(glossary, roots=[root])
    assert [f.rule_code for f in findings] == ["term-case"]
    baseline_path = tmp_path / ".drift-baseline.json"
    save_baseline(baseline_path, findings)
    baseline = load_baseline(baseline_path)
    assert baseline is not None
    fresh, _ = apply_baseline(findings, baseline)
    assert fresh == []


def test_hint_examples_inside_code_are_not_live_hints(tmp_path: Path) -> None:
    glossary_dir, root = _widget_project(
        tmp_path,
        "Document hints like `<!-- d10e: ignore-file[unlinked-term] -->` or\n"
        "`<!-- d10e: ignore[unlinked-term] widget -->` in prose.\n"
        "The widget spins unlinked.\n",
    )
    glossary = load_glossary(glossary_dir)
    findings = run_drift_checks(glossary, roots=[root])
    assert [f.rule_code for f in findings] == ["unlinked-term"]
