from typing import Any, cast

x = cast(int, "1")  # SAFETY: input validated at boundary
y: Any = 1  # SAFETY: any JSON value allowed here
z = 1  # type: ignore[assignment]  # SAFETY: dynamic attribute
# SAFETY: legacy shim, remove after migration
w = 2  # ty: ignore[invalid-assignment]
# SAFETY: validated by schema
v = cast(int, "3")
