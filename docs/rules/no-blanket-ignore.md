# no-blanket-ignore

**Rule id:** `pyslop/no-blanket-ignore` · **Engine:** ast-grep · **Severity:** error

## Rationale

A bare `# type: ignore` or `# ty: ignore` suppresses *every* error on the
line — present and future. The next refactor can introduce a genuine type
error on the same line and the checker will stay silent. Naming the code
(`# type: ignore[union-attr]`) keeps the suppression scoped: anything else
still fails loudly.

## Bad

```python
row = query()  # type: ignore
value = coerce(raw)  # ty: ignore
```

Each line above is one finding: an ignore with no `[code]`.

## Good

```python
row = query()  # type: ignore[union-attr]
value = coerce(raw)  # ty: ignore[invalid-argument-type]
```

## Notes

- A `# SAFETY: <reason>` comment does **not** satisfy this rule. The
  `pyslop/require-safety-comment` rule still requires the justification, but
  justification is no substitute for naming the suppressed code — a bare
  ignore needs both fixes (add the code, keep the reason).
- Bare `# noqa` is deliberately out of scope here: ruff's `PGH004` already
  flags blanket `noqa`, so this rule stays silent on comments without
  `type:`/`ty:`.
- Matching is textual on the comment (`ignore` not followed by `[`), because
  ast-grep's regex engine has no lookahead. `# type: ignore  # extra words`
  is still bare and still flagged.
