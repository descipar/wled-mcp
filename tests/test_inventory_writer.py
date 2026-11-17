"""Inventory writer (issue #201: DISC-09, DISC-10, acceptance DISC-T06, mocked).

Every test runs in ``tmp_path`` with synthetic values; nothing contacts a device or the
network. Permission failures are simulated by patching, never by chmod (DEC-033).
"""

import hashlib
import os
import threading
from pathlib import Path

import pytest

from wled_mcp import cli, setup
from wled_mcp.access import AccessPolicy, ToolClass
from wled_mcp.config import InventoryConfig, load_config, validate_document
from wled_mcp.filelock import LockTimeout, config_backup_path, config_lock_path, exclusive_lock
from wled_mcp.inventory_writer import InventoryWriteError, InventoryWriter
from wled_mcp.resources import Resources

SECRET = "synthetic-secret-marker"
BASE = (
    'schema_version = 1\n\n[[devices]]\nid = "desk"\nname = "Desk"\n'
    'base_url = "http://192.0.2.10"\n'
)


def block(device_id: str, host: str, extra: str = "") -> str:
    return (
        f'\n[[devices]]\nid = "{device_id}"\nname = "{device_id.title()}"\n'
        f'base_url = "http://{host}"\n{extra}'
    )


def appender(text: str):
    return lambda current: current + text.encode()


class Rig:
    def __init__(self, tmp_path: Path, content: str = BASE, **options) -> None:
        self.path = tmp_path / "inventory.toml"
        self.path.write_bytes(content.encode())
        self.applied: list[InventoryConfig] = []
        self.fail_apply = False
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.writer = self.make(**options)

    def make(self, access: AccessPolicy | None = None, baseline="current", **options):
        def apply(config: InventoryConfig) -> None:
            if self.fail_apply:
                raise RuntimeError(SECRET)
            self.applied.append(config)

        return InventoryWriter(
            self.path,
            self.sha if baseline == "current" else baseline,
            access or AccessPolicy(),
            apply,
            **options,
        )

    def files(self) -> list[str]:
        return sorted(p.name for p in self.path.parent.iterdir())


def denied(*args, **kwargs):
    raise PermissionError(SECRET)


def error_of(call) -> InventoryWriteError:
    with pytest.raises(InventoryWriteError) as caught:
        call()
    return caught.value


# -- happy path and unchanged candidate ------------------------------------------


def test_write_replaces_atomically_keeps_backup_reloads_and_advances_the_baseline(tmp_path):
    rig = Rig(tmp_path)
    before = rig.path.read_bytes()
    result = rig.writer.update(appender(block("lamp", "192.0.2.20")))
    assert (result.written, result.reloaded, result.backup) == (True, True, True)
    assert config_backup_path(rig.path).read_bytes() == before
    assert [d.id for d in result.devices] == ["desk", "lamp"] and len(rig.applied) == 1
    assert result.sha256 == hashlib.sha256(rig.path.read_bytes()).hexdigest()
    # The baseline moved with the write, so the next write is not a conflict.
    second = rig.writer.update(appender(block("shelf", "192.0.2.30")))
    assert second.written and config_backup_path(rig.path).read_bytes().endswith(b'192.0.2.20"\n')
    assert [d.id for d in load_config(str(rig.path), str(tmp_path), {}).devices] == [
        "desk",
        "lamp",
        "shelf",
    ]
    assert not [n for n in rig.files() if n.startswith(".wled-mcp-config-")]


def test_an_unchanged_candidate_writes_nothing_and_makes_no_backup(tmp_path):
    rig = Rig(tmp_path)
    for edit in (lambda current: None, lambda current: current):
        result = rig.writer.update(edit)
        assert (result.written, result.reloaded, result.backup) == (False, False, False)
        assert [d.id for d in result.devices] == ["desk"]
    assert not config_backup_path(rig.path).exists() and rig.applied == []


