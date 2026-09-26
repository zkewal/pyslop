import json
import shutil
from pathlib import Path

import pytest

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "ruff"


def test_any_arg_yields_ruff_ann401_alongside_no_any_finding(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        ["check", str(FIXTURES / "ann.py"), "--format", "json", "--only", "ruff"]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    ann = next(f for f in findings if f["rule"] == "ANN401")
    assert ann["engine"] == "ruff"
    assert ann["file"].endswith("ann.py")
    assert ann["severity"] == "error"
    assert ann["message"]
    code = main(
        [
            "check",
            str(FIXTURES / "ann.py"),
            "--format",
            "json",
            "--only",
            "ast-grep",
        ]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert any(
        f["engine"] == "ast-grep" and f["rule"] == "pyslop/no-any" for f in findings
    )


def test_fix_sorts_imports_and_leaves_cast_untouched(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    target = tmp_path / "fix.py"
    shutil.copy(FIXTURES / "fix.py", target)
    code = main(["check", str(target), "--fix", "--format", "json", "--only", "ruff"])
    assert code == 1
    capsys.readouterr()
    text = target.read_text()
    assert text.index("import os") < text.index("import sys")
    assert "cast(int" in text
    assert "SAFETY" not in text
    code = main(["check", str(target), "--format", "json", "--only", "ast-grep"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert any(
        f["engine"] == "ast-grep" and f["rule"] == "pyslop/require-safety-comment"
        for f in findings
    )


@pytest.mark.parametrize("name", ["ruff.toml", ".ruff.toml"])
def test_standalone_ruff_config_wins_over_shipped(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Root ruff config above a package pyproject that has no [tool.ruff]:
    # ruff keeps walking up, so pyslop must not force the shipped profile.
    (tmp_path / name).write_text('[lint]\nselect = ["E"]\n')
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0"\n')
    target = pkg / "ann.py"
    shutil.copy(FIXTURES / "ann.py", target)
    code = main(["check", str(target), "--format", "json", "--only", "ruff"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []
