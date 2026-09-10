# ty config

**Shipped config:** `src/pyslop/config/ty.toml` (bundled in the package, so it
works with no vendored rules). Strict: every ty rule at `error`. The
`python-version = "3.12"` inside it describes the tool's own floor; it is
never forced onto consumers (see below).

## Consumer config wins

`pyslop check` runs `ty check --project <owning project>` and lets ty
discover configuration the supported way. When the project has `ty.toml` or
`[tool.ty]` in `pyproject.toml`, that config applies as-is: the consumer's
Python floor, rule levels, and overrides are honored, and no `--error all`
is forced over them. (Unjustified downgrades are still reported by
`pyslop/deviation-needs-reason`.) `.ty.toml` is not a ty-supported name and
is ignored on purpose — honoring it would silently suppress strict
defaults.

With no consumer ty config, pyslop adds only `--error all`: every rule,
including ones added after the pin, is an error, while ty infers the floor
natively from `requires-python`. No config file is ever forced, so the
shipped strict `ty.toml` doubles only as the source `init` stamps rules
from. `pyslop init` writes `[tool.ty.rules]` (strict, no `[environment]`),
leaving the floor to native inference.

A diagnostics signal whose concise lines do not parse is a runner failure
(exit 2), never a silent green: the reported count is cross-checked against
parsed findings.

## Beta status

ty is pre-1.0 (`0.0.80`, pinned exactly in `pyproject.toml` and `uv.lock`).
Its rule set still grows release to release. When the pin is bumped,
regenerate the `[rules]` list in `src/pyslop/config/ty.toml` from
`ty explain rule` so the shipped file keeps naming every rule explicitly.

## mypy coexists untouched

pyslop never reads, writes, or invokes `[tool.mypy]` — or the `mypy` binary.
A consumer already on mypy keeps its config and CI step exactly as they are
and runs both side by side. `pyslop check` leaves the consumer's
`pyproject.toml` unchanged.

## Skipping ty

`pyslop check --no-ty` skips the ty engine (pre-commit speed). ruff and
ast-grep still run.
