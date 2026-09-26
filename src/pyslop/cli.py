"""Thin runner: ast-grep scan over vendored rules, merged JSON findings."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tokenize
import tomllib
from collections.abc import Iterator, Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, NamedTuple, TypedDict

import pathspec

SAFETY_RULES = frozenset(
    {
        "pyslop/require-safety-comment",
        "pyslop/no-any",
    }
)
SAFETY_RE = re.compile(r"#\s*SAFETY\s*:\s*\S")
REPO_SPEC = "git+https://github.com/zkewal/pyslop"
DEVIATION_RULE = "pyslop/deviation-needs-reason"
URL_RE = re.compile(r"https?://\S")
PYSLOP_KEYS = ("rules", "exclude")
TY_CONCISE_RE = re.compile(
    r"^(?P<file>.+):(?P<line>\d+):(?P<col>\d+): "
    r"(?P<severity>\w+)\[(?P<rule>[^\]]+)\] (?P<message>.*)$"
)
# SAFETY: finding mappings mix str and int values by design.
Finding = dict[str, Any]


def bundled(*parts: str) -> Path:
    """File shipped inside the package (rules, configs)."""
    return Path(__file__).resolve().parent.joinpath(*parts)


def bundled_rules_dir() -> Path:
    return bundled("rules")


def bundled_ty_config() -> Path:
    return bundled("config", "ty.toml")


def emit(text: str) -> None:
    """One line to stdout (the shipped T20 rules ban print())."""
    sys.stdout.write(text + "\n")


def emit_error(text: str) -> None:
    """One line to stderr."""
    sys.stderr.write(text + "\n")


def walk_up(start: Path) -> Iterator[Path]:
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
    # Pinned engines install beside pyslop's interpreter; prefer them over
    # PATH, which also makes a direct `.venv/bin/pyslop` call work.
    here = str(Path(sys.executable).parent)
    binary = shutil.which(name, path=here) or shutil.which(name)
    if binary is None:
        emit_error(
            f"pyslop: {name} binary not found next to {sys.executable} or on PATH"
        )
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
    return pyslop_table(pyproject).get("exclude", [])


def safety_lines(text: str) -> set[int]:
    """Lines where an escape hatch counts as justified.

    A `# SAFETY: <reason>` comment covers its own line, and the next line
    only when it stands alone on its line. Only real comment tokens count,
    so text inside a string literal never does. Untokenizable source covers
    nothing (fail closed).
    """
    covered: set[int] = set()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return covered
    for token in tokens:
        if token.type == tokenize.COMMENT and SAFETY_RE.search(token.string):
            line = token.start[0]
            covered.add(line)
            if not token.line[: token.start[1]].strip():
                covered.add(line + 1)
    return covered


TY_SUMMARY_RE = re.compile(r"^Found (?P<count>\d+) diagnostics?$")


def _project_root(paths: list[str]) -> Path:
    """Owning project dir: nearest pyproject parent, else the working dir."""
    pyproject = nearest_pyproject(_start(paths))
    if pyproject is not None:
        return pyproject.parent
    return Path.cwd()


def _has_tool_table(pyproject: Path, name: str) -> bool:
    """True when pyproject.toml parses and has a [tool.<name>] table."""
    try:
        tool = tomllib.loads(pyproject.read_text()).get("tool", {})
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return isinstance(tool, dict) and name in tool


def _consumer_ty_configured(root: Path) -> bool:
    """True when the project opts into ty config (ty.toml or [tool.ty]).

    `.ty.toml` is deliberately not detected: ty does not support it, so
    treating it as configuration would suppress strict defaults.
    """
    return (root / "ty.toml").is_file() or _has_tool_table(
        root / "pyproject.toml", "ty"
    )


def run_ty(paths: list[str]) -> list[Finding] | None:
    """Run ty; None means the runner itself failed.

    Consumer config wins: when the owning project has ty.toml or [tool.ty],
    ty runs under its own discovery (`--project`) with no extra flags, so
    the consumer's Python floor, rule levels, and overrides apply. With no
    consumer config, `--error all` keeps strict defaults (every rule,
    including ones added after the pin, is an error) while ty infers the
    floor natively from `requires-python`. No config file is ever forced:
    the bundled strict `ty.toml` is only the source `init` stamps rules
    from. A diagnostics signal whose lines do not parse is a runner
    failure, never a silent green.
    """
    binary = require_binary("ty")
    if binary is None:
        return None
    root = _project_root(paths)
    cmd = [binary, "check", "--project", str(root), "--output-format", "concise"]
    if not _consumer_ty_configured(root):
        cmd[2:2] = ["--error", "all"]
    proc = subprocess.run(
        [*cmd, *paths],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        emit_error(f"pyslop: ty check failed:\n{proc.stderr}")
        return None
    findings = []
    summary: int | None = None
    for line in proc.stdout.splitlines():
        match = TY_CONCISE_RE.match(line)
        if match is None:
            count = TY_SUMMARY_RE.match(line.strip())
            if count is not None:
                summary = int(count.group("count"))
            continue
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
    if proc.returncode == 1 and (summary is None or summary != len(findings)):
        emit_error(
            "pyslop: ty signaled diagnostics but the concise output did not "
            f"parse (summary={summary}, parsed={len(findings)}); "
            "refusing partial results:\n"
            f"{proc.stdout.strip()[:1000]}"
        )
        return None
    return findings


def shipped_ruff_config() -> Path:
    return bundled("config", "ruff.toml")


def _start(paths: list[str]) -> Path:
    """Resolved first checked path, or the working directory."""
    return Path(paths[0]).resolve() if paths else Path.cwd()


def _consumer_ruff_configured(start: Path) -> bool:
    """True when ruff would find a consumer config walking up from start.

    Mirrors ruff's own discovery: `.ruff.toml`, `ruff.toml`, or a
    pyproject with [tool.ruff]; a pyproject without it does not stop the walk.
    """
    for candidate in walk_up(start):
        if (candidate / ".ruff.toml").is_file() or (candidate / "ruff.toml").is_file():
            return True
        pyproject = candidate / "pyproject.toml"
        if pyproject.is_file() and _has_tool_table(pyproject, "ruff"):
            return True
    return False


def ruff_config_args(paths: list[str]) -> list[str]:
    """--config shipped unless the consumer has its own ruff config."""
    if _consumer_ruff_configured(_start(paths)):
        return []
    return ["--config", str(shipped_ruff_config())]


def run_ruff(paths: list[str], *, fix: bool) -> tuple[list[Finding], int]:
    """Run ruff check, mapped to findings. Returns (findings, fatal_exit)."""
    binary = require_binary("ruff")
    if binary is None:
        return [], 2
    # --force-exclude: pre-commit passes file names, and ruff otherwise
    # drops the consumer's exclude for explicitly named files.
    cmd = [
        binary,
        "check",
        "--output-format",
        "json",
        "--force-exclude",
        *ruff_config_args(paths),
    ]
    if fix:
        cmd.append("--fix")
    proc = subprocess.run([*cmd, *paths], capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        emit_error(f"pyslop: ruff failed:\n{proc.stderr}")
        return [], 2
    try:
        raw = json.loads(proc.stdout if proc.stdout.strip() else "[]")
    except json.JSONDecodeError:
        emit_error(f"pyslop: could not parse ruff output:\n{proc.stderr}")
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
# Exclude globs are gitignore-style: `src/**` crosses directories.
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


def _init_rev() -> str:
    """Pinned pyslop release for generated files: installed version, else main.

    Never the consumer's git state: `git describe` in the target repo stamps
    unrelated consumer tags (e.g. v2.229.0) into the hook/workflow pin.
    """
    release = _pyslop_version()
    return f"v{release}" if release != "unknown" else "main"


def _pre_commit_entry(rev: str) -> str:
    return (
        "\n".join(
            [
                "  - repo: local",
                "    hooks:",
                "      - id: pyslop",
                "        name: pyslop",
                (
                    "        entry: uv tool run "
                    f"--from {REPO_SPEC}@{rev} "
                    "pyslop check --no-ty"
                ),
                "        language: system",
                "        types: [python]",
                "        pass_filenames: true",
            ]
        )
        + "\n"
    )


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
      # ty resolves imports from the project's .venv. Swap in your own
      # install step if the project does not use uv.
      - name: Install project dependencies
        run: uv sync
      - name: Check for slop
        run: uv tool run --from {REPO_SPEC}@{rev} pyslop check
"""


