# Shipped ruff config

Pyslop ships a curated ruff config at `src/pyslop/config/ruff.toml` (bundled in
the wheel like the rules). `pyslop check` passes it via `ruff --config` when
the nearest `pyproject.toml` has no `[tool.ruff]` section; a consumer config
always wins when present. Preview off, `target-version = "py312"`.

Ruff carries the rules it already has so pyslop only adds the gaps via
ast-grep. Families selected:

- **E, W** (pycodestyle errors/warnings): basic hygiene, keeps diffs clean.
- **F** (pyflakes): unused imports/names, undefined names. Dead code is where
  slop hides.
- **I** (isort): sorted imports. Required for `--fix` to be deterministic.
- **UP** (pyupgrade): modern syntax for the floor version (`X | None`, `match`
  idioms). Old idioms invite untyped patterns.
- **B** (flake8-bugbear): likely bugs (mutable defaults, unused loop vars).
- **ANN** (flake8-annotations): every parameter and return annotated. This is
  Python's `noImplicitAny`: TypeScript repos get it from the compiler, Python
  has no type checker default that requires it, so ruff carries it. An
  unannotated parameter is *no evidence*, which is exactly what pyslop is
  about. Includes **ANN401**, which bans `Any`; `pyslop/no-any` independently
  requires SAFETY for explicit `Any`. A legacy adopter that cannot afford
  annotations yet leaves `ANN0`/`ANN2` out of its *own* `select` with a reason
  and an issue link; the shipped default stays strict.
- **BLE** (flake8-blind-except): no blind `except Exception` / bare `except`.
- **TRY** (tryceratops) minus **TRY003**: `raise` without `from`, verbose
  logging in handlers. TRY003 (long message inside `raise`) is style and is
  ignored in the shipped config.
- **S110, S112** (flake8-bandit): `try/except/pass` and `try/except/continue`
  — silent swallowing. (Full `S` is off: bandit needs per-repo tuning.)
- **ERA** (eradicate): dead commented-out code.
- **ARG** (flake8-unused-arguments): unused function arguments, including
  `**kwargs` no one reads.
- **FBT** (flake8-boolean-trap): boolean positional args/traps in signatures.
- **PLR09** (pylint refactor): too many branches/returns/statements — long
  functions accumulate untyped shortcuts.
- **C90** (mccabe): complexity cap, same reason as PLR09.
- **RET** (flake8-return): redundant `else: return`, missing explicit return.
- **SIM** (flake8-simplify): `isinstance` nests and other simplifiable shapes
  that hide data contracts.
- **PERF** (perflint): list-building anti-patterns.
- **FURB** (refurb): modern idioms the type checker understands better.
- **PIE** (flake8-pie): miscellaneous correctness (`unnecessary-pass`, …).
- **PGH** (pygrep-hooks): e.g. **PGH003** bans blanket `# type: ignore`
  without a code — pairs with the SAFETY rule.
- **RUF** (ruff-specific): e.g. **RUF100** flags unused `noqa`, so
  suppressions cannot linger after the violation is gone.
- **T20** (flake8-print): no `print` in shipped code — use logging.
- **TD** (flake8-todo): `TODO`/`FIXME` stay visible as findings, never silent.
- **FIX** (flake8-fixme): same as TD for `FIXME`/`XXX`/`HACK`.

Deliberately **not** selected: `D` (docstring presence and shape is a per-repo
style rollout, not slop) and `TRY003` (exception-message style). Consumers who
want them add them to their own `[tool.ruff.lint] select`. Removed in v0.1.6
because neither speaks to type evidence. v0.1.6 also dropped `ANN0`/`ANN2`;
v0.1.7 restored them, see the ANN entry above for why.