# -- rollback: nothing is damaged -------------------------------------------------


@pytest.mark.parametrize(
    ("candidate", "stage"),
    [
        (BASE + "unknown_key = 1\n", "validation"),
        (BASE + block("desk", "192.0.2.99"), "validation"),  # duplicate ID
        (BASE.replace('name = "Desk"', 'name = "Desk"\nmax_class = "control"'), "access"),
        (
            BASE.replace(
                "schema_version = 1\n", 'schema_version = 1\n[access]\nprofile = "read-only"\n'
            ),
            "access",
        ),
        ("schema_version = 1\ndevices = []\n", "validation"),  # drops a configured ID
    ],
)
def test_invalid_access_changing_or_id_dropping_candidates_are_refused_before_writing(
    tmp_path, candidate, stage
):
    rig = Rig(tmp_path)
    before = rig.path.read_bytes()
    error = error_of(lambda: rig.writer.update(lambda current: candidate.encode()))
    assert (error.code, error.application) == ("INVENTORY_RELOAD_FAILED", "not_applied")
    assert error.data == {"stage": stage}
    assert rig.path.read_bytes() == before and rig.applied == []
    assert rig.files() == [".inventory.toml.lock", "inventory.toml"]


def test_a_failing_apply_restores_the_previous_bytes(tmp_path):
    rig = Rig(tmp_path)
    before = rig.path.read_bytes()
    rig.fail_apply = True
    error = error_of(lambda: rig.writer.update(appender(block("lamp", "192.0.2.20"))))
    assert (error.code, error.application, error.data) == (
        "INVENTORY_RELOAD_FAILED",
        "not_applied",
        {"stage": "reload"},
    )
    assert rig.path.read_bytes() == before and SECRET not in str(error)
    rig.fail_apply = False  # the baseline did not move, so a retry works
    assert rig.writer.update(appender(block("lamp", "192.0.2.20"))).written


def test_a_failing_apply_and_a_failing_restore_report_unknown(tmp_path, monkeypatch):
    rig = Rig(tmp_path)
    rig.fail_apply = True
    real = setup.atomic_write
    calls = []

    def flaky(target, content, mode, before_replace=None):
        calls.append(target.name)
        if len(calls) == 3:  # backup, replace, then the restore
            raise PermissionError(SECRET)
        real(target, content, mode, before_replace)

    monkeypatch.setattr("wled_mcp.inventory_writer.atomic_write", flaky)
    error = error_of(lambda: rig.writer.update(appender(block("lamp", "192.0.2.20"))))
    assert (error.code, error.application) == ("INVENTORY_RELOAD_FAILED", "unknown")
    assert SECRET not in str(error) and str(rig.path) not in str(error)


# -- failed writes ----------------------------------------------------------------


@pytest.mark.parametrize("failing", ["os.replace", "mkstemp", "backup"])
def test_storage_failures_leave_the_file_unchanged_and_no_temporary_file(
    tmp_path, monkeypatch, failing
):
    rig = Rig(tmp_path)
    before = rig.path.read_bytes()
    if failing == "backup":
        real = setup.atomic_write

        def only_backup(target, content, mode, before_replace=None):
            if target.name.endswith(".bak"):
                raise PermissionError(SECRET)
            real(target, content, mode, before_replace)

        monkeypatch.setattr("wled_mcp.inventory_writer.atomic_write", only_backup)
    elif failing == "os.replace":
        monkeypatch.setattr(os, "replace", denied)
    else:
        monkeypatch.setattr("tempfile.mkstemp", denied)
    error = error_of(lambda: rig.writer.update(appender(block("lamp", "192.0.2.20"))))
    assert (error.code, error.application) == ("STORAGE_FAILED", "not_applied")
    assert rig.path.read_bytes() == before and rig.applied == []
    assert SECRET not in str(error) and str(tmp_path) not in str(error)
    assert not [n for n in rig.files() if n.startswith(".wled-mcp-config-")]


