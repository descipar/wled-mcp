from pathlib import Path

import pytest

from tests.network_guard import install_no_network


def pytest_configure():
    # Keep test artifacts inside the checkout, including on restricted Windows hosts.
    (Path(__file__).resolve().parents[1] / ".artifacts").mkdir(exist_ok=True)


@pytest.fixture
def no_network(monkeypatch):
    """The offline guard of tests/network_guard.py; fails the test if it refused anything."""
    attempts = install_no_network(monkeypatch)
    yield attempts
    assert attempts == []
