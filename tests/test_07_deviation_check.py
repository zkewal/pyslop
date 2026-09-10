import json
from pathlib import Path

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "deviations"
RULE = "pyslop/deviation-needs-reason"


def _check(capsys, target, *extra):
    code = main(["check", str(target), "--format", "json", *extra])
    return code, json.loads(capsys.readouterr().out)


def test_uncommented_per_file_ignore_points_at_toml_line(capsys):
    code, findings = _check(
        capsys, FIXTURES / "per_file_ignore_bad", "--only", "pyslop"
    )
    assert code == 1
    assert len(findings) == 1
    (finding,) = findings
    assert finding["engine"] == "pyslop"
    assert finding["rule"] == RULE
    assert finding["file"].endswith("pyproject.toml")
    assert "per_file_ignore_bad" in finding["file"]
    assert (finding["line"], finding["col"]) == (6, 1)
    assert finding["severity"] == "error"
    assert finding["message"]
    assert finding["fix_hint"]


def test_reasoned_per_file_ignore_passes(capsys):
    code, findings = _check(
        capsys, FIXTURES / "per_file_ignore_good", "--only", "pyslop"
    )
    assert code == 0
    assert findings == []


def test_inline_off_with_reason_suppresses_rule(capsys):
    code, findings = _check(
        capsys, FIXTURES / "rules_off" / "off_sample.py", "--only", "ast-grep"
    )
    assert code == 0
    assert findings == []
    code, findings = _check(capsys, FIXTURES / "rules_off", "--only", "pyslop")
    assert code == 0
    assert findings == []


def test_warn_downgrades_severity_without_failing(capsys):
    code, findings = _check(
        capsys, FIXTURES / "rules_warn" / "warn_sample.py", "--only", "ast-grep"
    )
    assert code == 0
    assert len(findings) == 1
    assert findings[0]["rule"] == "pyslop/no-module-mocking"
    assert findings[0]["severity"] == "warning"
    assert findings[0]["fix_hint"]


def test_unknown_pyslop_key_is_error_finding(capsys):
    code, findings = _check(capsys, FIXTURES / "unknown_key", "--only", "pyslop")
    assert code == 1
    assert len(findings) == 1
    assert findings[0]["engine"] == "pyslop"
    assert findings[0]["rule"] == RULE
    assert findings[0]["line"] == 8
    assert "stranger" in findings[0]["message"]


def test_ty_override_downgrade_without_reason_is_flagged(capsys):
    code, findings = _check(capsys, FIXTURES / "ty_override_bad", "--only", "pyslop")
    assert code == 1
    assert len(findings) == 1
    assert findings[0]["rule"] == RULE
    assert findings[0]["line"] == 7
    assert "unresolved-import" in findings[0]["message"]


def test_reasoned_ty_override_passes(capsys):
    code, findings = _check(capsys, FIXTURES / "ty_override_good", "--only", "pyslop")
    assert code == 0
    assert findings == []


def test_excluded_path_is_silent_and_kept_path_reports(capsys):
    code, findings = _check(
        capsys, FIXTURES / "exclude" / "gen" / "dirty.py", "--only", "ast-grep"
    )
    assert code == 0
    assert findings == []
    code, findings = _check(
        capsys, FIXTURES / "exclude" / "kept.py", "--only", "ast-grep"
    )
    assert code == 1
    assert len(findings) == 1
    assert findings[0]["rule"] == "pyslop/swallowed-exception"
    assert findings[0]["line"] == 7
