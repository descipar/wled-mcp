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


@pytest.fixture(autouse=True)
def no_real_discovery(monkeypatch):
    """No test reaches the real discovery engine: its mDNS socket sends UDP datagrams,
    which the connect-based offline guard does not see. A test opts in with a ``FakeEngine``
    (tests/discovery_support.py). The process-wide run guard starts fresh for every test."""
    from tests.discovery_support import refusing_engine
    from wled_mcp import discovery_tools

    monkeypatch.setattr(discovery_tools, "run_engine", refusing_engine)
    discovery_tools.GUARD.reset()