def _write_hook(base: Path, rev: str) -> None:
    hook = base / ".pre-commit-config.yaml"
    if hook.is_file():
        existing = hook.read_text()
        if "pyslop" in existing:
            emit(f"pyslop: {hook} already present, skipping")
        elif "repos:" in existing:
            _append_block(hook, _pre_commit_entry(rev))
            emit(f"pyslop: added hook to {hook}")
        else:
            emit(f"pyslop: {hook} has no repos:, skipping")
    else:
        hook.write_text("repos:\n" + _pre_commit_entry(rev))
        emit(f"pyslop: wrote {hook}")


def _write_workflow(base: Path, rev: str) -> None:
    workflow = base / ".github" / "workflows" / "pyslop.yml"
    if workflow.is_file():
        emit(f"pyslop: {workflow} already present, skipping")
    else:
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(_workflow_text(rev))
        emit(f"pyslop: wrote {workflow}")


def _ty_rules_block() -> str:
    """Shipped strict ty rules as [tool.ty.rules]; the floor stays native.

    No `[environment]` is stamped: ty infers the floor from the consumer's
    `requires-python`, so no PEP440 parsing is needed here.
    """
    data = tomllib.loads(bundled_ty_config().read_text())
    rules = data.get("rules", {})
    lines = ["[tool.ty.rules]"]
    lines.extend(f'{key} = "{rules[key]}"' for key in sorted(rules))
    return "\n".join(lines) + "\n"


