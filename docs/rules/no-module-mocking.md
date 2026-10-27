# no-module-mocking

**Rule id:** `pyslop/no-module-mocking` · **Engine:** ast-grep · **Severity:** error

## Rationale

`patch("some.module.attr")` and `monkeypatch.setattr("some.module.attr", v)`
mock by dotted string: the string is invisible to the type checker, to
rename refactors, and to readers. The test passes while the production path
it claims to cover no longer exists. Mocking by string also couples the test
to module layout instead of to behaviour, so moving a function breaks ten
tests that never touched its contract.

The fix is a real seam: dependency injection, a protocol, or a fixture that
hands the test a fake object. When the seam is an attribute on a concrete
object, `patch.object(obj, "attr")` and `monkeypatch.setattr(obj, "attr", v)`
are allowed, because the target object is checked, not a string.

## Bad

```python
mock.patch("billing.client.charge")
patch("billing.client.charge", return_value=1)
mocker.patch("billing.client.charge")
monkeypatch.setattr("billing.client.charge", fake)
monkeypatch.delattr("billing.client.charge")
patch(target="billing.client.charge")
patch.multiple("billing.client", charge=DEFAULT)
```

Each line above is one finding: a string target Naming a module path.

## Good

```python
mock.patch.object(client, "charge")
patch.object(client, "charge")
monkeypatch.setattr(client, "charge", fake)
patch(fake_client)
```

`patch(obj)` with a non-string target passes, since there is no dotted path.
So does any string that is not a dotted path: `client.patch("items/1")` and
`requests.patch("https://api/x")` are HTTP calls, not mocks.
`patch.object` in any form (`patch.object`, `mock.patch.object`,
`mocker.patch.object`) always passes.

## Notes

- A target counts only when it is a plain string shaped like a dotted path
  (`name.name[.name...]`). The rule looks at the first positional argument of
  `patch` / `*.patch` / `patch.multiple`, at a `target=` keyword on `patch`,
  and at the first argument of any `*.setattr` / `*.delattr` (so a renamed
  pytest fixture like `mp.setattr` counts too).
- A dotted string sent to an HTTP client (`client.patch("items.json")`)
  still fires; rename or build the URL if that happens.
- The rule is structural (`kind: call` + `has`) rather than `pattern:` plus
  `constraints:`. ast-grep checks constraints only after an `any:` branch has
  already matched, so a keyword call like `patch(target="a.b")` would bind
  to `patch($S)` first and then be dropped.
- Deviation pattern for legacy suites: an older test tree that mocks dozens
  of module paths by string cannot migrate in one PR. For
  those targets, add a `[tool.pyslop.rules]` override disabling
  `pyslop/no-module-mocking` for the legacy test path, with a reason and an
  issue link per the deviation rule, then migrate one test file per PR.
  New test files must use real seams from day one.
