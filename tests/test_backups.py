import json
import logging
import os
import shutil
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import anyio
import httpx2 as httpx
import pytest

import wled_mcp.backups as backups_module
from tests.backup_support import (
    FIRMWARE,
    GOOD_ID,
    PRESET,
    TickClock,
    envelope,
    listing_names,
    make_store,
    write_raw,
)
from tests.test_inventory_client import config, device
from wled_mcp.backups import MAX_SNAPSHOT_BYTES
from wled_mcp.client import ClientFailure, Endpoint
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources

REPO = Path(__file__).resolve().parents[1]
POSIX = os.name != "nt"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def code_of(call, *args, **kwargs):
    with pytest.raises(ClientFailure) as caught:
        call(*args, **kwargs)
    return caught.value.error.code


# -- T12 format ----------------------------------------------------------------


def test_roundtrip_preserves_unknown_preset_fields_and_order(tmp_path):
    store = make_store(tmp_path)
    record = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    snapshot = store.load("desk", record.backup_id)
    assert snapshot.preset == PRESET
    assert list(snapshot.preset) == list(PRESET)
    assert snapshot.preset_id == 5 and snapshot.firmware == FIRMWARE
    document = json.loads((store.directory / "desk" / f"{record.backup_id}.json").read_text())
    assert set(document) == set(envelope("x"))
    assert "mac" not in json.dumps(document).lower() and "http" not in json.dumps(document)


def test_contract_example_validates():
    raw = (REPO / "examples/contracts/snapshot.json").read_bytes()
    document = json.loads(raw)
    snapshot = backups_module.parse_snapshot(raw, "desk", document["backup_id"])
    assert snapshot.preset["vendor_extension"] == {"opaque_value": "preserved"}


@pytest.mark.parametrize(
    "override",
    [
        {"format_version": 0},
        {"format_version": 2},
        {"format_version": True},
        {"format_version": "1"},
        {"preset": {}},
        {"preset": []},
        {"preset": None},
        {"preset_id": 0},
        {"preset_id": 251},
        {"preset_id": True},
        {"preset_id": "5"},
        {"created_at": "2026-11-04 12:00:00"},
        {"created_at": "2026-13-04T12:00:00Z"},
        {"created_at": "2026-11-04T12:00:01Z"},  # disagrees with the ID timestamp
        {"firmware": {"version": ""}},
        {"firmware": {"version": "0.15.1", "mac": "x"}},
        {"firmware": "0.15.1"},
        {"extra": 1},
        {"device_id": "other"},
        {"backup_id": "b-20261104T120000Z-ffffffffffff"},
    ],
)
def test_invalid_envelopes_rejected_without_leaks(tmp_path, override):
    store = make_store(tmp_path)
    write_raw(store, "desk", f"{GOOD_ID}.json", envelope(GOOD_ID, **override))
    with pytest.raises(ClientFailure) as caught:
        store.load("desk", GOOD_ID)
    assert caught.value.error.code == "VALIDATION_ERROR"
    assert str(tmp_path) not in caught.value.error.message


def test_missing_key_and_malformed_bytes_rejected(tmp_path):
    store = make_store(tmp_path)
    document = envelope(GOOD_ID)
    del document["created_at"]
    cases = [
        json.dumps(document).encode(),
        b'{"format_version": 1,',
        b"\xff\xfe",
        b'{"format_version":1,"format_version":1}',
        json.dumps(envelope(GOOD_ID)).replace('"x"', "NaN").encode(),
        b"x" * (MAX_SNAPSHOT_BYTES + 1),
        b"[" * 100_000,
    ]
    for raw in cases:
        write_raw(store, "desk", f"{GOOD_ID}.json", raw)
        assert code_of(store.load, "desk", GOOD_ID) == "VALIDATION_ERROR", raw[:20]


def test_new_snapshot_rejects_bad_input_before_touching_filesystem(tmp_path):
    store = make_store(tmp_path)
    for bad in ({}, {"x": float("nan")}, {1: "int key"}):
        assert code_of(store.backup_preset, "desk", 5, bad, FIRMWARE) == "VALIDATION_ERROR"
    assert code_of(store.backup_preset, "desk", 0, PRESET, FIRMWARE) == "VALIDATION_ERROR"
    huge = {"blob": "a" * MAX_SNAPSHOT_BYTES}
    assert code_of(store.backup_preset, "desk", 5, huge, FIRMWARE) == "VALIDATION_ERROR"
    assert not store.directory.exists()


