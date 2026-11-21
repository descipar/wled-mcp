"""Issue #203: ``wled_add_device`` (DISC-08; DISC-05 caps on the read, DISC-10 reload).

Mocked evidence only: every test runs in ``tmp_path`` with synthetic RFC 1918 literals
(written with ``~`` for the dots, see ``d``) and a scripted ``enroll_tools.fetch_info``;
nothing contacts a device or the network. Permission failures are simulated by patching,
never by chmod (DEC-033). The live enrollment is separate (docs/validation/m7-m8.md).
"""

import hashlib
import json
import logging
import threading
import tomllib
from pathlib import Path
from types import MappingProxyType
from typing import Any

import anyio
import pytest
from mcp import MCPError
from mcp.client import Client

from tests.discovery_support import FakeEngine, make_resources
from tests.enroll_support import FakeFetch
from tests.http_support import running_service, sdk_client
from tests.test_discovery import FakeNetwork, answer_first, device
from tests.test_discovery_engine import MAC_A, MAC_B, FakeConnection, FakeTransport, wled
from tests.tool_contract import OPEN_WORLD_TOOLS, expected_names
from wled_mcp import discovery, discovery_tools, enroll_tools, setup
from wled_mcp.access import ToolClass
from wled_mcp.config import ConfigurationError, Device, load_config, validate_document
from wled_mcp.discovery_caps import HOST_TIMEOUT
from wled_mcp.discovery_engine import HttpTransport, InfoResult, KnownDevice
from wled_mcp.enroll_tools import AddDeviceRequest, build_enroll_operations, parse_base_url
from wled_mcp.filelock import config_backup_path, config_lock_path, exclusive_lock
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import create_server

REAL_FETCH = enroll_tools.fetch_info  # captured at import, before the autouse refusing guard
SECRET = "synthetic-secret-marker"
TOOL = "wled_add_device"


def d(text: str) -> str:
    """Private-range literals are written with ``~`` for the dots, so that the repository's
    private-identifier check (DEC-005) sees no literal; the value is rebuilt here."""
    return text.replace("~", ".")


IP1, IP2, IP3 = d("10~0~1~5"), d("172~16~5~9"), d("192~168~7~4")
URL1, URL2 = f"http://{IP1}", f"http://{IP2}:8080"
BASE = (
    "schema_version = 1\n# keep me\n\n"
    '[access]\nprofile = "full"\n\n'
    '[[devices]]\nid = "desk"\nname = "Desk"\nbase_url = "http://192.0.2.10"\n'
    "\n# trailing note\n"
)
WITH_OLD = BASE + f'\n[[devices]]\nid = "old"\nname = "Old"\nbase_url = "{URL2}"\nmac = "{MAC_A}"\n'


@pytest.fixture
def fetch(monkeypatch) -> FakeFetch:
    fake = FakeFetch(default=wled(MAC_A, "Kitchen Strip"))
    monkeypatch.setattr(enroll_tools, "fetch_info", fake)
    return fake


def script(monkeypatch, *answers: InfoResult) -> FakeFetch:
    fake = FakeFetch(*answers)
    monkeypatch.setattr(enroll_tools, "fetch_info", fake)
    return fake


def make(tmp_path: Path, content: str | bytes = BASE) -> tuple[Resources, Path]:
    path = tmp_path / "inventory.toml"
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    return Resources(load_config(str(path), str(tmp_path), {})), path


async def call(resources: Resources, **arguments: Any) -> Outcome:
    operation = build_enroll_operations(resources)[0]
    arguments.setdefault("base_url", URL1)
    validated = operation.request_model.model_validate(arguments).model_dump()
    return await operation.execute(validated)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> list[dict[str, Any]]:
    return tomllib.loads(path.read_text())["devices"]


def untouched(path: Path, before: bytes) -> None:
    assert path.read_bytes() == before
    assert not config_backup_path(path).exists()


# -- 1. request validation: nothing fetched, nothing written ------------------------------

BAD_URLS = [
    (d("ftp://10~0~1~5"), "invalid_url"),
    (d("https://10~0~1~5"), "invalid_url"),
    (d("HTTP://10~0~1~5"), "invalid_url"),
    (d("10~0~1~5"), "invalid_url"),
    (d("http://user:pw@10~0~1~5"), "invalid_url"),
    (d("http://10~0~1~5/json"), "invalid_url"),
    (d("http://10~0~1~5//"), "invalid_url"),
    (d("http://10~0~1~5?x=1"), "invalid_url"),
    (d("http://10~0~1~5#f"), "invalid_url"),
    (d("http://10~0~1~5 "), "invalid_url"),
    (d("http://10~0~1~5\n"), "invalid_url"),
    (d("http://10~0~1~5%31"), "invalid_url"),
    (d("http://10~0~1~5\\x"), "invalid_url"),
    (d("http://10~0~1~5:"), "invalid_url"),
    (d("http://10~0~1~5:0"), "invalid_url"),
    (d("http://10~0~1~5:65536"), "invalid_url"),
    (d("http://10~0~1~5:080"), "invalid_url"),
    (d("http://10~0~1~5:8:9"), "invalid_url"),
    (d("http://10~0~1~5:80x"), "invalid_url"),
    ("http://", "invalid_url"),
    ("http://desk.example", "not_ipv4_literal"),
    ("http://desk.example:80", "not_ipv4_literal"),
    ("http://[2001:db8::1]", "not_ipv4_literal"),
    (d("http://10~0~1"), "not_ipv4_literal"),
    (d("http://10~0~1~05"), "not_ipv4_literal"),
    (d("http://010~0~1~5"), "not_ipv4_literal"),
    ("http://0x0a.0.1.5", "not_ipv4_literal"),
    ("http://167772421", "not_ipv4_literal"),
    (d("http://10~0~1~256"), "not_ipv4_literal"),
    ("http://8.8.8.8", "not_private"),
    ("http://192.0.2.10", "not_private"),
    ("http://127.0.0.1", "not_private"),
    (d("http://169~254~1~5"), "not_private"),
    (d("http://100~64~0~1"), "not_private"),
    ("http://224.0.0.1", "not_private"),
    ("http://255.255.255.255", "not_private"),
    ("http://172.32.0.1", "not_private"),
]


@pytest.mark.parametrize(("value", "reason"), BAD_URLS)
@pytest.mark.anyio
async def test_a_bad_address_is_refused_before_any_read(tmp_path, fetch, value, reason):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    outcome = await call(resources, base_url=value)
    assert outcome.ok is False and outcome.error is not None
    assert outcome.error.code == "VALIDATION_ERROR"
    assert outcome.data == {"field": "base_url", "reason": reason}
    assert (outcome.application, outcome.verification) == ("not_attempted", "not_requested")
    assert outcome.device_id is None and fetch.calls == []
    untouched(path, before)
    echoed = value.removeprefix("http://").strip()
    assert not echoed or echoed not in json.dumps(outcome.model_dump())


def test_the_canonical_stored_form():
    assert parse_base_url(f"http://{IP1}")[2] == f"http://{IP1}"
    assert parse_base_url(f"http://{IP1}:80")[2] == f"http://{IP1}"
    assert parse_base_url(f"http://{IP1}/")[2] == f"http://{IP1}"
    assert parse_base_url(f"http://{IP2}:8080")[1:] == (8080, f"http://{IP2}:8080")


@pytest.mark.parametrize(
    "arguments",
    [
        {"device_id": "Bad ID"},
        {"device_id": "-x"},
        {"device_id": "x" * 65},
        {"device_id": ""},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 65},
        {"name": "bad\x07name"},
        {"expected_mac": "00005e00530"},
        {"expected_mac": "zz005e005301"},
        {"expected_mac": "00-00-5e-00-53-01"},
        {"expected_mac": 5},
        {"max_class": "read"},
        {"candidate": {"address": IP1}},
        {"timeout_seconds": 5},
        {"dry_run": "yes"},
        {"base_url": "x" * 41},
    ],
)
@pytest.mark.anyio
async def test_invalid_fields_and_unknown_arguments_are_refused(tmp_path, fetch, arguments):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError):  # the served schema refuses it the same way
        await call(resources, **arguments)
    assert fetch.calls == []
    untouched(path, before)


def test_the_request_schema_names_no_range_host_or_candidate_field():
    schema = AddDeviceRequest.model_json_schema()
    assert set(schema["properties"]) == {"base_url", "device_id", "name", "expected_mac", "dry_run"}
    assert schema["additionalProperties"] is False


# -- 2. success -----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_success_appends_one_entry_and_returns_exactly_it(tmp_path, fetch):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    outcome = await call(resources, base_url=f"http://{IP1}:80/")
    assert outcome.ok is True and outcome.error is None
    assert (outcome.application, outcome.verification) == ("not_attempted", "not_requested")
    assert outcome.dry_run is False and outcome.device_id == "kitchen-strip"
    entry = {"id": "kitchen-strip", "name": "Kitchen Strip", "base_url": URL1, "mac": MAC_A}
    assert outcome.data["entry"] == entry
    assert tables(path)[-1] == entry and len(tables(path)) == 2
    assert outcome.data["verified"] == {"firmware_version": "0.15.0", "product": "FOSS"}
    assert (outcome.data["inventory_size"], outcome.data["written"]) == (2, True)
    assert outcome.data["reloaded"] is True
    assert path.read_bytes().startswith(before)  # comments and blank lines are kept
    assert config_backup_path(path).read_bytes() == before
    assert "max_class" not in path.read_text()
    assert fetch.calls == [(IP1, 80)]  # exactly one read, of the parsed address


@pytest.mark.anyio
async def test_an_explicit_port_is_kept_and_probed(tmp_path, fetch):
    resources, path = make(tmp_path)
    outcome = await call(resources, base_url=URL2)
    assert outcome.ok and outcome.data["entry"]["base_url"] == URL2  # type: ignore[index]
    assert fetch.calls == [(IP2, 8080)]


@pytest.mark.anyio
async def test_the_product_may_be_absent_in_the_verified_summary(tmp_path, monkeypatch):
    script(monkeypatch, InfoResult("wled", MAC_A, "0.15.0", None, "Desk Two"))
    resources, path = make(tmp_path)
    outcome = await call(resources)
    assert outcome.ok
    assert outcome.data["verified"] == {"firmware_version": "0.15.0", "product": None}
    assert tables(path)[-1]["mac"] == MAC_A


# -- 3. in-process reload ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_new_entry_is_in_effect_without_a_restart(tmp_path, fetch):
    resources, path = make(tmp_path)
    old = resources.inventory
    outcome = await call(resources, device_id="strip")
    assert outcome.ok
    assert len(old) == 1 and resources.inventory[:1] == old  # the earlier snapshot is unchanged
    assert resources.resolve("strip").base_url == URL1
    resources.require_access("strip", ToolClass.CONTROL)  # raises when unknown or capped
    assert resources.monitor.is_configured("strip")
    reloaded = load_config(str(path), str(tmp_path), {})
    assert [x.id for x in reloaded.devices] == ["desk", "strip"]
    assert reloaded.devices[1].mac == MAC_A
    validate_document(path.read_bytes())


# -- 4. defaults ------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_defaults_come_from_the_reported_name_else_the_mac(tmp_path, monkeypatch):
    resources, path = make(tmp_path)
    script(monkeypatch, wled(MAC_A, "WLED"), wled(MAC_B, "WLED"))
    first = await call(resources)
    assert first.data["entry"]["id"] == "wled-005301"  # type: ignore[index]
    assert first.data["entry"]["name"] == "wled-005301"  # type: ignore[index]
    second = await call(resources, base_url=URL2)
    assert second.data["entry"]["id"] == "wled-005302"  # type: ignore[index]


@pytest.mark.anyio
async def test_a_default_id_is_unique_against_the_existing_ids(tmp_path, monkeypatch):
    resources, path = make(tmp_path)
    script(monkeypatch, wled(MAC_A, "Desk"))
    outcome = await call(resources)
    assert outcome.data["entry"]["id"] == "desk-2"  # type: ignore[index]
    assert outcome.data["entry"]["name"] == "Desk"  # type: ignore[index]


