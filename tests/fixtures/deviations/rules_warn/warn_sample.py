"""Proves rules-warn downgrades no-module-mocking to a warning."""

from unittest import mock


def test_uses_legacy_bridge() -> None:
    with mock.patch("billing.client.charge", return_value=1) as charge:
        assert charge is not None