# -- T12 path safety / destination mismatch ---------------------------------------


@pytest.mark.parametrize(
    "backup_id",
    [
        "../x",
        "/etc/passwd",
        "a/b",
        "a\\b",
        "b-20261104T120000Z-0123456789ab\x00",
        "b-٠" * 3,
        "B-20261104T120000Z-0123456789AB",
        "b-" + "0" * 500,
        "",
        GOOD_ID + ".json",
        "*",
    ],
)
def test_unsafe_backup_ids_rejected(tmp_path, backup_id):
    store = make_store(tmp_path)
    assert code_of(store.load, "desk", backup_id) == "VALIDATION_ERROR"


@pytest.mark.parametrize("device_id", ["..", "../desk", "Desk", "a/b", "", "desk\x00", "x" * 65])
def test_unsafe_device_ids_rejected(tmp_path, device_id):
    store = make_store(tmp_path)
    assert code_of(store.load, device_id, GOOD_ID) == "VALIDATION_ERROR"
    assert code_of(store.backup_preset, device_id, 5, PRESET, FIRMWARE) == "VALIDATION_ERROR"
    assert not store.directory.exists()


def test_well_formed_missing_id_is_not_found(tmp_path):
    store = make_store(tmp_path)
    assert code_of(store.load, "desk", GOOD_ID) == "PRESET_NOT_FOUND"
    store.backup_preset("desk", 5, PRESET, FIRMWARE)
    assert code_of(store.load, "desk", GOOD_ID) == "PRESET_NOT_FOUND"


@pytest.mark.skipif(not POSIX, reason="symlinks need POSIX privileges")
def test_symlinked_file_and_directory_never_followed(tmp_path):
    store = make_store(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(envelope(GOOD_ID)))
    (store.directory / "desk").mkdir(parents=True)
    (store.directory / "desk" / f"{GOOD_ID}.json").symlink_to(outside)
    assert code_of(store.load, "desk", GOOD_ID) == "VALIDATION_ERROR"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (store.directory / "lamp").symlink_to(elsewhere)
    assert code_of(store.load, "lamp", GOOD_ID) == "PRESET_NOT_FOUND"
    assert code_of(store.backup_preset, "lamp", 5, PRESET, FIRMWARE) == "BACKUP_FAILED"
    assert list(elsewhere.iterdir()) == []


def test_directory_named_like_snapshot_is_invalid(tmp_path):
    store = make_store(tmp_path)
    (store.directory / "desk" / f"{GOOD_ID}.json").mkdir(parents=True)
    assert code_of(store.load, "desk", GOOD_ID) in {"VALIDATION_ERROR", "BACKUP_FAILED"}
    assert store.list_snapshots("desk").invalid_count == 1


def test_destination_mismatch_and_renamed_files(tmp_path):
    store = make_store(tmp_path)
    write_raw(store, "desk", f"{GOOD_ID}.json", envelope(GOOD_ID, device_id="lamp"))
    assert code_of(store.load, "desk", GOOD_ID) == "VALIDATION_ERROR"
    other = "b-20261104T120000Z-aaaaaaaaaaaa"
    write_raw(store, "desk", f"{other}.json", envelope(GOOD_ID, device_id="desk"))
    assert code_of(store.load, "desk", other) == "VALIDATION_ERROR"
    # A snapshot of device A is invisible through device B.
    record = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    assert code_of(store.load, "lamp", record.backup_id) == "PRESET_NOT_FOUND"
    assert store.list_snapshots("lamp").snapshots == ()


@pytest.mark.anyio
async def test_unknown_device_fails_before_filesystem(tmp_path):
    async with Resources(config(tmp_path)) as resources:
        with pytest.raises(ClientFailure) as caught:
            await resources.load_snapshot("nope", GOOD_ID)
        assert caught.value.error.code == "UNKNOWN_DEVICE"
        with pytest.raises(ClientFailure):
            await resources.plan_restore(
                "nope", GOOD_ID, firmware_version="0.15.1", destination_occupied=False
            )
        assert not resources.backups.directory.exists()