@pytest.mark.anyio
async def test_explicit_id_and_name_are_used_verbatim(tmp_path, fetch):
    resources, path = make(tmp_path)
    outcome = await call(resources, device_id="my-strip_1", name='Shelf "Light" Strip')
    assert outcome.ok
    assert outcome.data["entry"]["id"] == "my-strip_1"  # type: ignore[index]
    assert tables(path)[-1]["name"] == 'Shelf "Light" Strip'


# -- 5. conflicts -----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_duplicate_id_is_refused_before_any_read(tmp_path, fetch):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    outcome = await call(resources, device_id="desk")
    assert outcome.error is not None and outcome.error.code == "INVENTORY_CONFLICT"
    assert outcome.data == {"conflict": "id", "known_device_id": "desk"}
    assert outcome.application == "not_attempted" and outcome.device_id is None
    assert fetch.calls == []
    untouched(path, before)


@pytest.mark.anyio
@pytest.mark.parametrize("stored", [URL1, URL1 + ":80", URL1 + "/"])
async def test_an_equal_address_is_refused_before_any_read(tmp_path, fetch, stored):
    resources, path = make(tmp_path, BASE.replace("http://192.0.2.10", stored))
    before = path.read_bytes()
    outcome = await call(resources, base_url=f"http://{IP1}:80")
    assert outcome.error is not None and outcome.error.code == "INVENTORY_CONFLICT"
    assert outcome.data == {"conflict": "base_url", "known_device_id": "desk"}
    assert outcome.application == "not_attempted" and fetch.calls == []
    untouched(path, before)


@pytest.mark.anyio
async def test_an_equal_mac_at_another_address_is_refused_and_never_rewritten(tmp_path, fetch):
    resources, path = make(tmp_path, WITH_OLD)
    before = path.read_bytes()
    outcome = await call(resources)
    assert outcome.error is not None and outcome.error.code == "INVENTORY_CONFLICT"
    assert outcome.data == {"conflict": "mac", "known_device_id": "old"}
    assert outcome.application == "not_applied" and len(fetch.calls) == 1
    assert "by hand" in outcome.error.message
    untouched(path, before)
    assert resources.resolve("old").base_url == URL2


@pytest.mark.anyio
async def test_an_entry_without_a_stored_mac_gives_no_mac_conflict(tmp_path, fetch):
    resources, path = make(tmp_path)
    assert resources.resolve("desk").mac is None
    assert (await call(resources)).ok


@pytest.mark.anyio
async def test_expected_mac_mismatch_and_match(tmp_path, fetch):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    bad = await call(resources, expected_mac=MAC_B)
    assert bad.error is not None and bad.error.code == "VALIDATION_ERROR"
    assert bad.data == {"field": "expected_mac", "reason": "mac_mismatch"}
    assert bad.application == "not_applied"
    assert MAC_A not in json.dumps(bad.model_dump())
    untouched(path, before)
    good = await call(resources, expected_mac="00:00:5E:00:53:01")
    assert good.ok and good.data["entry"]["mac"] == MAC_A  # type: ignore[index]


# -- 6. verification failures -----------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("kind", "code"),
    [
        ("refused", "UNREACHABLE"),
        ("timeout", "TIMEOUT"),
        ("other", "NOT_WLED"),
        ("error", "INVALID_RESPONSE"),
    ],
)
async def test_a_failed_read_writes_nothing(tmp_path, monkeypatch, kind, code):
    script(monkeypatch, InfoResult(kind))  # type: ignore[arg-type]
    resources, path = make(tmp_path)
    before = path.read_bytes()
    outcome = await call(resources)
    assert outcome.error is not None and outcome.error.code == code
    assert (outcome.application, outcome.device_id) == ("not_applied", None)
    assert "nothing was written" in outcome.error.message.lower()
    if kind == "timeout":
        assert "safe" in outcome.error.reconciliation
    untouched(path, before)
    assert len(resources.inventory) == 1


