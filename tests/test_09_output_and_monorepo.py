import json
from pathlib import Path

import pytest

from pyslop.cli import main

MONO = Path(__file__).parent / "fixtures" / "monorepo"
MSG = "ast-grep/pyslop/fixture-marker Fixture marker for monorepo discovery test."


def test_excluded_file_in_pkg_b_skipped_but_pkg_a_reported(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "check",
            str(MONO / "pkg_a" / "bad.py"),
            str(MONO / "pkg_b" / "bad.py"),
            "--format",
            "json",
            "--only",
            "ast-grep",
        ]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert len(findings) == 2
    for finding in findings:
        assert finding["file"].endswith("pkg_a/bad.py")
        assert finding["engine"] == "ast-grep"
        assert finding["rule"] == "pyslop/fixture-marker"
        assert finding["severity"] == "error"
        assert set(finding) == {
            "engine",
            "rule",
            "file",
            "line",
            "col",
            "message",
            "fix_hint",
            "severity",
        }
    assert sorted(f["line"] for f in findings) == [1, 3]


def test_fully_excluded_path_exits_zero_with_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "check",
            str(MONO / "pkg_b" / "bad.py"),
            "--format",
            "json",
            "--only",
            "ast-grep",
        ]
    )
    assert json.loads(capsys.readouterr().out) == []
    assert code == 0


def test_text_output_grouped_by_file_with_summary_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "check",
            str(MONO / "pkg_a" / "bad.py"),
            str(MONO / "pkg_a" / "also_bad.py"),
            "--only",
            "ast-grep",
        ]
    )
    assert capsys.readouterr().out.splitlines() == [
        f"{MONO / 'pkg_a' / 'also_bad.py'}:1:5 {MSG}",
        f"{MONO / 'pkg_a' / 'bad.py'}:1:5 {MSG}",
        f"{MONO / 'pkg_a' / 'bad.py'}:3:5 {MSG}",
        "3 findings (3 errors)",
    ]
    assert code == 1