# -- T12 atomic durable write ------------------------------------------------------


def test_success_leaves_exactly_one_final_file_with_private_mode(tmp_path):
    store = make_store(tmp_path)
    record = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    assert listing_names(store) == [f"{record.backup_id}.json"]
    if POSIX:
        assert (
            stat.S_IMODE((store.directory / "desk" / listing_names(store)[0]).stat().st_mode)
            == 0o600
        )
        assert stat.S_IMODE((store.directory / "desk").stat().st_mode) == 0o700


def test_fsync_order_file_before_publish_and_directories_after(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    events = []
    real_fsync, real_link = os.fsync, os.link
    monkeypatch.setattr(os, "fsync", lambda fd: (events.append("file"), real_fsync(fd))[1])
    monkeypatch.setattr(os, "link", lambda a, b: (events.append("publish"), real_link(a, b))[1])
    monkeypatch.setattr(
        backups_module.SnapshotStore,
        "_fsync_directory",
        staticmethod(lambda path: events.append(("dir", path.name))),
    )
    store.backup_preset("desk", 5, PRESET, FIRMWARE)
    # New directories are made durable in their parents before the file is written;
    # the device directory is synced after publishing (a no-op inside on Windows).
    assert events == [
        ("dir", tmp_path.name),
        ("dir", "backups"),
        "file",
        "publish",
        ("dir", "desk"),
    ]
    events.clear()
    store.backup_preset("desk", 5, PRESET, FIRMWARE)  # existing dirs: no parent syncs
    assert events == ["file", "publish", ("dir", "desk")]


@pytest.mark.parametrize("target", ["fsync", "link", "mkdir", "write"])
def test_write_faults_fail_closed_keep_old_snapshots_and_clean_temp(tmp_path, monkeypatch, target):
    store = make_store(tmp_path)
    first = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    before = listing_names(store)

    def boom(*args, **kwargs):
        raise OSError(28, "No space left on device /secret/path")

    if target == "fsync":
        monkeypatch.setattr(os, "fsync", boom)
    elif target == "link":
        monkeypatch.setattr(os, "link", boom)
    elif target == "mkdir":
        shutil.rmtree(store.directory / "desk")
        monkeypatch.setattr(Path, "mkdir", boom)
        before = []
    else:

        class FullDisk:
            def __init__(self, fd):
                self.fd = fd

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                os.close(self.fd)

            def write(self, data):
                raise OSError(28, "No space left on device")

        monkeypatch.setattr(os, "fdopen", lambda fd, *a, **k: FullDisk(fd))
    with pytest.raises(ClientFailure) as caught:
        store.backup_preset("desk", 6, PRESET, FIRMWARE)
    assert caught.value.error.code == "BACKUP_FAILED"
    assert (
        "secret" not in caught.value.error.message
        and str(tmp_path) not in caught.value.error.message
    )
    monkeypatch.undo()
    assert listing_names(store) == before
    if before:
        assert store.load("desk", first.backup_id).preset == PRESET


@pytest.mark.skipif(not POSIX or os.geteuid() == 0, reason="needs unprivileged POSIX")
def test_read_only_directory_fails_closed(tmp_path):
    store = make_store(tmp_path)
    store.directory.mkdir()
    store.directory.chmod(0o500)
    try:
        assert code_of(store.backup_preset, "desk", 5, PRESET, FIRMWARE) == "BACKUP_FAILED"
    finally:
        store.directory.chmod(0o700)
    assert listing_names(store) == []


def test_post_write_validation_failure_fails_backup_and_removes_final(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    calls = []
    real = backups_module.parse_snapshot

    def flaky(raw, device_id, backup_id):
        calls.append(1)
        if len(calls) == 2:  # the re-read of the published file
            raise ClientFailure("VALIDATION_ERROR", "corrupt")
        return real(raw, device_id, backup_id)

    monkeypatch.setattr(backups_module, "parse_snapshot", flaky)
    assert code_of(store.backup_preset, "desk", 5, PRESET, FIRMWARE) == "BACKUP_FAILED"
    assert listing_names(store) == []


def test_id_collision_never_overwrites_and_retries(tmp_path, monkeypatch):
    store = make_store(tmp_path, clock=lambda: TickClock()())
    tokens = iter(["aaaaaaaaaaaa", "aaaaaaaaaaaa", "bbbbbbbbbbbb"])
    monkeypatch.setattr(backups_module.secrets, "token_hex", lambda n: next(tokens))
    first = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    second = store.backup_preset("desk", 6, {"n": "other"}, FIRMWARE)
    assert first.backup_id != second.backup_id
    assert store.load("desk", first.backup_id).preset == PRESET
    assert store.load("desk", second.backup_id).preset_id == 6


def test_leftover_temp_ignored_and_not_counted(tmp_path):
    store = make_store(tmp_path, retain=1)
    write_raw(store, "desk", f".{GOOD_ID}.tmp", b"partial")
    store.backup_preset("desk", 5, PRESET, FIRMWARE)
    store.backup_preset("desk", 5, PRESET, FIRMWARE)
    names = listing_names(store)
    assert f".{GOOD_ID}.tmp" in names
    assert len([n for n in names if n.endswith(".json")]) == 1


# -- T12 retention ----------------------------------------------------------------


def test_retention_keeps_newest_n_and_isolated_per_device(tmp_path):
    store = make_store(tmp_path, retain=3)
    ids = [store.backup_preset("desk", 5, {"n": str(i)}, FIRMWARE).backup_id for i in range(5)]
    store.backup_preset("lamp", 5, PRESET, FIRMWARE)
    kept = [s.backup_id for s in store.list_snapshots("desk").snapshots]
    assert kept == ids[2:]
    assert len(store.list_snapshots("lamp").snapshots) == 1


def test_retention_one_keeps_only_newest(tmp_path):
    store = make_store(tmp_path, retain=1)
    for i in range(3):
        last = store.backup_preset("desk", 5, {"n": str(i)}, FIRMWARE)
    assert [s.backup_id for s in store.list_snapshots("desk").snapshots] == [last.backup_id]


def test_prune_only_after_durable_new_snapshot(tmp_path, monkeypatch):
    store = make_store(tmp_path, retain=2)
    ids = [store.backup_preset("desk", 5, PRESET, FIRMWARE).backup_id for _ in range(2)]
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "io")))
    assert code_of(store.backup_preset, "desk", 5, PRESET, FIRMWARE) == "BACKUP_FAILED"
    monkeypatch.undo()
    assert [s.backup_id for s in store.list_snapshots("desk").snapshots] == ids