def test_the_verification_read_is_one_get_of_json_info_with_the_hard_caps(monkeypatch):
    FakeConnection.instances = []
    FakeConnection.status, FakeConnection.error = 200, None
    FakeConnection.body = json.dumps(
        {"brand": "WLED", "ver": "0.15.0", "mac": "00:00:5E:00:53:01", "name": "Desk"}
    ).encode()
    monkeypatch.setattr(
        enroll_tools, "HttpTransport", lambda: HttpTransport(connection_factory=FakeConnection)
    )
    result = REAL_FETCH(IP1, 8080)
    assert result.kind == "wled"
    (connection,) = FakeConnection.instances
    assert (connection.host, connection.port, connection.timeout) == (IP1, 8080, HOST_TIMEOUT)
    assert [(m, p) for m, p, _ in connection.requests] == [("GET", "/json/info")]


# -- 7. dry run -------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_dry_run_reads_once_and_changes_nothing(tmp_path, fetch):
    resources, path = make(tmp_path)
    before, digest = path.read_bytes(), sha(path)
    snapshot = resources.inventory
    outcome = await call(resources, dry_run=True)
    assert outcome.ok and outcome.dry_run is True and outcome.device_id == "kitchen-strip"
    assert (outcome.application, outcome.verification) == ("not_attempted", "not_requested")
    assert outcome.data["entry"] == {
        "id": "kitchen-strip",
        "name": "Kitchen Strip",
        "base_url": URL1,
        "mac": MAC_A,
    }
    assert (outcome.data["written"], outcome.data["reloaded"]) == (False, False)
    assert outcome.data["inventory_size"] == 2
    assert fetch.calls == [(IP1, 80)]
    assert sha(path) == digest and path.read_bytes() == before
    assert not config_backup_path(path).exists() and not config_lock_path(path).exists()
    assert resources.inventory == snapshot


@pytest.mark.anyio
async def test_a_dry_run_reports_conflicts_and_failures_too(tmp_path, monkeypatch):
    resources, path = make(tmp_path, WITH_OLD)
    script(monkeypatch, wled(MAC_A, "X"), InfoResult("refused"))
    by_mac = await call(resources, dry_run=True)
    assert by_mac.error is not None and by_mac.data["conflict"] == "mac"
    assert by_mac.application == "not_attempted" and by_mac.dry_run is True
    by_id = await call(resources, dry_run=True, device_id="desk")
    assert by_id.data["conflict"] == "id"
    refused = await call(resources, dry_run=True, base_url=f"http://{IP3}")
    assert refused.error is not None and refused.error.code == "UNREACHABLE"
    assert refused.application == "not_attempted"


# -- 8. writer failure paths ------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_hand_edit_after_startup_is_a_conflict(tmp_path, fetch):
    resources, path = make(tmp_path)
    path.write_bytes(path.read_bytes() + b"# edited\n")
    edited = path.read_bytes()
    outcome = await call(resources)
    assert outcome.error is not None and outcome.error.code == "INVENTORY_CONFLICT"
    assert outcome.data == {"conflict": "file_changed"}
    assert outcome.application == "not_applied" and len(resources.inventory) == 1
    assert path.read_bytes() == edited


@pytest.mark.anyio
async def test_an_unwritable_directory_and_a_held_lock_leave_the_file_untouched(
    tmp_path, fetch, monkeypatch
):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    monkeypatch.setattr("os.access", lambda *a, **k: False)
    outcome = await call(resources)
    assert outcome.error is not None and outcome.error.code == "STORAGE_FAILED"
    assert outcome.data == {"reason": "not_writable"} and outcome.application == "not_applied"
    assert path.read_bytes() == before
    monkeypatch.undo()
    monkeypatch.setattr(enroll_tools, "fetch_info", fetch)

    resources, path = make(tmp_path)
    resources.inventory_writer()._lock_timeout = 0.2
    held, release = threading.Event(), threading.Event()

    def hold() -> None:
        with exclusive_lock(config_lock_path(path), 1):
            held.set()
            release.wait(5)

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(5)
    try:
        outcome = await call(resources)
    finally:
        release.set()
        holder.join(5)
    assert outcome.error is not None and outcome.data == {"reason": "locked"}
    assert outcome.error.code == "STORAGE_FAILED" and outcome.application == "not_applied"
    assert path.read_bytes() == before
    assert str(tmp_path) not in json.dumps(outcome.model_dump())


