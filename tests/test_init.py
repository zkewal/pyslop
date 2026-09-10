import json
import shutil
from pathlib import Path

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "init"


def fresh_repo(tmp_path):
    dest = tmp_path / "fresh"
    shutil.copytree(FIXTURES / "fresh", dest)
    return dest


def custom_repo(tmp_path):
    dest = tmp_path / "custom"
    shutil.copytree(FIXTURES / "custom", dest)
    return dest


def test_init_vendors_rules_and_writes_all_blocks(tmp_path, capsys):
    root = fresh_repo(tmp_path)
    code = main(["init", str(root)])
    capsys.readouterr()
    assert code == 0
    assert (root / "tools" / "pyslop" / "rules" / "sgconfig.yml").is_file()
    assert list((root / "tools" / "pyslop" / "rules" / "pyslop").glob("*.yml"))
    text = (root / "pyproject.toml").read_text()
    assert "[tool.pyslop]" in text
    assert "[tool.ruff]" in text
    assert "[tool.ty]" in text
    assert "pyslop" in (root / ".pre-commit-config.yaml").read_text()
    workflow = root / ".github" / "workflows" / "pyslop.yml"
    assert workflow.is_file()
    assert "pyslop@main" in workflow.read_text()


def test_init_never_overwrites_existing_keys(tmp_path, capsys):
    root = custom_repo(tmp_path)
    hook_before = (root / ".pre-commit-config.yaml").read_text()
    workflow_before = (root / ".github" / "workflows" / "pyslop.yml").read_text()
    code = main(["init", str(root)])
    out = capsys.readouterr().out
    assert code == 0
    text = (root / "pyproject.toml").read_text()
    assert 'select = ["E", "F"]' in text
    assert "[tool.mypy]" in text
    assert "[tool.pyslop]" in text
    assert "[tool.ty]" in text
    assert (root / ".pre-commit-config.yaml").read_text() == hook_before
    assert (root / ".github" / "workflows" / "pyslop.yml").read_text() == (
        workflow_before
    )
    assert "already present" in out


def test_init_starts_deviation_clean(tmp_path, capsys):
    root = fresh_repo(tmp_path)
    assert main(["init", str(root)]) == 0
    capsys.readouterr()
    code = main(
        ["check", str(root / "pyproject.toml"), "--format", "json", "--only", "pyslop"]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []


def test_init_creates_pyproject_when_missing(tmp_path, capsys):
    root = tmp_path / "empty"
    root.mkdir()
    code = main(["init", str(root)])
    capsys.readouterr()
    assert code == 0
    text = (root / "pyproject.toml").read_text()
    assert "[tool.pyslop]" in text
    assert "[tool.ruff]" in text
    assert "[tool.ty]" in text
