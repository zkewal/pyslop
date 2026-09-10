"""Thin runner: ast-grep scan over vendored rules, merged JSON findings."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

SAFETY_RULE = "pyslop/require-safety-comment"
SAFETY_RE = re.compile(r"#\s*SAFETY\s*:\s*\S")
TY_CONCISE_RE = re.compile(
    r"^(?P<file>.+):(?P<line>\d+):(?P<col>\d+): "
    r"(?P<severity>\w+)\[(?P<rule>[^\]]+)\] (?P<message>.*)$"
)


def bundled_rules_dir() -> Path:
    return Path(__file__).resolve().parent / "rules"


def bundled_ty_config() -> Path:
    return Path(__file__).resolve().parent / "config" / "ty.toml"


def discover_rules_dir(paths: list[str]) -> Path:
    """tools/pyslop/rules walking up from the first path, else bundled rules."""
    start = Path(paths[0]).resolve() if paths else Path.cwd()
    directory = start if start.is_dir() else start.parent
    for candidate in (directory, *directory.parents):
        vendored = candidate / "tools" / "pyslop" / "rules"
        if vendored.is_dir():
            return vendored
    return bundled_rules_dir()


def has_safety(lines: list[str], lineno: int) -> bool:
    """True when a non-empty `# SAFETY: <reason>` is on the line or the one above."""
    same = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
    prev = lines[lineno - 2] if lineno - 2 >= 0 else ""
    return bool(SAFETY_RE.search(same) or SAFETY_RE.search(prev))


def run_ty(paths: list[str]) -> list[dict] | None:
    """Run ty with the shipped strict config; None means the runner itself failed."""
    binary = shutil.which("ty")
    if binary is None:
        print("pyslop: ty binary not found on PATH", file=sys.stderr)
        return None
    proc = subprocess.run(
        [
            binary,
            "check",
            "--config-file",
            str(bundled_ty_config()),
            "--error",
            "all",  # new rules added after the pin stay errors too
            "--output-format",
            "concise",
            *paths,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        print(f"pyslop: ty check failed:\n{proc.stderr}", file=sys.stderr)
        return None
    findings = []
    for line in proc.stdout.splitlines():
        match = TY_CONCISE_RE.match(line)
        if match is None:
            continue  # summary lines like "Found 2 diagnostics"
        findings.append(
            {
                "engine": "ty",
                "rule": f"ty/{match.group('rule')}",
                "file": match.group("file"),
                "line": int(match.group("line")),
                "col": int(match.group("col")),
                "message": match.group("message"),
                "fix_hint": "",
                "severity": match.group("severity"),
            }
        )
    return findings


def shipped_ruff_config() -> Path:
    return Path(__file__).resolve().parent / "config" / "ruff.toml"


def ruff_config_args(paths: list[str]) -> list[str]:
    """--config shipped unless the nearest pyproject has [tool.ruff]."""
    start = Path(paths[0]).resolve() if paths else Path.cwd()
    directory = start if start.is_dir() else start.parent
    for candidate in (directory, *directory.parents):
        pyproject = candidate / "pyproject.toml"
        if pyproject.is_file():
            try:
                has_ruff = "ruff" in tomllib.loads(pyproject.read_text()).get(
                    "tool", {}
                )
            except (OSError, tomllib.TOMLDecodeError):
                break
            return [] if has_ruff else ["--config", str(shipped_ruff_config())]
    return ["--config", str(shipped_ruff_config())]


def run_ruff(paths: list[str], fix: bool) -> tuple[list[dict], int]:
    """Run ruff check, mapped to findings. Returns (findings, fatal_exit)."""
    binary = shutil.which("ruff")
    if binary is None:
        print("pyslop: ruff binary not found on PATH", file=sys.stderr)
        return [], 2
    cmd = [binary, "check", "--output-format", "json", *ruff_config_args(paths)]
    if fix:
        cmd.append("--fix")
    proc = subprocess.run([*cmd, *paths], capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        print(f"pyslop: ruff failed:\n{proc.stderr}", file=sys.stderr)
        return [], 2
    try:
        raw = json.loads(proc.stdout if proc.stdout.strip() else "[]")
    except json.JSONDecodeError:
        print(f"pyslop: could not parse ruff output:\n{proc.stderr}", file=sys.stderr)
        return [], 2
    return [
        {
            "engine": "ruff",
            "rule": item.get("code", ""),
            "file": item.get("filename", ""),
            "line": item["location"]["row"],
            "col": item["location"]["column"],
            "message": item.get("message") or "",
            "fix_hint": (item.get("fix") or {}).get("message") or "",
            "severity": item.get("severity") or "error",
        }
        for item in raw
    ], 0


PYSLOP_BLOCK = """[tool.pyslop]
exclude = []
# Severity overrides by rule id, e.g. "pyslop/no-isinstance-ladder" = "warn".
[tool.pyslop.rules]
"""


def _embed_toml(path: Path, prefix: str) -> str:
    """Shipped standalone config rewritten as a [tool.<name>] block."""
    out = [f"[{prefix}]"]
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and not stripped.startswith("[["):
            out.append(f"[{prefix}.{stripped[1:]}")
        else:
            out.append(line)
    return "\n".join(out).rstrip() + "\n"


def _append_block(path: Path, block: str) -> None:
    """Append a TOML/YAML text block, keeping one blank line of separation."""
    text = path.read_text() if path.is_file() else ""
    text = text.rstrip("\n")
    path.write_text((text + "\n\n" if text else "") + block.rstrip("\n") + "\n")


def _init_rev(root: Path) -> str:
    """Pinned version for generated files: own git tag, else main."""
    proc = subprocess.run(
        ["git", "describe", "--tags"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    tag = proc.stdout.strip()
    return tag if proc.returncode == 0 and tag else "main"


def _pre_commit_entry(rev: str) -> str:
    return f"""  - repo: local
    hooks:
      - id: pyslop
        name: pyslop
        entry: uv tool run --from git+https://github.com/zkewal/pyslop@{rev} pyslop check --no-ty
        language: system
        types: [python]
        pass_filenames: true
