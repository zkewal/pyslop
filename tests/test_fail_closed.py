"""Fail closed: a broken engine is exit 2 with no findings, never a green run."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pyslop.cli import main

GREP_ITEM = {
    "ruleId": "pyslop/no-any",
    "file": "a.py",
    "range": {"start": {"line": 0, "column": 0}},
}

# Each case: the engine, its exit code, and its stdout.
BROKEN = {
    "ruff-crash": ("ruff", 2, ""),
    "ruff-bad-json": ("ruff", 1, "not json"),
    "ty-crash": ("ty", 2, ""),
    "ty-summary-mismatch": (
        "ty",
        1,
        "a.py:1:1: error[invalid-assignment] bad\nFound 2 diagnostics\n",
    ),
    "ast-grep-crash": ("ast-grep", 3, ""),
    "ast-grep-bad-json": ("ast-grep", 1, "not json"),
    "ast-grep-non-object": ("ast-grep", 1, json.dumps([1])),
    "ast-grep-no-range": ("ast-grep", 1, json.dumps([{"ruleId": "x", "file": "a"}])),
    "ast-grep-non-int-line": (
        "ast-grep",
        1,
        json.dumps([{**GREP_ITEM, "range": {"start": {"line": "0", "column": 0}}}]),
    ),
    "ast-grep-unreadable-source": (
        "ast-grep",
        1,
        json.dumps([{**GREP_ITEM, "file": "/nonexistent/a.py"}]),
    ),
}


@pytest.mark.parametrize("case", BROKEN)
def test_broken_engine_output_is_exit_2(
    case: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine, returncode, stdout = BROKEN[case]

    def _fake_run(
        cmd: list[str], **_: object
    ) -> subprocess.CompletedProcess[str]:  # SAFETY: test double
        return subprocess.CompletedProcess(cmd, returncode, stdout, "boom")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    (tmp_path / "a.py").write_text("x = 1\n")
    code = main(["check", str(tmp_path / "a.py"), "--format", "json", "--only", engine])
    assert code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("engine", ["ruff", "ty", "ast-grep"])
def test_missing_engine_binary_is_exit_2(
    engine: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(shutil, "which", lambda *_, **__: None)
    (tmp_path / "a.py").write_text("x = 1\n")
    code = main(["check", str(tmp_path / "a.py"), "--format", "json", "--only", engine])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert f"{engine} binary not found" in captured.err


def test_init_on_unparsable_pyproject_is_exit_2_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project\n")
    code = main(["init", str(tmp_path)])
    assert code == 2
    assert (tmp_path / "pyproject.toml").read_text() == "[project\n"
    assert not (tmp_path / ".pre-commit-config.yaml").exists()
    assert not (tmp_path / "tools").exists()
    assert "cannot parse" in capsys.readouterr().err