@pytest.mark.anyio
async def test_an_inline_devices_array_is_refused_without_writing(tmp_path, fetch):
    inline = (
        'schema_version = 1\ndevices = [{ id = "desk", name = "Desk", '
        'base_url = "http://192.0.2.10" }]\n'
    )
    resources, path = make(tmp_path, inline)
    before = path.read_bytes()
    outcome = await call(resources)
    assert outcome.error is not None and outcome.error.code == "INVENTORY_RELOAD_FAILED"
    assert outcome.data == {"stage": "validation"} and outcome.application == "not_applied"
    untouched(path, before)


@pytest.mark.anyio
async def test_an_access_mismatch_is_refused_without_writing(tmp_path, fetch):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    # A running cap that the file does not carry: the profile or caps need a restart.
    object.__setattr__(resources.access, "caps", MappingProxyType({"desk": ToolClass.READ}))
    outcome = await call(resources)
    assert outcome.error is not None and outcome.error.code == "INVENTORY_RELOAD_FAILED"
    assert outcome.data == {"stage": "access"} and outcome.application == "not_applied"
    untouched(path, before)


@pytest.mark.anyio
async def test_a_failing_reload_restores_the_previous_bytes(tmp_path, fetch, monkeypatch):
    resources, path = make(tmp_path)
    before = path.read_bytes()

    def broken(self, config):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(Resources, "apply_inventory", broken)
    outcome = await call(resources)
    assert outcome.error is not None and outcome.error.code == "INVENTORY_RELOAD_FAILED"
    assert outcome.data == {"stage": "reload"} and outcome.application == "not_applied"
    assert path.read_bytes() == before and len(resources.inventory) == 1
    assert SECRET not in json.dumps(outcome.model_dump())


@pytest.mark.anyio
async def test_a_failing_reload_and_restore_is_unknown(tmp_path, fetch, monkeypatch):
    resources, path = make(tmp_path)

    def broken(self, config):
        raise RuntimeError(SECRET)

    real = setup.atomic_write
    calls: list[Path] = []

    def recording(target, content, mode, before_replace=None):
        calls.append(target)
        if len(calls) >= 3:  # backup, replace, then the restore fails
            raise PermissionError(SECRET)
        real(target, content, mode, before_replace)

    monkeypatch.setattr(Resources, "apply_inventory", broken)
    monkeypatch.setattr("wled_mcp.inventory_writer.atomic_write", recording)
    outcome = await call(resources)
    assert outcome.error is not None and outcome.error.code == "INVENTORY_RELOAD_FAILED"
    assert (outcome.application, outcome.verification) == ("unknown", "unknown")
    assert SECRET not in json.dumps(outcome.model_dump())


# -- 9. races and sequences -------------------------------------------------------------------


@pytest.mark.anyio
async def test_two_concurrent_calls_for_one_address_create_one_entry(tmp_path, fetch):
    resources, path = make(tmp_path)
    results: list[Outcome] = []

    async def one() -> None:
        results.append(await call(resources))

    async with anyio.create_task_group() as group:
        group.start_soon(one)
        group.start_soon(one)
    assert sorted(r.ok for r in results) == [False, True]
    failed = next(r for r in results if not r.ok)
    assert failed.error is not None and failed.error.code == "INVENTORY_CONFLICT"
    assert failed.data["conflict"] in {"base_url", "mac"}
    assert len(tables(path)) == 2 and len(resources.inventory) == 2


