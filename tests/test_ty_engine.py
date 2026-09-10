import json
import subprocess
from pathlib import Path

import pytest

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "ty"


def test_len_of_int_yields_ty_error(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["check", str(FIXTURES / "bad.py"), "--format", "json", "--only", "ty"])
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


def test_clean_file_exits_zero_with_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        ["check", str(FIXTURES / "good.py"), "--format", "json", "--only", "ty"]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_no_ty_flag_skips_type_check(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "check",
            str(FIXTURES / "bad.py"),
            "--format",
            "json",
            "--only",
            "ty",
            "--no-ty",
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_mypy_config_left_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    content = (
        '[project]\nname = "fake"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\n\n[tool.mypy]\nstrict = true\n'
    )
    pyproject.write_text(content)
    target = tmp_path / "bad.py"
    target.write_text("print(len(3))\n")
    code = main(["check", str(target), "--format", "json", "--only", "ty"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert pyproject.read_text() == content
    assert any(f["engine"] == "ty" for f in findings)
    assert all(f["engine"] != "mypy" for f in findings)


FLOOR = Path(__file__).parent / "fixtures" / "ty_floor"
OVERRIDE = Path(__file__).parent / "fixtures" / "ty_override"
TYTOML = Path(__file__).parent / "fixtures" / "ty_toml"


def test_consumer_python_floor_applies(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["check", str(FLOOR / "v312.py"), "--format", "json", "--only", "ty"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert any(
        f["engine"] == "ty"
        and f["rule"] == "ty/invalid-syntax"
        and f["severity"] == "error"
        and f["file"].endswith("v312.py")
        for f in findings
    )


def test_ty_toml_floor_applies(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["check", str(TYTOML / "v312.py"), "--format", "json", "--only", "ty"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert any(
        f["engine"] == "ty"
        and f["rule"] == "ty/invalid-syntax"
        and f["file"].endswith("v312.py")
        for f in findings
    )


def test_consumer_rule_override_respected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        ["check", str(OVERRIDE / "badimport.py"), "--format", "json", "--only", "ty"]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []


def test_unparsed_diagnostics_signal_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "clean.py"
    target.write_text("x: int = 1\n")

    def _fake_run(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=1, stdout="garbage line\n", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)
    code = main(["check", str(target), "--format", "json", "--only", "ty"])
    out = capsys.readouterr()
    assert code == 2
    assert "ty" in out.err


@pytest.mark.parametrize("spec", [">=3.11,<3.13", "==3.11.*", "~=3.11", "==3.11.5"])
def test_native_floor_from_requires_python_forms(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], spec: str
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "floor"\nversion = "0.0.0"\nrequires-python = "{spec}"\n'
    )
    (tmp_path / "v312.py").write_text("type Alias = int\n")
    code = main(
        ["check", str(tmp_path / "v312.py"), "--format", "json", "--only", "ty"]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 1, spec
    assert any(
        f["engine"] == "ty"
        and f["rule"] == "ty/invalid-syntax"
        and f["file"].endswith("v312.py")
        for f in findings
    ), spec


def test_dot_ty_toml_does_not_suppress_strict_defaults(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "floor"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
    )
    (tmp_path / ".ty.toml").write_text('[environment]\npython-version = "3.11"\n')
    (tmp_path / "v312.py").write_text("type Alias = int\n")
    code = main(
        ["check", str(tmp_path / "v312.py"), "--format", "json", "--only", "ty"]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []
