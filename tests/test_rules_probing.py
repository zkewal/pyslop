import json
from pathlib import Path

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "probing"


def test_three_isinstance_branches_reported_once(capsys):
    code = main(["check", str(FIXTURES / "ladder_bad.py"), "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert len(findings) == 1
    (finding,) = findings
    assert finding["engine"] == "ast-grep"
    assert finding["rule"] == "pyslop/no-isinstance-ladder"
    assert finding["file"].endswith("ladder_bad.py")
    assert finding["line"] == 2
    assert finding["severity"] == "error"
    assert finding["message"]
    assert finding["fix_hint"]


def test_two_branches_and_mixed_subjects_pass(capsys):
    code = main(["check", str(FIXTURES / "ladder_good.py"), "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []


def test_literal_attr_names_reported_per_line(capsys):
    code = main(["check", str(FIXTURES / "attr_bad.py"), "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert sorted(f["line"] for f in findings) == [3, 4, 5, 6]
    for finding in findings:
        assert finding["engine"] == "ast-grep"
        assert finding["rule"] == "pyslop/no-dynamic-attr-on-literal"
        assert finding["file"].endswith("attr_bad.py")
        assert finding["severity"] == "error"
        assert finding["message"]
        assert finding["fix_hint"]


def test_variable_attr_names_pass(capsys):
    code = main(["check", str(FIXTURES / "attr_good.py"), "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []
