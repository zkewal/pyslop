# no-isinstance-ladder

**Rule id:** `pyslop/no-isinstance-ladder` · **Engine:** ast-grep · **Severity:** error

## Rationale

Three or more `isinstance()` checks on the same value in one `if`/`elif`
chain means the function is dispatching on type instead of parsing at the
boundary. Each new type adds another branch, and none of the branches is
checked by the type system — a value of an unexpected type slides through to
whatever the chain falls off the end of. A pydantic model or a `match`
statement puts the contract in one place where the checker can verify it.

Two branches are allowed: a single type-narrowing check (or a pair) is often
the honest shape of the code. The third branch is where the ladder starts.

## Bad

```python
def handle(value):
    if isinstance(value, int):
        return "int"
    elif isinstance(value, str):
        return "str"
    elif isinstance(value, float):
        return "float"
    return "other"
```

One finding on the `if` statement: three `isinstance()` checks on `value`
in one chain.

## Good

```python
def handle_two(value):
    if isinstance(value, int):
        return "int"
    elif isinstance(value, str):
        return "str"
    return "other"


def handle_mixed(value, other):
    if isinstance(value, int):
        return 1
    elif isinstance(other, str):  # different subject: not a ladder
        return 2
    elif isinstance(value, float):
        return 3
    return 0
```

Two branches pass, and branches on different subjects pass — the rule only
fires when three or more checks share the same variable name in one chain.

## Notes

- Only checks in the branch *conditions* count; an `isinstance()` call in a
  branch body does not. Compound conditions (`isinstance(x, int) or ...`,
  `not isinstance(...)`) are not matched — a known limitation, kept simple
  on purpose.
- A chain of four or more branches is still one finding on the `if`.
