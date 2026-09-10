import json
from pathlib import Path

from pyslop.cli import main

EXCEPTIONS = Path(__file__).parent / "fixtures" / "exceptions"
BLANKET = Path(__file__).parent / "fixtures" / "blanket_ignore"

SWALLOWED = "pyslop/swallowed-exception"
NO_BLANKET = "pyslop/no-blanket-ignore"


def test_handlers_that_neither_raise_nor_return_are_reported(capsys):
    code = main(
        ["check", str(EXCEPTIONS / "bad.py"), "--format", "json", "--only", "ast-grep"]
    )
    findings = [
        f for f in json.loads(capsys.readouterr().out) if f["rule"] == SWALLOWED
    ]
    assert code == 1
    assert sorted(f["line"] for f in findings) == [27, 34, 42, 49, 56, 59]
    for finding in findings:
        assert finding["engine"] == "ast-grep"
        assert finding["severity"] == "error"
        assert finding["message"]
        assert finding["fix_hint"]


def test_handlers_that_reraise_or_return_exit_zero(capsys):
    code = main(
        [
            "check",
            str(EXCEPTIONS / "good.py"),
            "--format",
            "json",
            "--only",
            "ast-grep",
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_bare_ignores_are_reported_even_with_safety(capsys):
    code = main(
        ["check", str(BLANKET / "bad.py"), "--format", "json", "--only", "ast-grep"]
    )
    findings = [
        f for f in json.loads(capsys.readouterr().out) if f["rule"] == NO_BLANKET
    ]
    assert code == 1
    assert sorted(f["line"] for f in findings) == [3, 4]
    for finding in findings:
        assert finding["engine"] == "ast-grep"
        assert finding["severity"] == "error"
        assert finding["message"]
        assert finding["fix_hint"]


def test_coded_ignores_with_reasons_exit_zero(capsys):
    code = main(
        ["check", str(BLANKET / "good.py"), "--format", "json", "--only", "ast-grep"]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out) == []