def init_command(root: str) -> int:
    base = Path(root).resolve()
    vendored = base / "tools" / "pyslop" / "rules"
    if vendored.is_dir():
        emit(f"pyslop: {vendored} already present, skipping")
    else:
        shutil.copytree(bundled_rules_dir(), vendored)
        emit(f"pyslop: vendored rules to {vendored}")
    pyproject = base / "pyproject.toml"
    try:
        tool = (
            tomllib.loads(pyproject.read_text()).get("tool", {})
            if pyproject.is_file()
            else {}
        )
    except tomllib.TOMLDecodeError as exc:
        emit_error(f"pyslop: cannot parse {pyproject}: {exc}")
        return 2
    for key, block, own_files in (
        ("pyslop", PYSLOP_BLOCK, ()),
        (
            "ruff",
            _embed_toml(shipped_ruff_config(), "tool.ruff"),
            (".ruff.toml", "ruff.toml"),
        ),
        ("ty", _ty_rules_block(), ("ty.toml",)),
    ):
        # The tool reads its own file ahead of pyproject, so a block here would be dead.
        own = next((name for name in own_files if (base / name).is_file()), None)
        if own is not None:
            emit(f"pyslop: {own} already present, skipping [tool.{key}]")
        elif key in tool:
            emit(f"pyslop: [tool.{key}] already present, skipping")
        else:
            _append_block(pyproject, block)
            emit(f"pyslop: added [tool.{key}] to {pyproject}")
    rev = _init_rev()
    _write_hook(base, rev)
    _write_workflow(base, rev)
    return 0


def has_reason_comment(lines: list[str], lineno: int) -> bool:
    """True when the line directly above is a comment containing a URL."""
    prev = lines[lineno - 2] if lineno >= 2 else ""
    stripped = prev.strip()
    return stripped.startswith("#") and bool(URL_RE.search(stripped))


