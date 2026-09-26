import json
from pathlib import Path
from typing import Any

import pytest

from pyslop.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "deviations"
RULE = "pyslop/deviation-needs-reason"


def _check(
    capsys: pytest.CaptureFixture[str], target: Path, *extra: str
) -> tuple[int, Any]:  # SAFETY: decoded JSON scaffolding
    code = main(["check", str(target), "--format", "json", *extra])
    return code, json.loads(capsys.readouterr().out)


def test_uncommented_per_file_ignore_points_at_toml_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
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


def test_reasoned_per_file_ignore_passes(capsys: pytest.CaptureFixture[str]) -> None:
    code, findings = _check(
        capsys, FIXTURES / "per_file_ignore_good", "--only", "pyslop"
    )
    assert code == 0
    assert findings == []


def test_inline_off_with_reason_suppresses_rule(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, findings = _check(
        capsys, FIXTURES / "rules_off" / "off_sample.py", "--only", "ast-grep"
    )
    assert code == 0
    assert findings == []
    code, findings = _check(capsys, FIXTURES / "rules_off", "--only", "pyslop")
    assert code == 0
    assert findings == []


def test_warn_downgrades_severity_without_failing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, findings = _check(
        capsys, FIXTURES / "rules_warn" / "warn_sample.py", "--only", "ast-grep"
    )
    assert code == 0
    assert len(findings) == 1
    assert findings[0]["rule"] == "pyslop/no-module-mocking"
    assert findings[0]["severity"] == "warning"
    assert findings[0]["fix_hint"]


def test_unknown_pyslop_key_is_error_finding(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, findings = _check(capsys, FIXTURES / "unknown_key", "--only", "pyslop")
    assert code == 1
    assert len(findings) == 1
    assert findings[0]["engine"] == "pyslop"
    assert findings[0]["rule"] == RULE
    assert findings[0]["line"] == 8
    assert "stranger" in findings[0]["message"]


def test_ty_override_downgrade_without_reason_is_flagged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, findings = _check(capsys, FIXTURES / "ty_override_bad", "--only", "pyslop")
    assert code == 1
    assert len(findings) == 1
    assert findings[0]["rule"] == RULE
    assert findings[0]["line"] == 7
    assert "unresolved-import" in findings[0]["message"]


def test_reasoned_ty_override_passes(capsys: pytest.CaptureFixture[str]) -> None:
    code, findings = _check(capsys, FIXTURES / "ty_override_good", "--only", "pyslop")
    assert code == 0
    assert findings == []


def test_excluded_path_is_silent_and_kept_path_reports(
    capsys: pytest.CaptureFixture[str],
) -> None:
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


URL = "https://github.com/org/repo/issues/1"
PROJECT = '[project]\nname = "p"\nversion = "0"\n\n'

# (config file, body, line of the unjustified disable). Each is a valid TOML
# spelling that the tool really applies, so each must need a reason.
DISABLES = {
    "header-trailing-comment": (
        "pyproject.toml",
        PROJECT + '[tool.pyslop.rules] # note\n"pyslop/no-any" = "off"\n',
        6,
    ),
    "dotted-key": (
        "pyproject.toml",
        PROJECT + '[tool.pyslop]\nrules."pyslop/no-any" = "off"\n',
        6,
    ),
    "tool-inline-table": (
        "pyproject.toml",
        PROJECT + '[tool]\npyslop = { rules = { "pyslop/no-any" = "off" } }\n',
        6,
    ),
    "ty-rules-table": (
        "pyproject.toml",
        PROJECT + '[tool.ty.rules]\ninvalid-assignment = "ignore"\n',
        6,
    ),
    "ty-overrides-subtable": (
        "pyproject.toml",
        PROJECT + '[[tool.ty.overrides]]\ninclude = ["gen/**"]\n\n'
        '[tool.ty.overrides.rules]\ninvalid-argument-type = "ignore"\n',
        9,
    ),
    "ruff-legacy-per-file-ignores": (
        "pyproject.toml",
        PROJECT + '[tool.ruff.per-file-ignores]\n"gen/*" = ["F401"]\n',
        6,
    ),
    "ruff-extend-per-file-ignores": (
        "pyproject.toml",
        PROJECT + '[tool.ruff.lint.extend-per-file-ignores]\n"gen/*" = ["F401"]\n',
        6,
    ),
    "ruff-inline-per-file-ignores": (
        "pyproject.toml",
        PROJECT + '[tool.ruff.lint]\nper-file-ignores = { "gen/*" = ["F401"] }\n',
        6,
    ),
    "ruff-toml": ("ruff.toml", '[lint.per-file-ignores]\n"gen/*" = ["F401"]\n', 2),
    "ty-toml-rules": ("ty.toml", '[rules]\ninvalid-assignment = "warn"\n', 2),
    "ty-toml-overrides": (
        "ty.toml",
        '[[overrides]]\ninclude = ["gen/**"]\n'
        'rules = { unresolved-import = "ignore" }\n',
        3,
    ),
}


@pytest.mark.parametrize("case", DISABLES)
def test_every_toml_spelling_of_a_disable_needs_a_reason(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    name, body, line = DISABLES[case]
    (tmp_path / name).write_text(body)
    code, findings = _check(capsys, tmp_path, "--only", "pyslop")
    assert code == 1
    assert [(f["rule"], Path(f["file"]).name, f["line"]) for f in findings] == [
        (RULE, name, line)
    ]


@pytest.mark.parametrize("case", DISABLES)
def test_reason_with_url_justifies_every_spelling(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    name, body, line = DISABLES[case]
    lines = body.splitlines()
    lines.insert(line - 1, f"# generated code, {URL}")
    (tmp_path / name).write_text("\n".join(lines) + "\n")
    code, findings = _check(capsys, tmp_path, "--only", "pyslop")
    assert code == 0
    assert findings == []


def test_reason_without_url_is_not_enough(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        PROJECT + '[tool.pyslop.rules]\n# trust me\n"pyslop/no-any" = "off"\n'
    )
    code, findings = _check(capsys, tmp_path, "--only", "pyslop")
    assert code == 1
    assert [f["line"] for f in findings] == [7]


def test_subpackage_disable_is_seen_from_monorepo_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text(PROJECT)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text(
        PROJECT + '[tool.pyslop.rules]\n"pyslop/require-safety-comment" = "off"\n'
    )
    code, findings = _check(capsys, tmp_path, "--only", "pyslop")
    assert code == 1
    assert [(f["file"], f["line"]) for f in findings] == [
        (str(pkg / "pyproject.toml"), 6)
    ]


@pytest.mark.parametrize(
    ("entry", "why"),
    [
        ('"pyslop/no-any" = "warning"', "unknown level"),
        ('E501 = "off"', "only applies to ast-grep rules"),
        ('"ty/invalid-assignment" = "off"', "only applies to ast-grep rules"),
        (f'"{RULE}" = "off"', "only applies to ast-grep rules"),
    ],
)
def test_pyslop_rules_entries_that_do_nothing_are_errors(
    entry: str, why: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Even a reason comment cannot make a no-op override valid.
    (tmp_path / "pyproject.toml").write_text(
        PROJECT + f"[tool.pyslop.rules]\n# {URL}\n{entry}\n"
    )
    code, findings = _check(capsys, tmp_path, "--only", "pyslop")
    assert code == 1
    assert [f["line"] for f in findings] == [7]
    assert why in findings[0]["message"]
