"""Fixture: coded ignores with reasons, plus noqa left to ruff."""

x = 1  # type: ignore[assignment]  # SAFETY: int widens to str downstream
y = 2  # ty: ignore[invalid-assignment]  # SAFETY: stub lies, returns str
w = undefined_helper()  # noqa: F821
