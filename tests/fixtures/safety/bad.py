from typing import Any, cast

x = cast(int, "1")
y: Any = 1
z = 1  # type: ignore[assignment]
w = 2  # ty: ignore[invalid-assignment]
v = 3  # type: ignore
# SAFETY: stale reason, blank line below breaks it

u = cast(int, "4")
