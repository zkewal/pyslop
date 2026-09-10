from unittest import mock
from unittest.mock import patch


def test_strings():
    mock.patch("billing.client.charge")
    patch("billing.client.charge")
    patch("billing.client.charge", return_value=1)


def test_monkeypatch(monkeypatch):
    monkeypatch.setattr("billing.client.charge", lambda: 1)