def deviation_finding(config: Path, line: int, col: int, message: str) -> Finding:
    return {
        "engine": "pyslop",
        "rule": DEVIATION_RULE,
        "file": str(config),
        "line": line,
        "col": col,
        "message": message,
        "fix_hint": (
            "Add a TOML comment on the line directly above "
            "with a reason and an issue URL."
        ),
        "severity": "error",
    }


class _Disable(NamedTuple):
    """One rule disable found in a parsed config."""

    key: str  # TOML key as written: rule id, glob, or unknown pyslop key
    value: str | None  # value on the key's line, None when it is a list/table
    message: str
    needs_reason: bool = True  # False: an error even with a reason comment


def _table(data: object, *keys: str) -> dict[str, object]:
    """Nested TOML table at keys, or {} when any level is missing or not a table."""
    for key in keys:
        if not isinstance(data, dict):
            return {}
        data = data.get(key)
    return {str(k): v for k, v in data.items()} if isinstance(data, dict) else {}


def _pyslop_disables(pyslop: dict[str, object]) -> Iterator[_Disable]:
    for key in pyslop:
        if key not in PYSLOP_KEYS:
            yield _Disable(
                key,
                None,
                f'Unknown [tool.pyslop] key "{key}" '
                '(only "rules" and "exclude" are supported).',
                needs_reason=False,
            )
    for rule, value in _table(pyslop, "rules").items():
        level = str(value).lower()
        if level not in ("off", "warn", "error"):
            yield _Disable(
                rule,
                str(value),
                f'Rule "{rule}" has unknown level "{value}" '
                '(use "off", "warn", or "error").',
                needs_reason=False,
            )
        elif "/" not in rule or rule.startswith("ty/") or rule == DEVIATION_RULE:
            yield _Disable(
                rule,
                str(value),
                f'"{rule}" cannot be set in [tool.pyslop.rules]: it only '
                "applies to ast-grep rules. Configure ruff and ty rules in "
                "their own sections.",
                needs_reason=False,
            )
        elif level == "off":
            yield _Disable(
                rule, str(value), f'Rule "{rule}" is turned off without a reason.'
            )


def _ruff_disables(ruff: dict[str, object]) -> Iterator[_Disable]:
    for path in (
        ("lint", "per-file-ignores"),
        ("lint", "extend-per-file-ignores"),
        ("per-file-ignores",),
        ("extend-per-file-ignores",),
    ):
        for glob in _table(ruff, *path):
            yield _Disable(
                glob,
                None,
                f'per-file-ignores entry for "{glob}" '
                "needs a reason and an issue link.",
            )


def _ty_rule_disables(rules: dict[str, object], where: str) -> Iterator[_Disable]:
    for rule, value in rules.items():
        if str(value).lower() in ("warn", "ignore"):
            yield _Disable(
                rule,
                str(value),
                f'{where} sets "{rule}" to "{value}" without a reason.',
            )


def _ty_disables(ty: dict[str, object]) -> Iterator[_Disable]:
    yield from _ty_rule_disables(_table(ty, "rules"), "ty rules")
    overrides = ty.get("overrides")
    for override in overrides if isinstance(overrides, list) else []:
        yield from _ty_rule_disables(_table(override, "rules"), "ty override")


def _config_disables(config: Path, data: dict[str, object]) -> Iterator[_Disable]:
    """Disables in one parsed config, by file kind."""
    if config.name == "pyproject.toml":
        yield from _pyslop_disables(_table(data, "tool", "pyslop"))
        yield from _ruff_disables(_table(data, "tool", "ruff"))
        yield from _ty_disables(_table(data, "tool", "ty"))
    elif config.name == "ty.toml":
        yield from _ty_disables(data)
    else:
        yield from _ruff_disables(data)