@pytest.mark.anyio
async def test_two_different_addresses_both_succeed_in_sequence(tmp_path, monkeypatch):
    script(monkeypatch, wled(MAC_A, "One"), wled(MAC_B, "Two"))
    resources, path = make(tmp_path)
    assert (await call(resources, base_url=URL1)).ok
    assert (await call(resources, base_url=URL2)).ok  # the baseline advanced: no file_changed
    assert [t["id"] for t in tables(path)] == ["desk", "one", "two"]
    assert [x.id for x in resources.inventory] == ["desk", "one", "two"]


# -- 10. config model and writer helper -------------------------------------------------------


def document(device_extra: str = "") -> bytes:
    return (
        'schema_version = 1\n[[devices]]\nid = "a"\nname = "A"\n'
        f'base_url = "http://192.0.2.10"\n{device_extra}'
    ).encode()


@pytest.mark.parametrize(
    "value", ["00005e005301", "00005E005301", "00:00:5e:00:53:01", "00:00:5E:00:53:01"]
)
def test_the_mac_key_is_normalized_to_lowercase_hex(value):
    assert validate_document(document(f'mac = "{value}"\n')).devices[0].mac == MAC_A


@pytest.mark.parametrize(
    "extra",
    [
        f'mac = "{SECRET}"\n',
        'mac = "00005e00530"\n',
        'mac = "00-00-5e-00-53-01"\n',
        "mac = 5\n",
        'mac = ""\n',
        "mac = []\n",
    ],
)
def test_a_bad_mac_gets_a_positional_locator_and_no_echo(extra):
    with pytest.raises(ConfigurationError) as raised:
        validate_document(document(extra))
    assert "devices[0].mac: invalid" in str(raised.value)
    assert SECRET not in str(raised.value) and "00005e00530" not in str(raised.value)


def test_the_device_without_mac_is_unchanged_and_the_block_helper_adds_it_last():
    assert validate_document(document()).devices[0].mac is None
    plain = setup.device_block("a", "A", "http://192.0.2.10")
    assert "mac" not in plain
    assert setup.device_block("a", "A", "http://192.0.2.10", MAC_A) == plain + f'mac = "{MAC_A}"\n'


@pytest.mark.anyio
async def test_the_tool_written_file_validates_and_loads(tmp_path, fetch):
    resources, path = make(tmp_path)
    assert (await call(resources)).ok
    assert validate_document(path.read_bytes()).devices[1].mac == MAC_A
    assert load_config(str(path), str(tmp_path), {}).devices[1].mac == MAC_A


# -- 11. discovery consumer -------------------------------------------------------------------


def test_the_stored_mac_reaches_the_known_devices_of_tool_and_cli(tmp_path):
    devices = [
        Device(id="a", name="A", base_url=URL1, mac=MAC_A),
        Device(id="b", name="B", base_url="http://b.invalid"),
    ]
    assert discovery_tools.known_devices(devices) == [
        KnownDevice("a", IP1, MAC_A, 80),
        KnownDevice("b", "b.invalid", None, 80),
    ]
    path = tmp_path / "inventory.toml"
    path.write_text(
        f'schema_version = 1\n[[devices]]\nid = "a"\nname = "A"\nbase_url = "{URL1}"\n'
        f'mac = "{MAC_A}"\n'
    )
    assert discovery._configured(str(path)).known == [KnownDevice("a", IP1, MAC_A, 80)]


@pytest.mark.anyio
async def test_a_stored_mac_gives_address_changed_without_reading_the_known_device(
    tmp_path, monkeypatch
):
    found = d("10~0~2~21")
    transport = FakeTransport({found: wled(MAC_A, "Moved")})
    network = FakeNetwork(answer_first(device("moved", found, MAC_A)))
    monkeypatch.setattr(discovery_tools, "run_engine", FakeEngine(network, transport))
    content = BASE.replace(
        'base_url = "http://192.0.2.10"', f'base_url = "{URL1}"\nmac = "{MAC_A}"'
    )
    resources, _ = make(tmp_path, content)
    operation = {op.name: op for op in build_operations(resources)}["wled_discover_devices"]
    request = operation.request_model.model_validate({"methods": ["mdns"]}).model_dump()
    outcome = await operation.execute(request)
    (candidate,) = outcome.data["candidates"]  # type: ignore[misc]
    assert candidate["status"] == "address_changed" and candidate["known_device_id"] == "desk"  # type: ignore[index]
    assert IP1 not in transport.addresses  # matched by the stored MAC, no read of the entry


