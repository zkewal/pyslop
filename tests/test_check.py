import json
import subprocess
from pathlib import Path

import pytest

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "safety"


def test_bad_file_lists_one_finding_per_unjustified_hatch(
    capsys: pytest.CaptureFixture[str],
) -> None:
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


def test_good_file_exits_zero_with_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
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


def test_broken_rules_config_fails_closed_not_green(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules = tmp_path / "tools" / "pyslop" / "rules"
    rules.mkdir(parents=True)
    (rules / "sgconfig.yml").write_text("ruleDirs: [pyslop\n")
    target = tmp_path / "dirty.py"
    dirty = 'def lookup(obj: object) -> bool:\n    return hasattr(obj, "name")\n'
    target.write_text(dirty)
    code = main(["check", str(target), "--format", "json", "--only", "ast-grep"])
    out = capsys.readouterr()
    assert code == 2
    assert "ast-grep" in out.err


def test_findings_signal_without_payload_fails_closed(
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
            args=[], returncode=1, stdout="", stderr="boom"
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)
    code = main(["check", str(target), "--format", "json", "--only", "ast-grep"])
    out = capsys.readouterr()
    assert code == 2
    assert "ast-grep" in out.err


def test_non_list_payload_fails_closed(
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
            args=[], returncode=1, stdout='{"ruleId": "x"}', stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)
    code = main(["check", str(target), "--format", "json", "--only", "ast-grep"])
    out = capsys.readouterr()
    assert code == 2
    assert "ast-grep" in out.err


def test_empty_list_payload_with_findings_signal_fails_closed(
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
            args=[], returncode=1, stdout="[]", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)
    code = main(["check", str(target), "--format", "json", "--only", "ast-grep"])
    out = capsys.readouterr()
    assert code == 2
    assert "ast-grep" in out.err
