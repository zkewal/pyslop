import json
from pathlib import Path

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "ty"


def test_len_of_int_yields_ty_error(capsys):
    code = main(["check", str(FIXTURES / "bad.py"), "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    ty_findings = [f for f in findings if f["engine"] == "ty"]
    assert any(
        f["rule"] == "ty/invalid-argument-type"
        and f["severity"] == "error"
        and f["file"].endswith("bad.py")
        and f["line"] == 1
        and f["message"]
        for f in ty_findings
    )


def test_clean_file_exits_zero_with_empty_list(capsys):
    code = main(["check", str(FIXTURES / "good.py"), "--format", "json"])
    assert code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_no_ty_flag_skips_type_check(capsys):
    code = main(["check", str(FIXTURES / "bad.py"), "--format", "json", "--no-ty"])
    assert code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_mypy_config_left_alone(tmp_path, capsys):
    pyproject = tmp_path / "pyproject.toml"
    content = (
        '[project]\nname = "fake"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\n\n[tool.mypy]\nstrict = true\n'
    )
    pyproject.write_text(content)
    target = tmp_path / "bad.py"
    target.write_text("print(len(3))\n")
    code = main(["check", str(target), "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert pyproject.read_text() == content
    assert any(f["engine"] == "ty" for f in findings)
    assert all(f["engine"] != "mypy" for f in findings)
