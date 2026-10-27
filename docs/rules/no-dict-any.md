# no-dict-any

**Rule id:** `pyslop/no-dict-any` · **Engine:** ast-grep · **Severity:** error

## Rationale

`dict[str, Any]` in a signature says "a mapping with string keys and
who-knows-what values": the checker cannot verify the values, callers guess
the shape, and every consumer downcasts or sprinkles `cast`. The fix is to
declare the shape once at the boundary — a `TypedDict`, dataclass, or pydantic
model — so the contract travels with the function instead of living in a
comment.

Local variables annotated `dict[str, Any]` are allowed: narrowing untyped
input inside the body is legitimate work. The rule only fires on parameters
and return annotations, where the shape is a promise to callers.

## Bad

```python
from typing import Any


def load_config(raw: dict[str, Any]): ...


def fetch() -> dict[str, Any]: ...


def index(rows: Mapping[str, Any]): ...
```

Each signature above is one finding.

## Good

```python
from typing import Any


class Config(TypedDict):
    retries: int


def load_config(raw: Config): ...


def parse() -> Config: ...


def scrub():
    blob: dict[str, Any] = json.loads(raw)  # local narrowing is fine
    return Config(retries=blob["retries"])
```

`dict[str, int]`, `dict`, and `list[Any]` never fire. Neither do types that
merely contain a dict next to an `Any`, such as
`Callable[[dict[str, int]], Any]` or `tuple[dict[str, int], Any]`: the outer
type must itself be the mapping. `Dict[str, Any]`, `typing.Dict[str, Any]`,
`typing.Mapping[str, Any]`, `MutableMapping[str, Any]`, and
`collections.abc.Mapping[str, Any]` (with `Any` or `typing.Any`) all fire
when they appear in a parameter or return position, including in methods and
nested functions. A wrapped one such as `Optional[dict[str, Any]]` fires too.

## Notes

- Bare `dict[str, ...]` annotations are `generic_type` nodes in tree-sitter;
  qualified `typing.Dict[...]` ones are `subscript` nodes, so the rule matches
  both kinds. The signature scope is enforced by requiring the node to sit
  inside a `type` annotation that belongs to a typed parameter or to a
  function's `return_type`, which is why locals (and default values) are
  excluded while methods and nested defs are still checked. String
  annotations (`-> "dict[str, Any]"`) are not parsed and do not fire. Same-or-previous-line `SAFETY` handling does not apply to this
  rule.
