import json
from pathlib import Path

import pytest

from pyslop.cli import _exclude_spec, _is_excluded, main

MONO = Path(__file__).parent / "fixtures" / "monorepo"
MSG = "pyslop/fixture-marker Fixture marker for monorepo discovery test."


@pytest.fixture(autouse=True)
def _repo_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    # Findings show paths relative to the working dir; pin it so the
    # expected lines below are literal.
    monkeypatch.chdir(Path(__file__).parent.parent)


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
        f"tests/fixtures/monorepo/pkg_a/also_bad.py:1:5 {MSG}",
        f"tests/fixtures/monorepo/pkg_a/bad.py:1:5 {MSG}",
        f"tests/fixtures/monorepo/pkg_a/bad.py:3:5 {MSG}",
        "3 findings (3 errors)",
    ]
    assert code == 1


def test_exclude_glob_matrix() -> None:
    cases = [
        # (relative path, patterns, excluded)
        ("src/app/b.py", ["src/**"], True),  # recursive trailing **
        ("src/b.py", ["src/**"], True),
        ("tests/x/test_y.py", ["tests/**"], True),
        ("other/a.py", ["src/**"], False),  # sibling nonmatch
        ("src.py", ["src/**"], False),  # prefix without separator
        ("pkg_b/bad.py", ["bad.py"], True),  # basename matches at depth
        ("a/b/c.py", ["**/*.py"], True),
        ("top.py", ["*.py"], True),  # root-level file
        ("a/top.py", ["*.py"], True),  # basename matches at depth
        ("x/a/b.py", ["a/b.py"], False),  # slashed patterns anchor at root
        ("gen/deep/dirty.py", ["gen/**", "!gen/keep.py"], True),
        ("gen/keep.py", ["gen/**", "!gen/keep.py"], False),  # ! reincludes
        ("a/b.py", ["a/c.py"], False),
        ("a/b.py", [], False),
    ]
    for rel, patterns, excluded in cases:
        spec = _exclude_spec(Path(), patterns)
        assert _is_excluded(rel, spec) is excluded, (rel, patterns)


def test_bad_exclude_glob_is_loud_and_excludes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _exclude_spec(tmp_path, ["!"]) is None
    assert "bad exclude glob" in capsys.readouterr().err
    assert _is_excluded("anything.py", None) is False


def test_nested_exclude_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture-exclude"\nversion = "0.0.0"\n'
        '\n[tool.pyslop]\nexclude = ["gen/**", "!gen/keep.py"]\n'
    )
    nested = tmp_path / "gen" / "deep"
    nested.mkdir(parents=True)
    dirty = 'def lookup(obj: object) -> bool:\n    return hasattr(obj, "name")\n'
    (nested / "dirty.py").write_text(dirty)
    keep = tmp_path / "keep.py"
    keep.write_text(dirty)
    reincluded = tmp_path / "gen" / "keep.py"
    reincluded.write_text(dirty)
    code = main(
        [
            "check",
            str(nested / "dirty.py"),
            str(keep),
            str(reincluded),
            "--format",
            "json",
            "--only",
            "ast-grep",
        ]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert sorted(f["file"] for f in findings) == sorted([str(keep), str(reincluded)])


def test_bad_exclude_glob_end_to_end_excludes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\nversion = "0"\n\n[tool.pyslop]\nexclude = ["!"]\n'
    )
    target = tmp_path / "a.py"
    target.write_text('def f(obj: object) -> bool:\n    return hasattr(obj, "x")\n')
    code = main(["check", str(target), "--format", "json", "--only", "ast-grep"])
    captured = capsys.readouterr()
    assert code == 1
    assert [f["file"] for f in json.loads(captured.out)] == [str(target)]
    assert "bad exclude glob" in captured.err
