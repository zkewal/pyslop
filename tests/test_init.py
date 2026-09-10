import json
import shutil
import subprocess
from importlib.metadata import version
from pathlib import Path

import pytest

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "init"


def fresh_repo(tmp_path: Path) -> Path:
    dest = tmp_path / "fresh"
    shutil.copytree(FIXTURES / "fresh", dest)
    return dest


def custom_repo(tmp_path: Path) -> Path:
    dest = tmp_path / "custom"
    shutil.copytree(FIXTURES / "custom", dest)
    return dest


def test_init_vendors_rules_and_writes_all_blocks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = fresh_repo(tmp_path)
    code = main(["init", str(root)])
    capsys.readouterr()
    assert code == 0
    assert (root / "tools" / "pyslop" / "rules" / "sgconfig.yml").is_file()
    assert list((root / "tools" / "pyslop" / "rules" / "pyslop").glob("*.yml"))
    text = (root / "pyproject.toml").read_text()
    assert "[tool.pyslop]" in text
    assert "[tool.ruff]" in text
    assert "[tool.ty.rules]" in text
    assert "pyslop" in (root / ".pre-commit-config.yaml").read_text()
    workflow = root / ".github" / "workflows" / "pyslop.yml"
    assert workflow.is_file()
    assert f"pyslop@v{version('pyslop')}" in workflow.read_text()


def test_init_never_overwrites_existing_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    assert "[tool.ty.rules]" in text
    assert (root / ".pre-commit-config.yaml").read_text() == hook_before
    assert (root / ".github" / "workflows" / "pyslop.yml").read_text() == (
        workflow_before
    )
    assert "already present" in out


def test_init_starts_deviation_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = fresh_repo(tmp_path)
    assert main(["init", str(root)]) == 0
    capsys.readouterr()
    code = main(
        ["check", str(root / "pyproject.toml"), "--format", "json", "--only", "pyslop"]
    )
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []


def test_init_pins_pyslop_release_not_consumer_tag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git not available")
    root = fresh_repo(tmp_path)
    subprocess.run([git, "init", "-q"], cwd=root, check=True)
    subprocess.run(
        [
            git,
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=test",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        ],
        cwd=root,
        check=True,
    )
    subprocess.run([git, "tag", "v2.229.0"], cwd=root, check=True)
    assert main(["init", str(root)]) == 0
    capsys.readouterr()
    hook = (root / ".pre-commit-config.yaml").read_text()
    workflow = (root / ".github" / "workflows" / "pyslop.yml").read_text()
    assert f"pyslop@v{version('pyslop')}" in hook
    assert f"pyslop@v{version('pyslop')}" in workflow
    assert "v2.229.0" not in hook
    assert "v2.229.0" not in workflow


def test_init_creates_pyproject_when_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    code = main(["init", str(root)])
    capsys.readouterr()
    assert code == 0
    text = (root / "pyproject.toml").read_text()
    assert "[tool.pyslop]" in text
    assert "[tool.ruff]" in text
    assert "[tool.ty.rules]" in text


def test_init_stamps_ty_rules_without_forced_floor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "py311"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "floor"\nversion = "0.0.0"\n'
        'requires-python = ">=3.11,<3.13"\n'
    )
    assert main(["init", str(root)]) == 0
    capsys.readouterr()
    text = (root / "pyproject.toml").read_text()
    assert "[tool.ty.rules]" in text
    assert "python-version" not in text


def test_init_floor_applies_natively_after_init(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "py311check"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "floor"\nversion = "0.0.0"\n'
        'requires-python = ">=3.11,<3.13"\n'
    )
    assert main(["init", str(root)]) == 0
    capsys.readouterr()
    (root / "v312.py").write_text("type Alias = int\n")
    code = main(["check", str(root / "v312.py"), "--format", "json", "--only", "ty"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 1
    assert any(
        f["engine"] == "ty" and f["rule"] == "ty/invalid-syntax" for f in findings
    )
