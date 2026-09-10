from collections.abc import Mapping
from typing import Any


def bad_param(raw: dict[str, Any]):  # SAFETY: fixture
    return raw


def bad_return() -> dict[str, Any]:  # SAFETY: fixture
    return {}


def bad_mapping(rows: Mapping[str, Any]):  # SAFETY: fixture
    return rows