@pytest.mark.skipif(not POSIX, reason="symlinks need POSIX privileges")
def test_prune_never_touches_foreign_invalid_temp_symlink_or_other_devices(tmp_path):
    store = make_store(tmp_path, retain=1)
    old = "b-20200101T000000Z-000000000000"
    keepers = {
        "notes.txt": b"foreign",
        f"{old.replace('0000', '1111')}.json": b"corrupt",
        f".{old}.tmp": b"temp",
    }
    for name, data in keepers.items():
        write_raw(store, "desk", name, data)
    (store.directory / "desk" / "link.json").symlink_to(tmp_path)
    other = store.backup_preset("lamp", 5, PRESET, FIRMWARE)
    write_raw(store, "desk", f"{old}.json", envelope(old, created_at="2020-01-01T00:00:00Z"))
    record = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    names = listing_names(store)
    assert f"{old}.json" not in names  # oldest valid pruned
    assert f"{record.backup_id}.json" in names
    assert set(keepers) <= set(names) and "link.json" in names
    assert store.load("lamp", other.backup_id)
    assert record.pruned == 1 and any("invalid" in w for w in record.warnings)


def test_tie_break_on_equal_created_at_uses_backup_id(tmp_path):
    later = TickClock(datetime(2026, 11, 5, tzinfo=UTC))
    store = make_store(tmp_path, retain=2, clock=later)
    ids = ["b-20261104T120000Z-bbbbbbbbbbbb", "b-20261104T120000Z-aaaaaaaaaaaa"]
    for backup_id in ids:
        write_raw(store, "desk", f"{backup_id}.json", envelope(backup_id))
    assert [s.backup_id for s in store.list_snapshots("desk").snapshots] == sorted(ids)
    record = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    remaining = [s.backup_id for s in store.list_snapshots("desk").snapshots]
    assert remaining == [ids[0], record.backup_id]  # "aaaa" (lowest tie-break) pruned


def test_prune_failure_is_warning_only(tmp_path, monkeypatch, caplog):
    store = make_store(tmp_path, retain=1)
    first = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    real_unlink = os.unlink

    def selective(path, *args, **kwargs):
        if Path(path).name.startswith("."):
            return real_unlink(path, *args, **kwargs)
        raise OSError(13, "denied")

    monkeypatch.setattr(os, "unlink", selective)
    with caplog.at_level(logging.WARNING, logger="wled_mcp.backups"):
        record = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    monkeypatch.undo()
    assert record.warnings and record.pruned == 0
    assert store.load("desk", first.backup_id) and store.load("desk", record.backup_id)
    assert str(tmp_path) not in caplog.text


# -- T07 dry run -------------------------------------------------------------------


def test_dry_run_plan_mutates_nothing(tmp_path):
    store = make_store(tmp_path)
    plan = store.plan_backup("desk")
    assert plan["backup_required"] is True and plan["backup_storage_writable"] is True
    assert not store.directory.exists()
    store.backup_preset("desk", 5, PRESET, FIRMWARE)
    before = [(p.name, p.stat().st_mtime_ns) for p in (store.directory / "desk").iterdir()]
    store.plan_backup("desk")
    assert before == [(p.name, p.stat().st_mtime_ns) for p in (store.directory / "desk").iterdir()]


# -- restoration planning (deferred execution) -----------------------------------------


def test_restore_plan_is_read_only_and_requires_exact_firmware_and_device(tmp_path):
    store = make_store(tmp_path)
    record = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    before = listing_names(store)
    plan = store.plan_restore(
        "desk", record.backup_id, firmware_version="0.15.1", destination_occupied=False
    )
    data = plan.as_data()
    assert data["execution"] == "deferred" and data["target_preset_id"] == 5
    assert (
        code_of(
            store.plan_restore,
            "desk",
            record.backup_id,
            firmware_version="0.15.2",
            destination_occupied=False,
        )
        == "UNSUPPORTED_CAPABILITY"
    )
    assert (
        code_of(
            store.plan_restore,
            "lamp",
            record.backup_id,
            firmware_version="0.15.1",
            destination_occupied=False,
        )
        == "PRESET_NOT_FOUND"
    )
    assert listing_names(store) == before


def test_restore_plan_occupied_destination_needs_overwrite_and_prior_snapshot(tmp_path):
    store = make_store(tmp_path)
    source = store.backup_preset("desk", 5, PRESET, FIRMWARE)
    prior = store.backup_preset("desk", 7, {"n": "current"}, FIRMWARE)
    base = {"firmware_version": "0.15.1", "destination_occupied": True, "target_preset_id": 7}
    assert code_of(store.plan_restore, "desk", source.backup_id, **base) == "VALIDATION_ERROR"
    assert (
        code_of(store.plan_restore, "desk", source.backup_id, overwrite=True, **base)
        == "VALIDATION_ERROR"
    )
    assert (
        code_of(
            store.plan_restore,
            "desk",
            source.backup_id,
            overwrite=True,
            prior_backup_id=source.backup_id,
            **base,
        )
        == "VALIDATION_ERROR"
    )  # prior covers preset 5, not target 7
    plan = store.plan_restore(
        "desk", source.backup_id, overwrite=True, prior_backup_id=prior.backup_id, **base
    )
    assert plan.source_preset_id == 5 and plan.target_preset_id == 7


# -- synthetic destructive operation through Resources (abort before POST) ---------------


def preset_server(posts, preset_body=None):
    async def handler(request):
        if request.method == "POST":
            posts.append(request.url.path)
            return httpx.Response(200, json={"success": True})
        return httpx.Response(200, json={"on": True})

    return httpx.MockTransport(handler)


async def destructive(resources, device_id="desk", *, after_backup=None):
    """Stand-in for #9's overwrite/delete: backup first, then one POST."""

    async def prepare(context):
        await context.backup_preset(5, PRESET, FIRMWARE)
        if after_backup is not None:
            await after_backup(context)
        return {"on": True}

    return await resources.write_verified(device_id, "synthetic_destroy", prepare, lambda s: True)


@pytest.mark.anyio
async def test_backup_failure_aborts_with_zero_posts(tmp_path, monkeypatch):
    posts = []
    async with Resources(config(tmp_path), preset_server(posts)) as resources:
        monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "io")))
        outcome = await destructive(resources)
        monkeypatch.undo()
    assert posts == []
    assert (outcome.ok, outcome.application, outcome.verification) == (
        False,
        "not_attempted",
        "not_requested",
    )
    assert outcome.error.code == "BACKUP_FAILED" and outcome.error.write_retryable is False
    assert listing_names(make_store(tmp_path)) == []


@pytest.mark.anyio
async def test_snapshot_is_durable_before_post_and_id_reported(tmp_path):
    posts, seen_at_post = [], []
    store_dir = tmp_path / "backups" / "desk"

    async def handler(request):
        if request.method == "POST":
            seen_at_post.append(sorted(p.name for p in store_dir.iterdir()))
            posts.append(1)
            return httpx.Response(200, json={"success": True})
        return httpx.Response(200, json={"on": True})

    async with Resources(config(tmp_path), httpx.MockTransport(handler)) as resources:
        outcome = await destructive(resources)
    assert outcome.ok and len(posts) == 1
    backup_id = outcome.data["backup_id"]
    assert seen_at_post == [[f"{backup_id}.json"]]


@pytest.mark.anyio
async def test_changed_prior_object_conflict_keeps_snapshot_and_sends_nothing(tmp_path):
    posts = []

    async def recheck(context):
        raise ClientFailure("PRESET_CONFLICT", "Preset changed since it was read.")

    async with Resources(config(tmp_path), preset_server(posts)) as resources:
        outcome = await destructive(resources, after_backup=recheck)
    assert posts == []
    assert outcome.error.code == "PRESET_CONFLICT" and outcome.application == "not_attempted"
    assert outcome.data["backup_id"]


@pytest.mark.anyio
async def test_timeout_after_snapshot_no_resend_no_rollback(tmp_path):
    posts = []

    async def handler(request):
        if request.method == "POST":
            posts.append(1)
            raise httpx.ReadTimeout("slow")
        raise httpx.ConnectError("gone")

    async with Resources(config(tmp_path), httpx.MockTransport(handler)) as resources:
        outcome = await destructive(resources)
        listing = resources.backups.list_snapshots("desk")
    assert posts == [1]
    assert outcome.error.code == "WRITE_OUTCOME_UNKNOWN" and outcome.application == "unknown"
    assert outcome.data["backup_id"] == listing.snapshots[0].backup_id


@pytest.mark.anyio
async def test_same_device_serialized_distinct_ids_other_device_progresses(tmp_path):
    posts = []
    entered, release = anyio.Event(), anyio.Event()
    results = {}

    async def hold(context):
        entered.set()
        await release.wait()

    async with Resources(
        config(tmp_path, devices=[device("desk"), device("lamp")]), preset_server(posts)
    ) as resources:

        async def run(name, device_id, hook=None):
            results[name] = await destructive(resources, device_id, after_backup=hook)

        async with anyio.create_task_group() as group:
            group.start_soon(run, "a", "desk", hold)
            await entered.wait()
            group.start_soon(run, "b", "desk")
            group.start_soon(run, "c", "lamp")
            with anyio.fail_after(2):
                while "c" not in results:
                    await anyio.sleep(0.01)
            assert "b" not in results  # blocked by the desk lock
            release.set()
    ids = {results[k].data["backup_id"] for k in "ab"}
    assert len(ids) == 2 and all(r.ok for r in results.values())
    assert len(resources.backups.list_snapshots("desk").snapshots) == 2


@pytest.mark.anyio
async def test_one_store_shared_and_no_preset_tools_registered(tmp_path):
    async with Resources(config(tmp_path)) as resources:
        operations = build_operations(resources)
        assert resources.backups.retain_per_device == 20
        assert resources.backups.directory == tmp_path / "backups"
        assert not resources.backups.directory.exists()
        names = [op.name if hasattr(op, "name") else op.__class__.__name__ for op in operations]
        assert not any("restore" in str(n) or "preset" in str(n) for n in names)
    assert Endpoint.PRESETS  # presets endpoint exists but #8 never reads it


