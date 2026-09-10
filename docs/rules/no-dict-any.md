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


def load_config(raw: dict[str, Any]):
    ...


def fetch() -> dict[str, Any]:
    ...


def index(rows: Mapping[str, Any]):
    ...
```

Each signature above is one finding.

## Good

```python
from typing import Any


class Config(TypedDict):
    retries: int


def load_config(raw: Config):
    ...


def parse() -> Config:
    ...


def scrub():
    blob: dict[str, Any] = json.loads(raw)  # local narrowing is fine
    return Config(retries=blob["retries"])
```

`dict[str, int]`, `dict`, and `list[Any]` never fire. `Dict[str, Any]`,
`typing.Dict[str, Any]`, `typing.Mapping[str, Any]`, and
`collections.abc.Mapping[str, Any]` (with `Any` or `typing.Any`) all fire
when they appear in a parameter or return position.

## Notes

- Bare `dict[str, ...]` annotations are `generic_type` nodes in tree-sitter;
  qualified `typing.Dict[...]` ones are `subscript` nodes, so the rule matches
  both kinds. The signature scope is enforced with `inside:
  function_definition` minus `inside: block`, which is why locals are
  excluded. Same-or-previous-line `SAFETY` handling does not apply to this
  rule.
