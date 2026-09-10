import json
import shutil
from pathlib import Path

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "ruff"


def test_any_arg_yields_ruff_ann401_alongside_safety_finding(capsys):
    code = main(["check", str(FIXTURES / "ann.py"), "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    by_engine_rule = {(f["engine"], f["rule"]) for f in findings}
    assert ("ruff", "ANN401") in by_engine_rule
    assert ("ast-grep", "pyslop/require-safety-comment") in by_engine_rule
    ann = next(f for f in findings if f["rule"] == "ANN401")
    assert ann["file"].endswith("ann.py")
    assert ann["severity"] == "error"
    assert ann["message"]


def test_fix_sorts_imports_and_leaves_cast_untouched(capsys, tmp_path):
    target = tmp_path / "fix.py"
    shutil.copy(FIXTURES / "fix.py", target)
    code = main(["check", str(target), "--fix", "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    text = target.read_text()
    assert text.index("import os") < text.index("import sys")
    assert "cast(int" in text
    assert "SAFETY" not in text
    assert any(
        f["engine"] == "ast-grep" and f["rule"] == "pyslop/require-safety-comment"
        for f in findings
    )
