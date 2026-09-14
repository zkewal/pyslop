# pyslop

Deterministic anti-slop for Python. A thin runner over [ruff](https://docs.astral.sh/ruff/),
[ty](https://docs.astral.sh/ty/), and [ast-grep](https://ast-grep.github.io/) plus a vendored
set of evidence rules, in the spirit of [dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop).

Slop is code that fakes certainty or throws away type evidence: `Any`, bare `cast`, unjustified
`type: ignore`, `except` blocks that swallow, `isinstance` ladders instead of boundary parsing.
pyslop makes each of those an error unless it carries a `# SAFETY: <reason>` comment.

## Install

Install a pinned tag with `uv`; nothing else to set up:

```bash
uvx --from git+https://github.com/zkewal/pyslop@v0.1.6 pyslop --version
```

Engine versions are pinned exactly (`==` in `pyproject.toml`), so a tag
install resolves identically everywhere — `uv.lock` is not consulted for
tool installs. From a checkout, `uv sync` then `uv run pyslop ...`.

## Usage

One command returns every violation as JSON with a stable rule id and a fix hint:

```bash
pyslop check --format json          # whole project
pyslop check src tests/test_*.py    # only these paths (pre-commit stays fast)
pyslop check --fix                  # safe ruff rewrites only, never evidence rules
pyslop check --only ruff            # one engine: ast-grep | ruff | ty | pyslop
pyslop check --format github        # GitHub workflow commands (::error/::warning)
pyslop render --format github       # render findings JSON piped on stdin
pyslop format                       # ruff format
pyslop init                         # vendor rules + configs into a repo (see skills/install-pyslop)
```

Exit code is 1 when any error-severity finding exists, 0 otherwise.
`pyslop render` reads one findings JSON array from stdin and renders it with
the same formats and exit rule; `--format github` emits one `::error` or
`::warning` workflow command per finding (actions/toolkit escaping, stable
sort, no summary line).

## Rules

ruff carries what it already has ([shipped config](docs/config/ruff.md), ty runs strict
([shipped config](docs/config/ty.md)); pyslop adds the gaps as ast-grep rules:

| Rule | What it flags |
| ---- | ------------- |
| `pyslop/require-safety-comment` | `cast()`, `type:`/`ty: ignore` without `# SAFETY: <reason>` |
| `pyslop/no-any` | Explicit `Any` without `# SAFETY: <reason>` |
| `pyslop/no-blanket-ignore` | bare `type:`/`ty: ignore` without a code |
| `pyslop/swallowed-exception` | `except` handlers that neither raise nor return |
| `pyslop/no-isinstance-ladder` | 3+ `isinstance` branches on one value in one function |
| `pyslop/no-dynamic-attr-on-literal` | `getattr`/`hasattr`/`setattr` with a string-literal name |
| `pyslop/no-kwargs-passthrough` | `**kwargs` without `Unpack[SomeTypedDict]` in public signatures |
| `pyslop/no-dict-any` | `dict[str, Any]` / `Mapping[str, Any]` in signatures |
| `pyslop/no-module-mocking` | `patch("dotted.path")` / `monkeypatch.setattr("dotted.path", …)` |
| `pyslop/deviation-needs-reason` | config overrides that dodge a rule without a reason |

Each rule has rationale and bad/good examples under [docs/rules](docs/rules/).

## Deviations

Suppressions are allowed but must stay honest. Any config override that turns a rule
off for a path — `[tool.pyslop.rules]`, `[tool.ruff.lint.per-file-ignores]`,
`[[tool.ty.overrides]]` — needs a comment on the line directly above it with a reason
and an issue URL, or `pyslop check` reports `pyslop/deviation-needs-reason`:

```toml
[tool.pyslop.rules]
# Slow rollout, see https://github.com/org/repo/issues/1
"pyslop/no-isinstance-ladder" = "off"
```

Prefer `exclude` globs and per-file reasoning over broad disables. There is no
baseline file: remove one deviation per PR until none remain.

## Adoption order

Adopt one rule per PR across the repo: SAFETY comments and swallowed exceptions
first, `Any` removal last. The `install-pyslop` skill walks an agent through
`pyslop init`, the first `pyslop check`, and the diff review.
