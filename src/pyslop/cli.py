"""Thin runner: ast-grep scan over vendored rules, merged JSON findings."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePath

SAFETY_RULE = "pyslop/require-safety-comment"
SAFETY_RE = re.compile(r"#\s*SAFETY\s*:\s*\S")
DEVIATION_RULE = "pyslop/deviation-needs-reason"
URL_RE = re.compile(r"https?://\S")
KEYVAL_RE = re.compile(r"^\s*(?P<key>[^=\s][^=]*?)\s*=\s*(?P<value>.*)$")
PAIR_RE = re.compile(r"""["']?(?P<key>[\w/.-]+)["']?\s*=\s*["'](?P<value>[^"']*)["']""")
OFF_VALUE_RE = re.compile(r"""^\s*["']off["']\s*(#.*)?$""", re.IGNORECASE)
PYSLOP_KEYS = ("rules", "exclude")
TY_CONCISE_RE = re.compile(
    r"^(?P<file>.+):(?P<line>\d+):(?P<col>\d+): "
    r"(?P<severity>\w+)\[(?P<rule>[^\]]+)\] (?P<message>.*)$"
)


def bundled(*parts: str) -> Path:
    """File shipped inside the package (rules, configs)."""
    return Path(__file__).resolve().parent.joinpath(*parts)


def bundled_rules_dir() -> Path:
    return bundled("rules")


def bundled_ty_config() -> Path:
    return bundled("config", "ty.toml")


def walk_up(start: Path):
    """Yield a dir (or a file's parent) then each parent up to the root."""
    directory = start if start.is_dir() else start.parent
    yield directory
    yield from directory.parents


def nearest_pyproject(path: Path) -> Path | None:
    """Nearest pyproject.toml walking up, or None."""
    for candidate in walk_up(path.resolve()):
        pyproject = candidate / "pyproject.toml"
        if pyproject.is_file():
            return pyproject
    return None


def require_binary(name: str) -> str | None:
    """Engine binary path, or None after reporting it missing."""
    binary = shutil.which(name)
    if binary is None:
        print(f"pyslop: {name} binary not found on PATH", file=sys.stderr)
    return binary


def discover_rules_dir(paths: list[str]) -> Path:
    """tools/pyslop/rules walking up from the first path, else bundled rules."""
    for candidate in walk_up(_start(paths)):
        vendored = candidate / "tools" / "pyslop" / "rules"
        if vendored.is_dir():
            return vendored
    return bundled_rules_dir()


def pyslop_excludes(pyproject: Path) -> list[str]:
    """Exclude globs from [tool.pyslop]. Thin wrapper over pyslop_table."""
    exclude = pyslop_table(pyproject).get("exclude", [])
    if not isinstance(exclude, list):
        return []
    return [e for e in exclude if isinstance(e, str)]


def has_safety(lines: list[str], lineno: int) -> bool:
    """True when a non-empty `# SAFETY: <reason>` is on the line or the one above."""
    same = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
    prev = lines[lineno - 2] if lineno - 2 >= 0 else ""
    return bool(SAFETY_RE.search(same) or SAFETY_RE.search(prev))


def run_ty(paths: list[str]) -> list[dict] | None:
    """Run ty with the shipped strict config; None means the runner itself failed."""
    binary = require_binary("ty")
    if binary is None:
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
    return bundled("config", "ruff.toml")


def _start(paths: list[str]) -> Path:
    """Resolved first checked path, or the working directory."""
    return Path(paths[0]).resolve() if paths else Path.cwd()


def ruff_config_args(paths: list[str]) -> list[str]:
    """--config shipped unless the nearest pyproject has [tool.ruff]."""
    pyproject = nearest_pyproject(_start(paths))
    try:
        data = tomllib.loads(pyproject.read_text()) if pyproject else {}
    except (OSError, tomllib.TOMLDecodeError):
        data = {}
    if "ruff" in data.get("tool", {}):
        return []
    return ["--config", str(shipped_ruff_config())]


def run_ruff(paths: list[str], fix: bool) -> tuple[list[dict], int]:
    """Run ruff check, mapped to findings. Returns (findings, fatal_exit)."""
    binary = require_binary("ruff")
    if binary is None:
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
# Severity overrides by rule id ("warn" / "error" / "off").
# An entry that turns a rule off needs a reason comment with an issue
# URL on the line directly above it, or `pyslop check` reports
# pyslop/deviation-needs-reason.
[tool.pyslop.rules]
# Example (keep the reason line above the entry):
# # Slow rollout, see https://github.com/org/repo/issues/1
# "pyslop/no-isinstance-ladder" = "off"
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


def has_reason_comment(lines: list[str], lineno: int) -> bool:
    """True when the line directly above is a comment containing a URL."""
    prev = lines[lineno - 2] if lineno >= 2 else ""
    stripped = prev.strip()
    return stripped.startswith("#") and bool(URL_RE.search(stripped))


def deviation_finding(pyproject: Path, line: int, col: int, message: str) -> dict:
    return {
        "engine": "pyslop",
        "rule": DEVIATION_RULE,
        "file": str(pyproject),
        "line": line,
        "col": col,
        "message": message,
        "fix_hint": (
            "Add a TOML comment on the line directly above "
            "with a reason and an issue URL."
        ),
        "severity": "error",
    }


def _col(raw: str) -> int:
    return len(raw) - len(raw.lstrip()) + 1


def _unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    return text


def _scan_off_pairs(
    pyproject: Path,
    lines: list[str],
    lineno: int,
    raw: str,
    kind: str,
) -> list[dict]:
    """Flag unjustified disables inside `rules = { ... }` (any line of it).

    kind is "pyslop" (value "off" disables) or "ty" ("warn"/"ignore"
    downgrades). Each pair is judged by the comment above its own line.
    """
    findings = []
    for pair in PAIR_RE.finditer(raw):
        value = pair.group("value").lower()
        disabling = value == "off" if kind == "pyslop" else value in ("warn", "ignore")
        if not disabling or has_reason_comment(lines, lineno):
            continue
        name = pair.group("key")
        if kind == "pyslop":
            message = f'Rule "{name}" is turned off without a reason.'
        else:
            message = (
                f'ty override sets "{name}" to "{pair.group("value")}" '
                "without a reason."
            )
        findings.append(deviation_finding(pyproject, lineno, pair.start() + 1, message))
    return findings


def check_pyproject_deviations(pyproject: Path) -> list[dict]:
    """Flag unjustified rule disables in one pyproject.toml (line-oriented).

    Sources: `[tool.pyslop.rules]` entries set to `"off"` (table or inline
    form), every `[tool.ruff.lint.per-file-ignores]` entry, and
    `[[tool.ty.overrides]]` rule downgrades to `"warn"`/`"ignore"`.
    Justified means the line directly above is a comment with a URL.
    Unknown `[tool.pyslop]` keys are errors too.
    """
    try:
        text = pyproject.read_text()
    except OSError:
        return []
    lines = text.splitlines()
    findings: list[dict] = []
    section: str | None = None
    pending: str | None = None  # inside multiline `rules = { ... }`
    depth = 0
    for lineno, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("["):
            header = re.sub(r"\s+", "", stripped).replace('"', "").replace("'", "")
            if header == "[tool.pyslop]":
                section = "pyslop"
            elif header == "[tool.pyslop.rules]":
                section = "pyslop-rules"
            elif header == "[tool.ruff.lint.per-file-ignores]":
                section = "ruff-ignores"
            elif header == "[[tool.ty.overrides]]":
                section = "ty-overrides"
            else:
                match = re.match(r"^\[tool\.pyslop\.([^]]+)\]$", header)
                if match and match.group(1).split(".")[0] not in PYSLOP_KEYS:
                    findings.append(
                        deviation_finding(
                            pyproject,
                            lineno,
                            _col(raw),
                            f'Unknown [tool.pyslop] key "{match.group(1)}" '
                            '(only "rules" and "exclude" are supported).',
                        )
                    )
                section = None
            pending = None
            continue
        if section is None:
            continue
        if pending is not None:
            findings.extend(_scan_off_pairs(pyproject, lines, lineno, raw, pending))
            depth += raw.count("{") - raw.count("}")
            if depth <= 0:
                pending = None
            continue
        match = KEYVAL_RE.match(raw)
        if match is None:
            continue
        key = _unquote(match.group("key"))
        value = match.group("value")
        if section == "pyslop":
            if key == "rules":
                findings.extend(
                    _scan_off_pairs(pyproject, lines, lineno, raw, "pyslop")
                )
                depth = value.count("{") - value.count("}")
                if depth > 0:
                    pending = "pyslop"
            elif key.split(".")[0] not in PYSLOP_KEYS:
                findings.append(
                    deviation_finding(
                        pyproject,
                        lineno,
                        _col(raw),
                        f'Unknown [tool.pyslop] key "{key}" '
                        '(only "rules" and "exclude" are supported).',
                    )
                )
        elif section == "pyslop-rules":
            if OFF_VALUE_RE.match(value) and not has_reason_comment(lines, lineno):
                findings.append(
                    deviation_finding(
                        pyproject,
                        lineno,
                        _col(raw),
                        f'Rule "{key}" is turned off without a reason.',
                    )
                )
        elif section == "ruff-ignores":
            if not has_reason_comment(lines, lineno):
                findings.append(
                    deviation_finding(
                        pyproject,
                        lineno,
                        _col(raw),
                        f'per-file-ignores entry for "{key}" '
                        "needs a reason and an issue link.",
                    )
                )
        elif section == "ty-overrides" and key == "rules":
            findings.extend(_scan_off_pairs(pyproject, lines, lineno, raw, "ty"))
            depth = value.count("{") - value.count("}")
            if depth > 0:
                pending = "ty"
    return findings


def pyslop_table(pyproject: Path) -> dict:
    """Parsed [tool.pyslop] table, or {} when absent/unreadable."""
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    table = data.get("tool", {}).get("pyslop", {})
    return table if isinstance(table, dict) else {}


def apply_pyslop_config(findings: list[dict]) -> list[dict]:
    """Apply [tool.pyslop] rules severities (ast-grep only) and excludes."""
    cache: dict[Path | None, tuple[dict, list]] = {}
    kept = []
    for finding in findings:
        path = Path(finding["file"])
        project = nearest_pyproject(path)
        if project not in cache:
            table = pyslop_table(project) if project is not None else {}
            rules = table.get("rules", {})
            cache[project] = (
                rules if isinstance(rules, dict) else {},
                pyslop_excludes(project) if project is not None else [],
            )
        rules, exclude = cache[project]
        if finding["engine"] == "ast-grep" and finding["rule"] in rules:
            level = str(rules[finding["rule"]]).lower()
            if level == "off":
                continue
            if level == "warn":
                finding = {**finding, "severity": "warning"}
            elif level == "error":
                finding = {**finding, "severity": "error"}
        if project is not None and exclude:
            base = project.parent.resolve()
            absolute = path if path.is_absolute() else Path.cwd() / path
            try:
                rel = absolute.resolve().relative_to(base)
            except ValueError:
                rel = None
            if rel is not None and any(
                isinstance(pat, str) and PurePath(str(rel)).match(pat)
                for pat in exclude
            ):
                continue
        kept.append(finding)
    return kept


def format_command(paths: list[str]) -> int:
    binary = require_binary("ruff")
    if binary is None:
        return 2
    return subprocess.run([binary, "format", *paths], check=False).returncode


def print_text(findings: list[dict]) -> None:
    """One line per finding grouped by file, plus a summary. No color unless a TTY."""
    ordered = sorted(
        findings,
        key=lambda f: (f["file"], f["line"], f["col"], f["engine"], f["rule"]),
    )
    color = sys.stdout.isatty()
    for finding in ordered:
        loc = f"{finding['file']}:{finding['line']}:{finding['col']}"
        if color:
            loc = f"\x1b[1m{loc}\x1b[0m"
        print(f"{loc} {finding['engine']}/{finding['rule']} {finding['message']}")
    total = len(ordered)
    errors = sum(1 for finding in ordered if finding["severity"] == "error")
    print(
        f"{total} finding{'s' if total != 1 else ''} "
        f"({errors} error{'s' if errors != 1 else ''})"
    )


def check_command(
    paths: list[str],
    format: str,
    fix: bool,
    no_ty: bool,
    only: str | None = None,
) -> int:
    findings: list[dict] = []
    if only in (None, "ast-grep"):
        binary = require_binary("ast-grep")
        if binary is None:
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
    if only in (None, "pyslop"):
        seen: list[Path] = []
        for raw_path in paths:
            candidate = nearest_pyproject(Path(raw_path))
            if candidate is not None and candidate not in seen:
                seen.append(candidate)
        for pyproject in seen:
            findings.extend(check_pyproject_deviations(pyproject))
    findings = apply_pyslop_config(findings)
    if format == "json":
        print(json.dumps(findings, indent=2))
    else:
        print_text(findings)
    return 1 if any(f["severity"] == "error" for f in findings) else 0


def _pyslop_version() -> str:
    try:
        return version("pyslop")
    except PackageNotFoundError:
        return "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyslop", description="Deterministic anti-slop toolkit for Python."
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {_pyslop_version()}"
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
        choices=["ast-grep", "ruff", "ty", "pyslop"],
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