def test_retention_setting_wired_from_config(tmp_path):
    from wled_mcp.config import BackupSettings, StartupConfig

    cfg = StartupConfig(
        tmp_path / "c.toml", tmp_path, (device(),), backups=BackupSettings(retain_per_device=1000)
    )
    assert Resources(cfg).backups.retain_per_device == 1000


# -- OPS-03 ---------------------------------------------------------------------------


def test_logs_carry_no_payload_or_path(tmp_path, monkeypatch, caplog):
    store = make_store(tmp_path)
    monkeypatch.setattr(os, "link", lambda a, b: (_ for _ in ()).throw(OSError(1, "/very/secret")))
    with caplog.at_level(logging.DEBUG, logger="wled_mcp.backups"):
        code_of(store.backup_preset, "desk", 5, {"n": "PRIVATE-NAME"}, FIRMWARE)
    assert "PRIVATE-NAME" not in caplog.text and "secret" not in caplog.text
    assert str(tmp_path) not in caplog.text


def test_runtime_backups_cannot_enter_git():
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("needs a git checkout")
    for candidate in ("backups/desk/x.json", "runtime/backups/desk/x.json", "data/backups/x.json"):
        result = subprocess.run(["git", "check-ignore", "-q", candidate], cwd=REPO)
        assert result.returncode == 0, candidate
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert not [
        p for p in tracked if "backups/" in p and not p.startswith(("docs/", "tests/", "src/"))
    ]
    assert not [p for p in tracked if p.startswith(("backups/", "runtime/", "data/"))]
    assert [p for p in tracked if p.startswith("examples/") and "snapshot" in p] == [
        "examples/contracts/snapshot.json"
    ]
    assert sys.version_info >= (3, 11)


# -- review round 1 --------------------------------------------------------------------


def run_guarded(call, *args, timeout=5):
    """Run call in a daemon thread; a hang (e.g. FIFO open) fails instead of blocking."""
    import threading

    box = {}

    def target():
        try:
            box["result"] = call(*args)
        except BaseException as error:  # noqa: BLE001
            box["error"] = error

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), "call hung"
    if "error" in box:
        raise box["error"]
    return box["result"]


@pytest.mark.skipif(not POSIX, reason="needs os.mkfifo")
def test_fifo_named_like_snapshot_never_hangs_load_list_or_backup(tmp_path):
    store = make_store(tmp_path, retain=1)
    (store.directory / "desk").mkdir(parents=True)
    os.mkfifo(store.directory / "desk" / f"{GOOD_ID}.json")
    with pytest.raises(ClientFailure) as caught:
        run_guarded(store.load, "desk", GOOD_ID)
    assert caught.value.error.code == "VALIDATION_ERROR"
    assert run_guarded(store.list_snapshots, "desk").invalid_count == 1
    record = run_guarded(store.backup_preset, "desk", 5, PRESET, FIRMWARE)
    assert store.load("desk", record.backup_id)
    assert stat.S_ISFIFO((store.directory / "desk" / f"{GOOD_ID}.json").lstat().st_mode)


def test_backup_failed_reconciliation_matches_contract_example(tmp_path, monkeypatch):
    example = json.loads((REPO / "examples/contracts/errors.json").read_text())
    case = next(c for c in example["cases"] if c["name"] == "backup_failure")
    store = make_store(tmp_path)
    monkeypatch.setattr(os, "link", lambda a, b: (_ for _ in ()).throw(OSError(5, "io")))
    with pytest.raises(ClientFailure) as caught:
        store.backup_preset("desk", 5, PRESET, FIRMWARE)
    assert caught.value.error.reconciliation == case["expected"]["error"]["reconciliation"]
    assert "never replay the write" not in caught.value.error.reconciliation


@pytest.mark.anyio
async def test_outer_cancellation_after_shielded_backup_aborts_before_dispatch(tmp_path):
    posts = []
    async with Resources(config(tmp_path), preset_server(posts)) as resources:
        async with resources.operation("desk") as context:
            with anyio.CancelScope() as scope:
                scope.cancel()
                await context.backup_preset(5, PRESET, FIRMWARE)
                posts.append("reached dispatch")  # must be skipped
            assert scope.cancelled_caught
            assert len(context.backup_records) == 1
        assert posts == []
        assert len(resources.backups.list_snapshots("desk").snapshots) == 1