def test_a_directory_that_is_not_writable_is_a_storage_failure(tmp_path, monkeypatch):
    rig = Rig(tmp_path)
    monkeypatch.setattr(os, "access", lambda *a, **k: False)
    error = error_of(lambda: rig.writer.update(appender(block("lamp", "192.0.2.20"))))
    assert (error.code, error.data["reason"]) == ("STORAGE_FAILED", "unreadable")
    assert rig.applied == [] and not config_backup_path(rig.path).exists()


def test_a_missing_file_is_a_storage_failure(tmp_path):
    rig = Rig(tmp_path)
    rig.path.unlink()
    error = error_of(lambda: rig.writer.update(appender("x")))
    assert error.code == "STORAGE_FAILED"


# -- conflict ---------------------------------------------------------------------


def test_a_hand_edit_after_startup_is_a_conflict_and_nothing_is_written(tmp_path):
    rig = Rig(tmp_path)
    rig.path.write_bytes(BASE.encode() + b"# edited by hand\n")
    edited = rig.path.read_bytes()
    error = error_of(lambda: rig.writer.update(appender(block("lamp", "192.0.2.20"))))
    assert (error.code, error.data, error.application) == (
        "INVENTORY_CONFLICT",
        {"conflict": "file_changed"},
        "not_applied",
    )
    assert rig.path.read_bytes() == edited and rig.applied == []
    assert not config_backup_path(rig.path).exists()


def test_without_a_baseline_every_write_is_a_conflict(tmp_path):
    rig = Rig(tmp_path)
    writer = rig.make(baseline=None)
    assert error_of(lambda: writer.update(appender("x"))).code == "INVENTORY_CONFLICT"


def test_load_config_records_the_sha256_of_the_loaded_bytes(tmp_path):
    path = tmp_path / "inventory.toml"
    path.write_bytes(BASE.encode())
    loaded = load_config(str(path), str(tmp_path), {})
    assert loaded.config_sha256 == hashlib.sha256(BASE.encode()).hexdigest()


# -- concurrency ------------------------------------------------------------------


