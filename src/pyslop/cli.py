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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return check_command(args.paths, args.format, args.fix, args.no_ty, args.only)
    if args.command == "format":
        return format_command(args.paths)
    raise AssertionError(f"unknown command {args.command}")
