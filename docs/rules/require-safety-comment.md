# require-safety-comment

**Rule id:** `pyslop/require-safety-comment` · **Engine:** ast-grep · **Severity:** error

## Rationale

`cast()`, `# type: ignore[...]`, and `# ty: ignore[...]` all destroy type
evidence: after they are used, neither the type checker nor the next reader can
verify what the value really is. Sometimes an escape hatch is genuinely needed
(dynamic boundaries, third-party stubs that lie). When it is, the reason must
be written down exactly where the hatch is, or the justification rots while
the suppression lives forever.

Requiring a `# SAFETY: <reason>` comment forces the author to state what was
checked by hand instead of the checker, so reviewers can judge whether the
trade-off still holds.

## Bad

```python
from typing import cast

user_id = cast(int, raw)  # why is this sound? nobody knows
row = query()  # type: ignore[union-attr]
```

Each line above is one finding: an escape hatch with no justification.

## Good

```python
from typing import cast

user_id = cast(int, raw)  # SAFETY: raw matches ^\d+$ per route regex
# SAFETY: sqlalchemy returns ScalarResult here despite the stubs
row = query()  # type: ignore[union-attr]
```

A `# SAFETY: <non-empty reason>` comment on the same line, or alone on the
immediately preceding line, satisfies the rule. A trailing SAFETY comment on
the line above covers only that line, text inside a string never counts, and
a `SAFETY` comment separated by a blank line does not count. Imports are not findings; explicit `Any` is covered by the
separate [`pyslop/no-any`](no-any.md) rule.

## Notes

- The ast-grep rule flags every escape hatch; the `SAFETY` exemption is
  applied by the `pyslop check` runner by reading the source lines, because
  same-or-previous-line proximity is not expressible in ast-grep YAML.
- Bare `# type: ignore` (no brackets) is covered too: it still needs
  a `SAFETY` reason. Flagging fully bare suppressions is a separate rule.
- `cast()` is matched bare and qualified by `typing`, `t`, `tp`, or
  `typing_extensions`. Other `.cast()` methods (polars/pyspark
  `col.cast(...)`) are not flagged. An aliased import
  (`from typing import cast as c`) is not caught: that needs alias
  resolution, which ast-grep YAML cannot do.
- Explicit `Any` is covered by [`pyslop/no-any`](no-any.md), so teams can
  adopt casts and typed ignores before taking on a large existing `Any`
  inventory.
