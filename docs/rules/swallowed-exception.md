# swallowed-exception

**Rule id:** `pyslop/swallowed-exception` · **Engine:** ast-grep · **Severity:** error

## Rationale

An `except` handler that neither re-raises nor returns silently discards the
failure: the program continues as if nothing happened, and the next reader
cannot tell whether that was deliberate. Logging the error does not count —
a log line is not handling. If the exception is expected, say what happens
instead (`return`); if it is not, let it propagate (`raise`).

## Bad

```python
try:
    row = query()
except DBError as e:
    logger.exception("query failed")  # runs on, row unbound or stale
```

```python
for path in files:
    try:
        process(path)
    except OSError:
        continue  # which files failed? nobody knows
```

```python
try:
    x()
except ValueError:
    pass
```

Each handler above is one finding: no `raise` and no `return` anywhere in
the handler body.

## Good

```python
try:
    row = query()
except DBError:
    raise  # propagate, caller decides
```

```python
try:
    user = fetch(user_id)
except NotFound as e:
    raise UserMissing(user_id) from e  # translate, keep the chain
```

```python
def load(path: str) -> Config | None:
    try:
        return parse(path)
    except ParseError:
        return None  # caller handles None explicitly
```

A `raise` nested in control flow (`if`, `for`, `with`, a nested `try`) still
counts — the rule looks through everything except nested `def`/`class`/`lambda`
bodies, whose `raise`/`return` belong to another function.

## Notes

- `continue`, `break`, and `pass` do not satisfy the rule: the exception is
  still swallowed.
- Limitation (YAML cannot do dataflow): a `raise` inside a *nested* `try`
  inside the handler satisfies the outer handler too, even when the nested
  `try` can succeed and the original exception is lost. A nested handler that
  itself swallows is still flagged on its own.
