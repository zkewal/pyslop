# no-any

**Rule id:** `pyslop/no-any` · **Engine:** ast-grep · **Severity:** error

## Rationale

An explicit `Any` annotation discards the type evidence the checker could use
to catch mistakes. Sometimes a dynamic boundary really accepts any value. When
it does, the reason belongs next to the annotation so the choice can be
reviewed and revisited.

## Bad

```python
from typing import Any

config: Any = load_config()


def decode(raw: bytes) -> Any: ...
```

Each explicit use of `Any` is one finding unless it has a SAFETY reason.

## Good

```python
from typing import Any

config: Any = load_config()  # SAFETY: validated against ConfigSchema below


# SAFETY: this boundary accepts every JSON value by contract
def decode(raw: bytes) -> Any: ...
```

A `# SAFETY: <non-empty reason>` on the same line or the immediately
preceding line satisfies the rule. A `SAFETY` comment separated by a blank
line does not count. The import that provides `Any` is never flagged.

## Notes

- The ast-grep rule flags every explicit use of `Any`; the SAFETY exemption is
  applied by the `pyslop check` runner by reading the source lines, because
  same-or-previous-line proximity is not expressible in ast-grep YAML.
- `pyslop/require-safety-comment` covers casts and typed ignores. Keeping the
  rules separate lets teams adopt those sharper escape hatches before taking
  on a large existing `Any` inventory.
