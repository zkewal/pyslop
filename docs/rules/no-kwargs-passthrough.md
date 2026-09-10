# no-kwargs-passthrough

**Rule id:** `pyslop/no-kwargs-passthrough` · **Engine:** ast-grep · **Severity:** error

## Rationale

A public function that accepts `**kwargs` has no checkable contract: callers
cannot see what keys are allowed, the type checker cannot verify them, and
refactors silently break at runtime. The kwargs get passed through two or
three layers until nobody knows what the real inputs are. A private helper
(`_name`) may still use `**kwargs` to forward to a known API, but anything
public must declare its shape.

Requiring `**kwargs: Unpack[SomeTypedDict]` forces the author to write the
contract once, so every call site is verified and every reader can see the
allowed keys.

## Bad

```python
def create_tour(**kwargs):
    return _build(**kwargs)


def update_tour(tour_id: int, **kwargs: Any): ...
```

Each function above is one finding: a public name with untyped `**kwargs`.

## Good

```python
from typing import Unpack
from typing_extensions import TypedDict


class TourOpts(TypedDict):
    title: str
    locale: str


def create_tour(**kwargs: Unpack[TourOpts]):
    return _build(**kwargs)


def _forward(**kwargs):
    return _build(**kwargs)
```

An `Unpack[SomeTypedDict]` annotation (or `typing.Unpack`) satisfies the rule,
as does a private name starting with `_`. `async def` follows the same rules.

## Notes

- Both `def` and `async def` are matched; the `def $F` pattern covers both.
- Return annotations do not exempt a signature: typed `**kwargs` with
  `-> ...` is matched, and `Unpack[...]` / `P.kwargs` exemptions cover it too.
- `**kwargs: P.kwargs` (any ParamSpec name) is exempt: a ParamSpec-annotated
  forwarder preserves the wrapped signature, which is a checkable contract.
  The match is syntactic, not binding-aware: a non-ParamSpec `<Name>.kwargs`
  is trusted the same way a shadowed `Unpack` would be. Confirm the
  `ParamSpec` import on suspicion; fabrications that name no such attribute
  still fail downstream type checks.
- Any other annotation (including `Any` or `int`) still fails.