def _locate(
    lines: list[str], disable: _Disable, used: set[tuple[int, int]]
) -> tuple[int, int]:
    """(line, col) of the first unused `key = [value]` spot, else (1, 1).

    tomllib gives no positions, so this finds the key text. It handles
    tables, dotted keys, and inline tables. Where a key repeats, the first
    unused spot in file order wins.
    """
    value = (
        "" if disable.value is None else rf"""\s*["']{re.escape(disable.value)}["']"""
    )
    pattern = re.compile(
        rf"""(?:^|[\s{{.,])(?P<key>(["']?){re.escape(disable.key)}\2)\s*={value}"""
    )
    for lineno, raw in enumerate(lines, start=1):
        if raw.lstrip().startswith("#"):
            continue
        for match in pattern.finditer(raw):
            spot = (lineno, match.start("key") + 1)
            if spot not in used:
                used.add(spot)
                return spot
    return 1, 1


def check_config_deviations(config: Path) -> list[Finding]:
    """Flag unjustified rule disables in one config file.

    Parsed with tomllib, so every TOML spelling of a disable counts:
    - pyproject.toml: `[tool.pyslop.rules]` set to "off", ruff
      per-file-ignores, and ty rules or overrides set to "warn"/"ignore".
      Unknown `[tool.pyslop]` keys are errors too.
    - ruff.toml / .ruff.toml: per-file-ignores.
    - ty.toml: rules or overrides set to "warn"/"ignore".
    Justified means the line directly above is a comment with a URL.
    """
    try:
        text = config.read_text()
        data = tomllib.loads(text)
    except (OSError, tomllib.TOMLDecodeError):
        return []
    lines = text.splitlines()
    used: set[tuple[int, int]] = set()
    findings: list[Finding] = []
    for disable in _config_disables(config, data):
        line, col = _locate(lines, disable, used)
        if disable.needs_reason and has_reason_comment(lines, line):
            continue
        findings.append(deviation_finding(config, line, col, disable.message))
    return findings


class PyslopConfig(TypedDict, total=False):
    """Parsed [tool.pyslop] block: severity overrides and exclude globs."""

    rules: dict[str, str]
    exclude: list[str]


def pyslop_table(pyproject: Path) -> PyslopConfig:
    """Parsed [tool.pyslop] table, validated at the boundary, or {} when absent."""
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    tool = data.get("tool", {})
    table = tool.get("pyslop", {}) if isinstance(tool, dict) else {}
    if not isinstance(table, dict):
        return {}
    out: PyslopConfig = {}
    rules = table.get("rules")
    if isinstance(rules, dict):
        out["rules"] = {str(key): str(value) for key, value in rules.items()}
    exclude = table.get("exclude")
    if isinstance(exclude, list):
        out["exclude"] = [e for e in exclude if isinstance(e, str)]
    return out


def _exclude_spec(project: Path, patterns: list[str]) -> pathspec.PathSpec | None:
    """Gitignore-style matcher for excludes; loud, never a silent fallback."""
    try:
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    except ValueError as exc:
        emit_error(f"pyslop: bad exclude glob in {project}: {exc}")
        return None


def _is_excluded(rel_posix: str, spec: pathspec.PathSpec | None) -> bool:
    """True when an exclude glob covers a project-relative path.

    Single gitignore matcher, no legacy OR arm: `src/**` crosses directories,
    `!` reincludes, and a bad glob excludes nothing (loud).
    """
    return spec is not None and spec.match_file(rel_posix)


def apply_pyslop_config(findings: list[Finding]) -> list[Finding]:
    """Apply [tool.pyslop] rules severities (ast-grep only) and excludes."""
    CacheKey = tuple[dict[str, str], list[str], pathspec.PathSpec | None]
    cache: dict[Path | None, CacheKey] = {}
    kept = []
    for finding in findings:
        path = Path(finding["file"])
        project = nearest_pyproject(path)
        if project not in cache:
            table = pyslop_table(project) if project is not None else {}
            exclude = pyslop_excludes(project) if project is not None else []
            spec = _exclude_spec(project, exclude) if project is not None else None
            cache[project] = (table.get("rules", {}), exclude, spec)
        rules, exclude, spec = cache[project]
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
            rel = absolute.resolve()
            if not rel.is_relative_to(base):
                kept.append(finding)
                continue
            if _is_excluded(rel.relative_to(base).as_posix(), spec):
                continue
        kept.append(finding)
    return kept


