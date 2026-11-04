from pathlib import Path


def pytest_configure():
    # Keep test artifacts inside the checkout, including on restricted Windows hosts.
    (Path(__file__).resolve().parents[1] / ".artifacts").mkdir(exist_ok=True)