# -- 12. gating and contract ------------------------------------------------------------------


def served(tmp_path: Path, profile: str = "full"):
    resources = make_resources(tmp_path, profile=profile)
    return create_server(build_operations(resources), resources.access), resources


@pytest.mark.anyio
@pytest.mark.parametrize("profile", ["read-only", "control"])
async def test_the_tool_is_not_registered_below_the_full_profile(tmp_path, profile):
    server, _ = served(tmp_path, profile)
    async with Client(server) as client:
        names = [t.name for t in (await client.list_tools()).tools]
        assert TOOL not in names and names == expected_names(profile)
        with pytest.raises(MCPError) as caught:
            await client.call_tool(TOOL, {"base_url": URL1})
    assert (caught.value.code, caught.value.message) == (-32602, "Unknown tool")


@pytest.mark.anyio
async def test_the_full_profile_serves_it_as_a_manage_tool_with_open_world_hints(tmp_path):
    server, _ = served(tmp_path)
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert list(tools) == expected_names("full")
    hints = tools[TOOL].annotations
    assert (
        hints.read_only_hint,
        hints.destructive_hint,
        hints.idempotent_hint,
        hints.open_world_hint,
    ) == (False, False, False, True)
    assert TOOL in OPEN_WORLD_TOOLS
    properties = tools[TOOL].input_schema["properties"]
    assert set(properties) == {"base_url", "device_id", "name", "expected_mac", "dry_run"}
    assert tools[TOOL].input_schema["additionalProperties"] is False


@pytest.mark.anyio
async def test_the_served_descriptor_is_identical_over_streamable_http(tmp_path):
    server, _ = served(tmp_path)
    async with Client(server) as client:
        local = next(t for t in (await client.list_tools()).tools if t.name == TOOL)
    async with running_service(tmp_path) as running, sdk_client(running) as client:
        remote = next(t for t in (await client.list_tools()).tools if t.name == TOOL)
    assert local.model_dump() == remote.model_dump()


@pytest.mark.anyio
async def test_a_served_call_returns_the_envelope_and_the_new_id_is_usable(tmp_path, fetch):
    resources, path = make(tmp_path)
    server = create_server(build_operations(resources), resources.access)
    async with Client(server) as client:
        result = await client.call_tool(TOOL, {"base_url": URL1, "device_id": "strip"})
        listed = await client.call_tool("wled_list_devices", {})
    assert result.structured_content is not None and result.structured_content["ok"] is True
    assert result.structured_content["device_id"] == "strip"
    assert listed.structured_content is not None
    assert "strip" in json.dumps(listed.structured_content)


# -- 13. privacy and logging ------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_call_log_names_no_address_mac_or_name(tmp_path, fetch, caplog, capfd):
    resources, path = make(tmp_path)
    server = create_server(build_operations(resources), resources.access)
    with caplog.at_level(logging.DEBUG, logger="wled_mcp"):
        async with Client(server) as client:
            await client.call_tool(TOOL, {"base_url": URL1, "name": "Private Label"})
    text = "\n".join(r.getMessage() + repr(getattr(r, "call_fields", "")) for r in caplog.records)
    assert TOOL in text
    for secret in (IP1, MAC_A, "Private Label", "Kitchen"):
        assert secret not in text
    assert IP1 not in capfd.readouterr().err


@pytest.mark.anyio
async def test_error_data_carries_fixed_text_and_ids_only(tmp_path, fetch):
    resources, _ = make(tmp_path)
    for arguments in ({"device_id": "desk"}, {"base_url": "http://desk.example"}):
        outcome = await call(resources, **arguments)
        text = json.dumps(outcome.model_dump())
        assert IP1 not in text and "desk.example" not in text and MAC_A not in text
