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
`patch.object` in any form (`patch.object`, `mock.patch.object`,
`mocker.patch.object`) always passes.

## Notes

- `patch("path")` and `patch("path", ...)` are separate patterns because the
  trailing `, $$$` requires a comma; single-arg and multi-arg string calls
  would otherwise not both match. The same split applies to `$M.patch` and
  `monkeypatch.setattr`.
- dex-ios deviation pattern for legacy suites: older dex-ios test targets
  mock dozens of module paths by string and cannot migrate in one PR. For
  those targets, add a `[tool.pyslop.rules]` override disabling
  `pyslop/no-module-mocking` for the legacy test path, with a reason and an
  issue link per the deviation rule, then migrate one test file per PR.
  New test files must use real seams from day one.