def format_command(paths: list[str]) -> int:
    binary = require_binary("ruff")
    if binary is None:
        return 2
    return subprocess.run([binary, "format", *paths], check=False).returncode


def print_text(findings: list[Finding]) -> None:
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
        rule = str(finding["rule"])
        label = rule if "/" in rule else f"{finding['engine']}/{rule}"
        emit(f"{loc} {label} {finding['message']}")
    total = len(ordered)
    errors = sum(1 for finding in ordered if finding["severity"] == "error")
    emit(
        f"{total} finding{'s' if total != 1 else ''} "
        f"({errors} error{'s' if errors != 1 else ''})"
    )


def _escape_github_data(text: str) -> str:
    """Escape a workflow-command message: percent, CR, LF (percent first)."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_github_property(text: str) -> str:
    """Escape a workflow-command property: data escapes plus colon, comma."""
    escaped = _escape_github_data(text)
    return escaped.replace(":", "%3A").replace(",", "%2C")


def print_github(findings: list[Finding]) -> None:
    """One GitHub workflow command per finding, sorted exactly like text.

    `error` for error severity, `warning` for anything else. No summary line:
    a summary is not a workflow command; the exit code carries the signal.
    """
    ordered = sorted(
        findings,
        key=lambda f: (f["file"], f["line"], f["col"], f["engine"], f["rule"]),
    )
    for finding in ordered:
        command = "error" if finding["severity"] == "error" else "warning"
        file = _escape_github_property(str(finding["file"]))
        line = _escape_github_property(str(finding["line"]))
        col = _escape_github_property(str(finding["col"]))
        title = _escape_github_property(f"{finding['engine']} ({finding['rule']})")
        message = _escape_github_data(str(finding["message"]))
        emit(f"::{command} file={file},line={line},col={col},title={title}::{message}")


def _findings_exit(findings: list[Finding]) -> int:
    """Shared exit rule: 1 when any finding is error severity, else 0."""
    return 1 if any(f["severity"] == "error" for f in findings) else 0


class _RenderInputError(Exception):
    """Findings JSON on stdin is unusable: fail closed, never partial."""


def _render_finding(item: object, index: int) -> Finding:
    """One validated finding from a decoded JSON list, else _RenderInputError."""
    if not isinstance(item, dict):
        detail = f"finding {index} is not an object"
        raise _RenderInputError(detail)
    for key in ("engine", "rule", "file", "message", "severity"):
        if not isinstance(item.get(key), str):
            detail = f"finding {index} has no text field {key!r}"
            raise _RenderInputError(detail)
    line = item.get("line")
    col = item.get("col")
    if isinstance(line, bool) or isinstance(col, bool):
        detail = f"finding {index} has no integer line/col"
        raise _RenderInputError(detail)
    if not isinstance(line, int) or not isinstance(col, int):
        detail = f"finding {index} has no integer line/col"
        raise _RenderInputError(detail)
    return item


def _read_render_findings(raw: str) -> list[Finding]:
    """Parse and validate one findings JSON array, else _RenderInputError."""
    try:
        data: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        detail = f"invalid JSON: {exc}"
        raise _RenderInputError(detail) from exc
    if not isinstance(data, list):
        detail = "top level is not a JSON list"
        raise _RenderInputError(detail)
    return [_render_finding(item, index) for index, item in enumerate(data)]


def render_command(format: str) -> int:
    """Render findings JSON piped on stdin. Shares check's exit rule."""
    try:
        findings = _read_render_findings(sys.stdin.read())
    except _RenderInputError as exc:
        emit_error(f"pyslop: render: {exc}; refusing partial results.")
        return 2
    if format == "json":
        emit(json.dumps(findings, indent=2))
    elif format == "github":
        print_github(findings)
    else:
        print_text(findings)
    return _findings_exit(findings)


class _GrepOutputError(Exception):
    """Malformed engine output or unreadable source: fail closed, never partial."""


