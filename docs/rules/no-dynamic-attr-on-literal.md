# no-dynamic-attr-on-literal

**Rule id:** `pyslop/no-dynamic-attr-on-literal` · **Engine:** ast-grep · **Severity:** error

## Rationale

`getattr(x, "name")` with a string literal name is just `x.name` with the
evidence removed: the type checker cannot verify the attribute exists, so a
rename breaks silently at runtime instead of loudly at check time. If the
attribute is truly dynamic, the name should come from a variable (a caller,
config, or protocol) — and then this rule does not fire. A literal name
means the author knew the attribute statically and should have written it
statically.

## Bad

```python
name = getattr(obj, "name")
defaulted = getattr(obj, "name", None)
present = hasattr(obj, "name")
setattr(obj, "name", name)
```

Each line above is one finding: a dynamic lookup with a literal name,
including the three-argument `getattr` with a default.

## Good

```python
value = getattr(obj, name)  # truly dynamic: allowed
defaulted = getattr(obj, name, None)
present = hasattr(obj, name)
setattr(obj, name, value)
direct = obj.name  # literal name written statically: checked
```

A variable (non-literal) name passes, as does plain `obj.name`.

## Notes

- Both quote styles (`"name"`, `'name'`) are flagged. f-strings
  (`getattr(obj, f"{name}")`) are treated as dynamic and pass.
- `builtins.getattr` and expressions like `"a" + "b"` are out of scope.
