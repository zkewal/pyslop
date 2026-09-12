import io
import json
import sys
from pathlib import Path

import pytest

from pyslop.cli import main

MONO = Path(__file__).parent / "fixtures" / "monorepo"
TITLE = "ast-grep (pyslop/fixture-marker)"
MSG = "Fixture marker for monorepo discovery test."
CHECK_ARGV = [
    "check",
    str(MONO / "pkg_a" / "bad.py"),
    str(MONO / "pkg_a" / "also_bad.py"),
    "--only",
    "ast-grep",
]
EXPECTED = [
    f"::error file={MONO}/pkg_a/also_bad.py,line=1,col=5,title={TITLE}::{MSG}",
    f"::error file={MONO}/pkg_a/bad.py,line=1,col=5,title={TITLE}::{MSG}",
    f"::error file={MONO}/pkg_a/bad.py,line=3,col=5,title={TITLE}::{MSG}",
]


def _render(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload: str,
    args: list[str],
) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    code = main(["render", *args])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_check_github_errors_exact_lines_and_exit_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main([*CHECK_ARGV, "--format", "github"])
    out = capsys.readouterr().out
    assert out.splitlines() == EXPECTED
    assert "findings" not in out
    assert code == 1


def test_check_github_clean_is_empty_and_exit_0(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "check",
            str(MONO / "pkg_b" / "bad.py"),
            "--format",
            "github",
            "--only",
            "ast-grep",
        ]
    )
    assert capsys.readouterr().out == ""
    assert code == 0


def test_render_warning_and_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    warning = [
        {
            "engine": "ty",
            "rule": "ty/unresolved-import",
            "file": "pkg_a/bad.py",
            "line": 2,
            "col": 1,
            "message": "Cannot find import",
            "fix_hint": "",
            "severity": "warning",
        }
    ]
    code, out, _ = _render(
        monkeypatch, capsys, json.dumps(warning), ["--format", "github"]
    )
    assert out.splitlines() == [
        (
            "::warning file=pkg_a/bad.py,line=2,col=1,"
            "title=ty (ty/unresolved-import)::Cannot find import"
        )
    ]
    assert code == 0
    code, out, _ = _render(monkeypatch, capsys, "[]", ["--format", "github"])
    assert out == ""
    assert code == 0


def test_render_escaping_matrix(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = [
        {
            "engine": "ty",
            "rule": "pyslop/x:y,z%w",
            "file": "src/a:b,c%d.py",
            "line": 7,
            "col": 9,
            "message": "100% done\nnext\r\nline: ok, fine",
            "fix_hint": "",
            "severity": "warning",
        }
    ]
    code, out, _ = _render(
        monkeypatch, capsys, json.dumps(payload), ["--format", "github"]
    )
    assert out.splitlines() == [
        (
            "::warning file=src/a%3Ab%2Cc%25d.py,line=7,col=9,"
            "title=ty (pyslop/x%3Ay%2Cz%25w)::100%25 done%0Anext%0D%0Aline: ok, fine"
        )
    ]
    assert code == 0


def test_render_error_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = [
        {
            "engine": "ast-grep",
            "rule": "pyslop/fixture-marker",
            "file": "pkg_a/bad.py",
            "line": 1,
            "col": 5,
            "message": MSG,
            "fix_hint": "",
            "severity": "error",
        }
    ]
    code, out, _ = _render(
        monkeypatch, capsys, json.dumps(payload), ["--format", "github"]
    )
    assert out.splitlines() == [
        f"::error file=pkg_a/bad.py,line=1,col=5,title={TITLE}::{MSG}"
    ]
    assert code == 1


def test_render_rejects_bad_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = [
        "not json",
        "",
        '{"engine": "ast-grep"}',
        "[42]",
        '[{"engine": "ast-grep"}]',
        json.dumps(
            [
                {
                    "engine": "ast-grep",
                    "rule": "pyslop/fixture-marker",
                    "file": "pkg_a/bad.py",
                    "line": "1",
                    "col": 5,
                    "message": MSG,
                    "fix_hint": "",
                    "severity": "error",
                }
            ]
        ),
        json.dumps(
            [
                {
                    "engine": "ast-grep",
                    "rule": "pyslop/fixture-marker",
                    "file": "pkg_a/bad.py",
                    "line": True,
                    "col": 5,
                    "message": MSG,
                    "fix_hint": "",
                    "severity": "error",
                }
            ]
        ),
    ]
    for payload in bad:
        code, out, err = _render(monkeypatch, capsys, payload, ["--format", "github"])
        assert code == 2
        assert out == ""
        assert "render" in err


def test_check_render_equivalence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main([*CHECK_ARGV, "--format", "json"])
    assert code == 1
    produced = capsys.readouterr().out
    code = main([*CHECK_ARGV, "--format", "github"])
    assert code == 1
    direct = capsys.readouterr().out
    code, rendered, _ = _render(monkeypatch, capsys, produced, ["--format", "github"])
    assert code == 1
    assert rendered == direct
    assert rendered.splitlines() == EXPECTED
