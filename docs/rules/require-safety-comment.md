# require-safety-comment

**Rule id:** `pyslop/require-safety-comment` · **Engine:** ast-grep · **Severity:** error

## Rationale

`cast()`, `# type: ignore[...]`, `# ty: ignore[...]`, and explicit `Any`
annotations all destroy type evidence: after they are used, neither the type
checker nor the next reader can verify what the value really is. Sometimes an
escape hatch is genuinely needed (dynamic boundaries, third-party stubs that
lie). When it is, the reason must be written down exactly where the hatch is,
or the justification rots while the suppression lives forever.

Requiring a `# SAFETY: <reason>` comment forces the author to state what was
checked by hand instead of the checker, so reviewers can judge whether the
trade-off still holds.

## Bad

```python
from typing import Any, cast

user_id = cast(int, raw)  # why is this sound? nobody knows
config: Any = load_config()
row = query()  # type: ignore[union-attr]
```

Each line above is one finding: an escape hatch with no justification.

## Good

```python
from typing import Any, cast

user_id = cast(int, raw)  # SAFETY: raw matches ^\d+$ per route regex
config: Any = load_config()  # SAFETY: validated against ConfigSchema below
# SAFETY: sqlalchemy returns ScalarResult here despite the stubs
row = query()  # type: ignore[union-attr]
```

A `# SAFETY: <non-empty reason>` on the same line or the immediately
preceding line satisfies the rule. A `SAFETY` comment separated by a blank
line does not count. (`from typing import Any` itself is never flagged, only
uses of `Any`.)

## Notes

- The ast-grep rule flags every escape hatch; the `SAFETY` exemption is
  applied by the `pyslop check` runner by reading the source lines, because
  same-or-previous-line proximity is not expressible in ast-grep YAML.
- Bare `# type: ignore` (no brackets) is covered too: it still needs
  a `SAFETY` reason. Flagging fully bare suppressions is a separate rule.
