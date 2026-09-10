"""Fixture: bare ignores are errors even when justified."""

x = 1  # type: ignore  # SAFETY: hand-checked, error code to be narrowed
y = 2  # ty: ignore  # SAFETY: hand-checked, error code to be narrowed
