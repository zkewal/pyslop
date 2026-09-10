from unittest import mock
from unittest.mock import patch


def test_object_forms(client):
    mock.patch.object(client, "charge")
    patch.object(client, "charge")


def test_seams(monkeypatch, client):
    monkeypatch.setattr(client, "charge", lambda: 1)
