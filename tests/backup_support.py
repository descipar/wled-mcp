"""Helpers for snapshot store tests: synthetic data, fixed clock, tmp_path only."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from wled_mcp.backups import Firmware, SnapshotStore

FIRMWARE = Firmware("0.15.1", "synthetic-reference")
PRESET = {
    "n": "Saved scene",
    "on": True,
    "bri": 180,
    "seg": [{"id": 2, "start": 30, "stop": 60, "col": [[255, 80, 0]], "fx": 1}],
    "vendor_extension": {"opaque_value": ["preserved", 1.5, None]},
}


class TickClock:
    """Deterministic UTC clock advancing one second per reading."""

    def __init__(self, start: datetime | None = None) -> None:
        self.value = start or datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def make_store(tmp_path: Path, retain: int = 20, clock=None) -> SnapshotStore:
    return SnapshotStore(tmp_path / "backups", retain, clock or TickClock())


def envelope(backup_id: str, /, device_id: str = "desk", **override):
    document = {
        "format_version": 1,
        "backup_id": backup_id,
        "device_id": device_id,
        "preset_id": 5,
        "firmware": {"version": "0.15.1", "build_id": None},
        "created_at": "2026-11-04T12:00:00Z",
        "preset": {"n": "x", "on": False},
    }
    document.update(override)
    return document


GOOD_ID = "b-20261104T120000Z-0123456789ab"


def write_raw(store: SnapshotStore, device_id: str, name: str, content) -> Path:
    directory = store.directory / device_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(content if isinstance(content, bytes) else json.dumps(content).encode())
    return path


def listing_names(store: SnapshotStore, device_id: str = "desk") -> list[str]:
    directory = store.directory / device_id
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []
