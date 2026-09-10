from typing import Any


def good_typed(counts: dict[str, int]):
    return counts


def good_local():
    blob: dict[str, Any] = {}  # SAFETY: fixture
    return blob
