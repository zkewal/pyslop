import json
from pathlib import Path

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "signatures"


def _findings_for(capsys, filename, rule):
    code = main(
        ["check", str(FIXTURES / filename), "--format", "json", "--only", "ast-grep"]
    )
    findings = json.loads(capsys.readouterr().out)
    return code, [f for f in findings if f["rule"] == rule]


def test_kwargs_bad_flags_public_untyped_kwargs(capsys):
    code, kwargs = _findings_for(
        capsys, "kwargs_bad.py", "pyslop/no-kwargs-passthrough"
    )
    assert code == 1
    assert sorted(f["line"] for f in kwargs) == [1, 5, 9]
    for finding in kwargs:
        assert finding["engine"] == "ast-grep"
        assert finding["severity"] == "error"
        assert finding["message"]
        assert finding["fix_hint"]


def test_kwargs_good_allows_unpack_and_private(capsys):
    code, kwargs = _findings_for(
        capsys, "kwargs_good.py", "pyslop/no-kwargs-passthrough"
    )
    assert kwargs == []
    assert code == 0


def test_dict_any_bad_flags_signature_any(capsys):
    code, dict_any = _findings_for(capsys, "dict_any_bad.py", "pyslop/no-dict-any")
    assert code == 1
    assert sorted(f["line"] for f in dict_any) == [5, 9, 13]
    for finding in dict_any:
        assert finding["engine"] == "ast-grep"
        assert finding["severity"] == "error"
        assert finding["message"]
        assert finding["fix_hint"]


def test_dict_any_good_allows_locals_and_typed_values(capsys):
    code, dict_any = _findings_for(capsys, "dict_any_good.py", "pyslop/no-dict-any")
    assert dict_any == []
    assert code == 0


def test_mocking_bad_flags_dotted_string_targets(capsys):
    code, mocking = _findings_for(capsys, "mocking_bad.py", "pyslop/no-module-mocking")
    assert code == 1
    assert sorted(f["line"] for f in mocking) == [6, 7, 8, 12]
    for finding in mocking:
        assert finding["engine"] == "ast-grep"
        assert finding["severity"] == "error"
        assert finding["message"]
        assert finding["fix_hint"]


def test_mocking_good_allows_object_forms(capsys):
    code, mocking = _findings_for(capsys, "mocking_good.py", "pyslop/no-module-mocking")
    assert mocking == []
    assert code == 0
