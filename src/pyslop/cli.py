"""Thin runner: ast-grep scan over vendored rules, merged JSON findings."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SAFETY_RULE = "pyslop/require-safety-comment"
SAFETY_RE = re.compile(r"#\s*SAFETY\s*:\s*\S")


def bundled_rules_dir() -> Path:
    return Path(__file__).resolve().parent / "rules"


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


def check_command(paths: list[str], format: str) -> int:
    binary = shutil.which("ast-grep")
    if binary is None:
        print("pyslop: ast-grep binary not found on PATH", file=sys.stderr)
        return 2
    rules_dir = discover_rules_dir(paths)
    proc = subprocess.run(
        [binary, "scan", "--config", str(rules_dir / "sgconfig.yml"), "--json", *paths],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        raw = json.loads(proc.stdout if proc.stdout.strip() else "[]")
    except json.JSONDecodeError:
        print(
            f"pyslop: could not parse ast-grep output:\n{proc.stderr}", file=sys.stderr
        )
        return 2
    sources: dict[str, list[str]] = {}
    findings = []
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return check_command(args.paths, args.format)
    raise AssertionError(f"unknown command {args.command}")