def _preview(item: object) -> str:
    """Short repr for diagnostics (kept out of `raise` sites for TRY003)."""
    return f"{item!r}"[:200]


def _grep_finding(item: object, sources: dict[str, set[int]]) -> Finding | None:
    """One finding, or None when SAFETY-justified. Raises _GrepOutputError."""
    if not isinstance(item, dict):
        detail = f"finding is not an object: {_preview(item)}"
        raise _GrepOutputError(detail)
    try:
        start = item["range"]["start"]
        raw_line = start["line"]
        raw_col = start["column"]
    except (KeyError, TypeError) as exc:
        detail = f"finding has no range/start: {_preview(item)}"
        raise _GrepOutputError(detail) from exc
    if not isinstance(raw_line, int) or not isinstance(raw_col, int):
        detail = f"finding range is not integer: {_preview(item)}"
        raise _GrepOutputError(detail)
    line, col = raw_line + 1, raw_col + 1
    rule = item.get("ruleId", "")
    file = item.get("file", "")
    if not isinstance(rule, str) or not isinstance(file, str):
        detail = f"finding id/file is not text: {_preview(item)}"
        raise _GrepOutputError(detail)
    if rule in SAFETY_RULES:
        if file not in sources:
            try:
                sources[file] = safety_lines(Path(file).read_text())
            except OSError as exc:
                detail = f"cannot read source for finding: {file} ({exc})"
                raise _GrepOutputError(detail) from exc
        if line in sources[file]:
            return None
    return {
        "engine": "ast-grep",
        "rule": rule,
        "file": file,
        "line": line,
        "col": col,
        "message": item.get("message") or "",
        "fix_hint": item.get("note") or "",
        "severity": item.get("severity") or "error",
    }


def _decode_grep_output(proc: subprocess.CompletedProcess[str]) -> Sequence[object]:
    """Validated JSON list from ast-grep stdout. Raises _GrepOutputError."""
    text = proc.stdout.strip()
    if not text:
        if proc.returncode == 1:
            detail = "signaled findings but emitted no JSON"
            raise _GrepOutputError(detail)
        return []
    try:
        raw: object = json.loads(text)
    except json.JSONDecodeError as exc:
        detail = f"invalid JSON: {exc}"
        raise _GrepOutputError(detail) from exc
    if not isinstance(raw, list):
        detail = "top level is not a JSON list"
        raise _GrepOutputError(detail)
    if proc.returncode == 1 and not raw:
        # Findings signaled but the payload is empty: fail closed. (This
        # checks the raw payload so SAFETY-filtered runs still exit 0.)
        detail = "signaled findings but the payload is empty"
        raise _GrepOutputError(detail)
    return raw


def run_ast_grep(paths: list[str]) -> tuple[list[Finding], int]:
    """Run ast-grep scan with SAFETY filtering. Returns (findings, fatal_exit).

    Fail closed: ast-grep exits 0 (clean) or 1 (findings). Any other exit,
    a findings signal with no JSON payload, or malformed items are a runner
    failure (exit 2), never a silent green.
    """
    binary = require_binary("ast-grep")
    if binary is None:
        return [], 2
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
    if proc.returncode not in (0, 1):
        emit_error(
            "pyslop: ast-grep scan failed "
            f"(exit {proc.returncode}):\n{proc.stderr.strip()}"
        )
        return [], 2
    try:
        raw = _decode_grep_output(proc)
    except _GrepOutputError as exc:
        emit_error(f"pyslop: ast-grep: {exc}; refusing partial results.")
        return [], 2
    sources: dict[str, set[int]] = {}
    findings: list[Finding] = []
    try:
        for item in raw:
            finding = _grep_finding(item, sources)
            if finding is not None:
                findings.append(finding)
    except _GrepOutputError as exc:
        emit_error(f"pyslop: ast-grep: {exc}; refusing partial results.")
        return [], 2
    return findings, 0


CONFIG_NAMES = ("pyproject.toml", "ruff.toml", ".ruff.toml", "ty.toml")
SKIP_DIRS = frozenset({"node_modules", "__pycache__", "site-packages"})