"""


def _workflow_text(rev: str) -> str:
    return f"""name: pyslop

on:
  push:
  pull_request:

jobs:
  pyslop:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      # Private repo: the runner needs read access (a fine-grained PAT).
      - name: Check for slop
        run: uv tool run --from git+https://github.com/zkewal/pyslop@{rev} pyslop check
"""


def init_command(root: str) -> int:
    base = Path(root).resolve()
    vendored = base / "tools" / "pyslop" / "rules"
    if vendored.is_dir():
        print(f"pyslop: {vendored} already present, skipping")
    else:
        shutil.copytree(bundled_rules_dir(), vendored)
        print(f"pyslop: vendored rules to {vendored}")
    pyproject = base / "pyproject.toml"
    try:
        tool = (
            tomllib.loads(pyproject.read_text()).get("tool", {})
            if pyproject.is_file()
            else {}
        )
    except tomllib.TOMLDecodeError as exc:
        print(f"pyslop: cannot parse {pyproject}: {exc}", file=sys.stderr)
        return 2
    for key, block in (
        ("pyslop", PYSLOP_BLOCK),
        ("ruff", _embed_toml(shipped_ruff_config(), "tool.ruff")),
        ("ty", _embed_toml(bundled_ty_config(), "tool.ty")),
    ):
        if key in tool:
            print(f"pyslop: [tool.{key}] already present, skipping")
        else:
            _append_block(pyproject, block)
            print(f"pyslop: added [tool.{key}] to {pyproject}")
    rev = _init_rev(base)
    hook = base / ".pre-commit-config.yaml"
    if hook.is_file():
        existing = hook.read_text()
        if "pyslop" in existing:
            print(f"pyslop: {hook} already present, skipping")
        elif "repos:" in existing:
            _append_block(hook, _pre_commit_entry(rev))
            print(f"pyslop: added hook to {hook}")
        else:
            print(f"pyslop: {hook} has no repos:, skipping")
    else:
        hook.write_text("repos:\n" + _pre_commit_entry(rev))
        print(f"pyslop: wrote {hook}")
    workflow = base / ".github" / "workflows" / "pyslop.yml"
    if workflow.is_file():
        print(f"pyslop: {workflow} already present, skipping")
    else:
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(_workflow_text(rev))
        print(f"pyslop: wrote {workflow}")
    return 0


def format_command(paths: list[str]) -> int:
    binary = shutil.which("ruff")
    if binary is None:
        print("pyslop: ruff binary not found on PATH", file=sys.stderr)
        return 2
    return subprocess.run([binary, "format", *paths], check=False).returncode


def check_command(
    paths: list[str],
    format: str,
    fix: bool,
    no_ty: bool,
    only: str | None = None,
) -> int:
    findings: list[dict] = []
    if only in (None, "ast-grep"):
        binary = shutil.which("ast-grep")
        if binary is None:
            print("pyslop: ast-grep binary not found on PATH", file=sys.stderr)
            return 2
        rules_dir = discover_rules_dir(paths)
        proc = subprocess.run(
            [
                binary,
                "scan",
                "--config",
                str(rules_dir / "sgconfig.yml"),
                "--json",
                *paths,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            raw = json.loads(proc.stdout if proc.stdout.strip() else "[]")
        except json.JSONDecodeError:
            print(
                f"pyslop: could not parse ast-grep output:\n{proc.stderr}",
                file=sys.stderr,
            )
            return 2
        sources: dict[str, list[str]] = {}
        for item in raw:
            rule = item.get("ruleId", "")
            line = item["range"]["start"]["line"] + 1
            col = item["range"]["start"]["column"] + 1
            file = item.get("file", "")
            if rule == SAFETY_RULE:
                if file not in sources:
                    sources[file] = Path(file).read_text().splitlines()
                if has_safety(sources[file], line):
                    continue
            findings.append(
                {
                    "engine": "ast-grep",
                    "rule": rule,
                    "file": file,
                    "line": line,
                    "col": col,
                    "message": item.get("message") or "",
                    "fix_hint": item.get("note") or "",
                    "severity": item.get("severity") or "error",
                }
            )
    if only in (None, "ruff"):
        ruff_findings, fatal = run_ruff(paths, fix)
        if fatal:
            return fatal
        findings.extend(ruff_findings)
    if only in (None, "ty") and not no_ty:
        ty_findings = run_ty(paths)
        if ty_findings is None:
            return 2
        findings.extend(ty_findings)
    if format == "json":
        print(json.dumps(findings, indent=2))
    else:
        for finding in findings:
            print(
                f"{finding['file']}:{finding['line']}:{finding['col']}: "
                f"[{finding['rule']}] {finding['message']} "
                f"(fix: {finding['fix_hint']})"
            )
    return 1 if any(f["severity"] == "error" for f in findings) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyslop", description="Deterministic anti-slop toolkit for Python."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Run vendored rules over paths.")
    check.add_argument(
        "paths", nargs="*", default=["."], help="Files or dirs (default: .)."
    )
    check.add_argument("--format", choices=["text", "json"], default="text")
    check.add_argument(
        "--no-ty", action="store_true", help="Skip ty (pre-commit speed)."
    )
    check.add_argument(
        "--only",
        choices=["ast-grep", "ruff", "ty"],
        default=None,
        help="Run one engine only (default: all).",
    )
    check.add_argument(
        "--fix",
        action="store_true",
        help="Apply safe ruff fixes (never --unsafe-fixes).",
    )
    format_cmd = sub.add_parser("format", help="Run ruff format over paths.")
    format_cmd.add_argument(
        "paths", nargs="*", default=["."], help="Files or dirs (default: .)."
    )
    init_cmd = sub.add_parser("init", help="Vendor rules and write configs.")
    init_cmd.add_argument(
        "path", nargs="?", default=".", help="Repo root (default: .)."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return check_command(args.paths, args.format, args.fix, args.no_ty, args.only)
    if args.command == "format":
        return format_command(args.paths)
    if args.command == "init":
        return init_command(args.path)
    raise AssertionError(f"unknown command {args.command}")
