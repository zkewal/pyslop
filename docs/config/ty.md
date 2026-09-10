# ty config

**Shipped config:** `src/pyslop/config/ty.toml` (bundled in the package, so it
works with no vendored rules). Strict: every ty rule at `error`,
`python-version = "3.12"`. `pyslop check` passes it via
`ty check --config-file <bundled> --error all`; the `--error all` keeps rules
added after the pin at error too.

## Beta status

ty is pre-1.0 (`0.0.80`, pinned in `uv.lock`; `pyproject.toml` floors
`ty>=0.0.80` like the other engines). Its rule set still grows release to
release. When the pin is bumped, regenerate the `[rules]` list in
`src/pyslop/config/ty.toml` from `ty explain rule` so the shipped file keeps
naming every rule explicitly.

## mypy coexists untouched

pyslop never reads, writes, or invokes `[tool.mypy]` — or the `mypy` binary.
A consumer already on mypy keeps its config and CI step exactly as they are
and runs both side by side. `pyslop check` leaves the consumer's
`pyproject.toml` unchanged.

## Skipping ty

`pyslop check --no-ty` skips the ty engine (pre-commit speed). ruff and
ast-grep still run.