def _configs_in(directory: Path) -> Iterator[Path]:
    for name in CONFIG_NAMES:
        if (directory / name).is_file():
            yield directory / name


def _deviation_configs(paths: list[str]) -> list[Path]:
    """Every config that can disable a rule for the checked paths, deduped.

    Walks up from each path to its project root (nearest pyproject), and
    down through checked directories, so a subpackage in a monorepo cannot
    turn a rule off unseen when the root is checked.
    """
    seen: dict[Path, None] = {}
    for raw_path in paths:
        start = Path(raw_path).resolve()
        for directory in walk_up(start):
            seen.update(dict.fromkeys(_configs_in(directory)))
            if (directory / "pyproject.toml").is_file():
                break
        if start.is_dir():
            for root, dirs, _ in os.walk(start):
                dirs[:] = [
                    d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS
                ]
                seen.update(dict.fromkeys(_configs_in(Path(root))))
    return list(seen)


def _run_engines(
    paths: list[str], *, fix: bool, no_ty: bool, only: str | None
) -> tuple[list[Finding], int]:
    """Run the selected engines. Returns (findings, fatal_exit)."""
    findings: list[Finding] = []
    # ruff first: --fix rewrites files, and later engines must see the result.
    if only in (None, "ruff"):
        ruff_findings, fatal = run_ruff(paths, fix=fix)
        if fatal:
            return findings, fatal
        findings.extend(ruff_findings)
    if only in (None, "ast-grep"):
        grep_findings, fatal = run_ast_grep(paths)
        if fatal:
            return findings, fatal
        findings.extend(grep_findings)
    if only in (None, "ty") and not no_ty:
        ty_findings = run_ty(paths)
        if ty_findings is None:
            return findings, 2
        findings.extend(ty_findings)
    if only in (None, "pyslop"):
        for config in _deviation_configs(paths):
            findings.extend(check_config_deviations(config))
    return findings, 0


def _display_path(finding: Finding) -> Finding:
    """File relative to the working dir when under it, else absolute.

    Engines disagree (ruff reports absolute paths, ast-grep relative), so
    one form keeps grouping, sorting, and GitHub annotations consistent.
    """
    path = Path(finding["file"]).resolve()
    cwd = Path.cwd().resolve()
    shown = path.relative_to(cwd) if path.is_relative_to(cwd) else path
    return {**finding, "file": str(shown)}


def check_command(
    paths: list[str],
    format: str,
    *,
    fix: bool,
    no_ty: bool,
    only: str | None = None,
) -> int:
    findings, fatal = _run_engines(paths, fix=fix, no_ty=no_ty, only=only)
    if fatal:
        return fatal
    findings = [_display_path(f) for f in apply_pyslop_config(findings)]
    if format == "json":
        emit(json.dumps(findings, indent=2))
    elif format == "github":
        print_github(findings)
    else:
        print_text(findings)
    return _findings_exit(findings)


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
    check.add_argument("--format", choices=["text", "json", "github"], default="text")
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
    render = sub.add_parser("render", help="Render findings JSON piped on stdin.")
    render.add_argument("--format", choices=["text", "json", "github"], default="text")
    init_cmd = sub.add_parser("init", help="Vendor rules and write configs.")
    init_cmd.add_argument(
        "path", nargs="?", default=".", help="Repo root (default: .)."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        if args.only == "ty" and args.no_ty:
            emit_error("pyslop: --only ty with --no-ty runs nothing")
            return 2
        if args.fix and args.only not in (None, "ruff"):
            emit_error(f"pyslop: --fix only applies to ruff, not --only {args.only}")
            return 2
        return check_command(
            args.paths, args.format, fix=args.fix, no_ty=args.no_ty, only=args.only
        )
    if args.command == "format":
        return format_command(args.paths)
    if args.command == "render":
        return render_command(args.format)
    if args.command == "init":
        return init_command(args.path)
    raise AssertionError(args.command)  # unreachable, command is required