def test_two_threads_with_different_additions_both_land(tmp_path):
    rig = Rig(tmp_path)
    shared = rig.writer  # one writer shared by two requests, as in a server
    errors: list[BaseException] = []

    def add(name: str, host: str) -> None:
        try:
            shared.update(appender(block(name, host)))
        except BaseException as exc:  # noqa: BLE001 - collected for the assertion
            errors.append(exc)

    threads = [
        threading.Thread(target=add, args=("lamp", "192.0.2.20")),
        threading.Thread(target=add, args=("shelf", "192.0.2.30")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert errors == []
    ids = {d.id for d in validate_document(rig.path.read_bytes()).devices}
    assert ids == {"desk", "lamp", "shelf"}


def test_a_lock_held_elsewhere_is_a_locked_storage_failure(tmp_path):
    rig = Rig(tmp_path, lock_timeout=0.2)
    held, release = threading.Event(), threading.Event()

    def hold() -> None:
        with exclusive_lock(config_lock_path(rig.path), 1):
            held.set()
            release.wait(5)

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(5)
    try:
        before = rig.path.read_bytes()
        error = error_of(lambda: rig.writer.update(appender(block("lamp", "192.0.2.20"))))
        assert (error.code, error.data) == ("STORAGE_FAILED", {"reason": "locked"})
        assert rig.path.read_bytes() == before
        with pytest.raises(LockTimeout):
            with exclusive_lock(config_lock_path(rig.path), 0.1):
                pass
    finally:
        release.set()
        holder.join(5)
    assert rig.writer.update(appender(block("lamp", "192.0.2.20"))).written  # released


def test_the_cli_refuses_under_the_lock_and_keeps_a_backup_otherwise(tmp_path, capsys, monkeypatch):
    rig = Rig(tmp_path)
    argv = [
        "config", "add-device", "--config", str(rig.path), "--device-id", "lamp",
        "--device-name", "Lamp", "--base-url", "http://192.0.2.20", "--format", "json",
    ]  # fmt: skip
    before = rig.path.read_bytes()
    release, held = threading.Event(), threading.Event()

    def hold() -> None:
        with exclusive_lock(config_lock_path(rig.path), 1):
            held.set()
            release.wait(5)

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(5)
    try:
        monkeypatch.setattr(setup, "DEFAULT_TIMEOUT_SECONDS", 0.1)
        assert cli.main(argv) == 1
        assert "CONFIG_LOCKED" in capsys.readouterr().out and rig.path.read_bytes() == before
    finally:
        release.set()
        holder.join(5)
    assert cli.main(argv) == 0
    capsys.readouterr()
    assert config_backup_path(rig.path).read_bytes() == before
    assert b"lamp" in rig.path.read_bytes()


def test_config_init_force_keeps_the_replaced_file_as_backup(tmp_path, capsys):
    rig = Rig(tmp_path)
    before = rig.path.read_bytes()
    assert cli.main(["config", "init", "--config", str(rig.path), "--force"]) == 0
    capsys.readouterr()
    assert config_backup_path(rig.path).read_bytes() == before


# -- reload -----------------------------------------------------------------------


def resources_for(tmp_path: Path) -> tuple[Resources, Path]:
    path = tmp_path / "inventory.toml"
    path.write_bytes((BASE + block("shelf", "192.0.2.11")).encode())
    return Resources(load_config(str(path), str(tmp_path), {})), path


def grown(resources: Resources, path: Path) -> InventoryConfig:
    return validate_document(path.read_bytes() + block("lamp", "192.0.2.20").encode())


def test_reload_swaps_the_view_without_disturbing_running_iterations(tmp_path):
    resources, path = resources_for(tmp_path)
    old_lock = resources.locks["desk"]
    iterating = iter(resources.inventory)
    first = next(iterating)
    resources.apply_inventory(grown(resources, path))
    assert [d.id for d in [first, *iterating]] == ["desk", "shelf"]  # old snapshot
    assert [d.id for d in resources.inventory] == ["desk", "shelf", "lamp"]
    assert resources.resolve("lamp").id == "lamp"
    assert resources.locks["desk"] is old_lock and "lamp" in resources.locks
    assert resources.monitor.is_configured("lamp")
    resources.monitor.last_control.record("lamp", "op", "applied", "verified", None)
    assert resources.monitor.last_control.latest("lamp") is not None


def test_an_unknown_id_stays_unknown_after_a_rejected_write(tmp_path):
    resources, path = resources_for(tmp_path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    writer = InventoryWriter(path, sha, AccessPolicy(), resources.apply_inventory)
    error = error_of(lambda: writer.update(lambda current: current + b"bogus = 1\n"))
    assert error.code == "INVENTORY_RELOAD_FAILED"
    assert [d.id for d in resources.inventory] == ["desk", "shelf"]
    assert not resources.monitor.is_configured("lamp")
    writer.update(appender(block("lamp", "192.0.2.20")))
    assert [d.id for d in resources.inventory] == ["desk", "shelf", "lamp"]


def test_a_cap_in_the_running_policy_blocks_a_candidate_that_drops_it(tmp_path):
    path = tmp_path / "inventory.toml"
    text = BASE.replace('name = "Desk"', 'name = "Desk"\nmax_class = "control"')
    path.write_bytes(text.encode())
    sha = hashlib.sha256(text.encode()).hexdigest()
    caps = AccessPolicy("full", {"desk": ToolClass.CONTROL})
    writer = InventoryWriter(path, sha, caps, lambda config: None)
    assert writer.update(appender(block("lamp", "192.0.2.20"))).written
    bad = error_of(lambda: writer.update(lambda c: c.replace(b'max_class = "control"\n', b"")))
    assert bad.data == {"stage": "access"}
