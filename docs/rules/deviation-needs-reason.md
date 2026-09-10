# deviation-needs-reason

**Rule id:** `pyslop/deviation-needs-reason` · **Engine:** `pyslop` (the runner
itself, not ast-grep) · **Severity:** error

## Rationale

Existing violations are handled with per-path deviations carrying an issue
link, removed one rule per PR (`docs/decisions.md`). A deviation without a
written reason and a tracking link rots: nobody knows whether it is still
needed or who owns removing it. This check polices the config files
themselves — every override that disables a rule for a path must justify
itself in place.

## What is checked

`pyslop check` reads the nearest `pyproject.toml` for each checked path and
flags:

1. `[tool.pyslop.rules]` entries set to `"off"` (table form or inline
   `rules = { ... }`, single- or multi-line, dotted `rules."id" = "off"`).
2. Every `[tool.ruff.lint.per-file-ignores]` entry (any entry ignores rules
   for those paths).
3. `[[tool.ty.overrides]]` rule downgrades to `"warn"` or `"ignore"`
   (inline or dotted form). `"error"` is not a downgrade.
4. Unknown `[tool.pyslop]` keys — only `rules` and `exclude` are supported.

Justified means the TOML line **directly above** the entry is a `#` comment
containing a URL (the issue link); the comment text is the reason. A trailing
comment on the same line does not count, and neither does a comment separated
by a blank line. Inside a multi-line inline table, each entry is judged by
the line above its own line.

## Bad

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]
```

One finding pointing at the entry line: silenced with no reason on record.

## Good

```toml
[tool.ruff.lint.per-file-ignores]
# legacy bridge, remove in https://linear.app/x/DEX-1
"tests/**" = ["S101"]
```

```toml
[tool.pyslop]
# legacy bridge for old tests: https://linear.app/x/DEX-2
rules = { "pyslop/no-module-mocking" = "off" }
```

The second example also turns that rule off: `[tool.pyslop]` severity
overrides (`error` | `warn` | `off`) apply to ast-grep findings for the
nearest project. `off` drops the findings, `warn` reports them as warnings
(exit 0). Overrides never apply to ruff/ty findings — those engines own
their config. `exclude` takes globs (relative to the `pyproject.toml`) whose
findings are dropped for every engine.

## Notes

- The finding's `file` is the `pyproject.toml` itself, `line`/`col` point at
  the offending entry.
- Only `pyproject.toml` files are read. A `ruff.toml`
  `[lint.per-file-ignores]` section is out of scope for this check.
- `--only pyslop` runs just this check; `--only ast-grep|ruff|ty` skips it.
- Unknown rule *ids* inside `rules` are ignored (only unknown *keys* of
  `[tool.pyslop]` are errors); non-`error|warn|off` severity values leave the
  finding's severity untouched.
