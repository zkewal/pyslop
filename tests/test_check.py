import json
from pathlib import Path

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "safety"


def test_bad_file_lists_one_finding_per_unjustified_hatch(capsys):
    code = main(
        ["check", str(FIXTURES / "bad.py"), "--format", "json", "--only", "ast-grep"]
    )
    findings = [
        f
        for f in json.loads(capsys.readouterr().out)
        if f["rule"] == "pyslop/require-safety-comment"
    ]
    assert code == 1
    assert sorted(f["line"] for f in findings) == [3, 4, 5, 6, 7, 10]
    for finding in findings:
        assert finding["engine"] == "ast-grep"
        assert finding["rule"] == "pyslop/require-safety-comment"
        assert finding["file"].endswith("bad.py")
        assert finding["severity"] == "error"
        assert finding["message"]
        assert finding["fix_hint"]


def test_good_file_exits_zero_with_empty_list(capsys):
    code = main(
        [
            "check",
            str(FIXTURES / "good.py"),
            "--format",
            "json",
            "--only",
            "ast-grep",
        ]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []
