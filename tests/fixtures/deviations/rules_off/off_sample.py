"""Proves rules-off suppresses no-module-mocking."""

from unittest import mock


def test_uses_legacy_bridge() -> None:
    with mock.patch("billing.client.charge", return_value=1) as charge:
        assert charge is not None
