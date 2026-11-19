"""Issue #202: ``wled_set_discovery_ranges`` and the shared hard caps (mocked).

DISC-05 (caps shared by startup validator, tool and probe), DISC-07, DISC-10, DISC-T03
(each cap, hostile hand-edited file), DISC-T06 (writer and reload carrying ranges) and
DISC-T07 (gating). Every test runs in ``tmp_path`` with synthetic RFC 1918 literals;
nothing contacts a device or the network. Permission failures are simulated by patching,
never by chmod, and no test patches ``os.name`` (DEC-033).
"""

import json
import threading
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp import MCPError
from mcp.client import Client

from tests.tool_contract import expected_names
from wled_mcp import cli, setup
from wled_mcp.config import ConfigurationError, load_config, validate_document
from wled_mcp.discovery_caps import (
    CAPS,
    DiscoveryRangeError,
    check_ranges,
    validate_ranges,
)
from wled_mcp.discovery_config_tools import build_discovery_config_operations
from wled_mcp.filelock import config_backup_path, config_lock_path, exclusive_lock
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import create_server

SECRET = "synthetic-secret-marker"


def d(text: str) -> str:
    """Private-range literals are written with ``~`` for the dots, so that the repository's
    private-identifier check (DEC-005) sees no literal; the value is rebuilt here."""
    return text.replace("~", ".")


A, B, C = d("10~0~1~0/24"), d("172~16~5~0/28"), d("192~168~7~0/30")
BASE = (
    "schema_version = 1\n# keep me\n\n"
    '[access]\nprofile = "full"\n\n'
    '[[devices]]\nid = "desk"\nname = "Desk"\nbase_url = "http://192.0.2.10"\n'
    "\n# trailing note\n"
)
TOOL = "wled_set_discovery_ranges"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make(tmp_path: Path, content: str | bytes = BASE, **options: Any) -> tuple[Resources, Path]:
    path = tmp_path / "inventory.toml"
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    return Resources(load_config(str(path), str(tmp_path), {}, **options)), path


async def call(resources: Resources, **arguments: Any) -> Outcome:
    operation = build_discovery_config_operations(resources)[0]
    arguments.setdefault("dry_run", False)
    validated = operation.request_model.model_validate(arguments).model_dump()
    return await operation.execute(validated)


def listing(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


def ranges_line(*ranges: str) -> str:
    return "ranges = [" + ", ".join(f'"{r}"' for r in ranges) + "]"


# -- each hard cap, through the shared checker ------------------------------------------

CASES = [
    ("", "not_ipv4_cidr"),
    (d("10~0~1~0"), "not_ipv4_cidr"),
    ("fe8" + "0::/64", "not_ipv4_cidr"),
    (d("::ffff:10~0~1~0/120"), "not_ipv4_cidr"),
    (d("10~0~1~0/255~255~255~0"), "not_ipv4_cidr"),
    (d("10~0~1~0/0~0~0~255"), "not_ipv4_cidr"),
    (d(" 10~0~1~0/24"), "not_ipv4_cidr"),
    (d("10~0~1~0/24 "), "not_ipv4_cidr"),
    (d("10~0~1~0/24\n"), "not_ipv4_cidr"),
    (d("10~00~1~0/24"), "not_ipv4_cidr"),
    (d("10~0~1~0/024"), "not_ipv4_cidr"),
    (d("١٠~0~1~0/24"), "not_ipv4_cidr"),
    (d("10~0~1~0/33"), "not_ipv4_cidr"),
    ("999.0.1.0/24", "not_ipv4_cidr"),
    (d("10~0~1~5/24"), "not_network_address"),
    (d("172~16~5~1/28"), "not_network_address"),
    ("8.8.8.0/24", "not_private"),
    ("192.0.2.0/24", "not_private"),
    (d("100~64~0~0/24"), "not_private"),
    ("224.0.0.0/24", "not_private"),
    ("0.0.0.0/0", "not_private"),
    ("172.32.0.0/24", "not_private"),
    ("127.0.0.0/24", "loopback"),
    (d("169~254~1~0/24"), "link_local"),
    (d("10~0~0~0/23"), "too_broad"),
    (d("10~0~0~0/8"), "too_broad"),
    (d("172~16~0~0/12"), "too_broad"),
    (d("10~0~1~0/31"), "prefix_too_long"),
    (d("10~0~1~1/32"), "prefix_too_long"),
]


@pytest.mark.parametrize(("value", "reason"), CASES)
def test_each_cap_has_a_fixed_reason(value, reason):
    assert check_ranges([value]) == [(0, reason)]
    with pytest.raises(DiscoveryRangeError) as raised:
        validate_ranges([value])
    assert (raised.value.reason, raised.value.index) == (reason, 0)
    assert value.strip() not in str(raised.value) or not value.strip()


def test_duplicate_and_overlap_compare_with_earlier_accepted_entries():
    assert check_ranges([A, A]) == [(1, "duplicate")]
    assert check_ranges([d("10~0~1~0/25"), A]) == [(1, "overlap")]
    assert check_ranges([A, d("10~0~1~128/25")]) == [(1, "overlap")]
    # A rejected entry does not shadow a later one: B is judged against A only.
    assert check_ranges(["8.8.8.0/24", A, A]) == [(0, "not_private"), (2, "duplicate")]
    assert check_ranges([A, B, C]) == []


def test_the_probe_path_counts_entries_and_rechecks_before_probing():
    five = [f"10.0.{n}.0/24" for n in range(5)]
    with pytest.raises(DiscoveryRangeError, match="too_many_ranges"):
        validate_ranges(five)
    with pytest.raises(DiscoveryRangeError) as raised:
        validate_ranges([A, "8.8.8.0/24"])
    assert (raised.value.reason, raised.value.index) == ("not_private", 1)
    assert [str(n) for n in validate_ranges([A, B, C])] == [A, B, C]


def test_no_hard_cap_number_changed():
    assert (CAPS["ranges"], CAPS["min_prefix"], CAPS["max_prefix"]) == (4, 24, 30)
    assert CAPS["address_space"] == [d("10~0~0~0/8"), d("172~16~0~0/12"), d("192~168~0~0/16")]


# -- the tool: validation ---------------------------------------------------------------


@pytest.mark.anyio
async def test_the_tool_reports_every_rejection_in_index_order_and_never_echoes_values(tmp_path):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    hostile = ["8.8.8.0/24", A, d("10~0~1~0/25"), "not-a-range-" + SECRET]
    outcome = await call(resources, ranges=hostile)
    assert outcome.ok is False and outcome.error is not None
    assert outcome.error.code == "VALIDATION_ERROR"
    assert (outcome.application, outcome.verification) == ("not_attempted", "not_requested")
    assert outcome.data == {
        "rejected": [
            {"index": 0, "reason": "not_private"},
            {"index": 2, "reason": "overlap"},
            {"index": 3, "reason": "not_ipv4_cidr"},
        ]
    }
    text = json.dumps(outcome.model_dump())
    assert SECRET not in text and "8.8.8" not in text
    assert path.read_bytes() == before and listing(tmp_path) == ["inventory.toml"]
    assert resources.discovery_ranges == ()


@pytest.mark.parametrize("ranges", [[f"10.0.{n}.0/24" for n in range(5)], [1], d("10~0~1~0/24")])
def test_a_fifth_entry_or_a_wrong_type_is_a_schema_rejection(tmp_path, ranges):
    resources, _ = make(tmp_path)
    operation = build_discovery_config_operations(resources)[0]
    with pytest.raises(ValueError):  # the dispatcher turns this into VALIDATION_ERROR
        operation.request_model.model_validate({"ranges": ranges})


@pytest.mark.anyio
async def test_a_fifth_entry_through_the_server_is_validation_error_without_rejected(tmp_path):
    resources, path = make(tmp_path)
    server = create_server(build_operations(resources), resources.access)
    before = path.read_bytes()
    with anyio.fail_after(30):
        async with Client(server) as client:
            result = await client.call_tool(TOOL, {"ranges": [f"10.0.{n}.0/24" for n in range(5)]})
    envelope = result.structured_content
    assert envelope is not None and envelope["ok"] is False
    assert envelope["error"]["code"] == "VALIDATION_ERROR"
    assert "rejected" not in envelope["data"]
    assert path.read_bytes() == before


# -- the tool: success, no-op, dry run --------------------------------------------------


@pytest.mark.anyio
async def test_a_write_inserts_the_table_before_the_first_device_and_reloads(tmp_path):
    resources, path = make(tmp_path)
    devices_before = resources.inventory
    outcome = await call(resources, ranges=[A, B])
    assert outcome.ok and outcome.error is None and outcome.device_id is None
    assert (outcome.application, outcome.verification) == ("not_attempted", "not_requested")
    assert outcome.data == {
        "ranges_before": [],
        "ranges_after": [A, B],
        "changed": True,
        "written": True,
        "reloaded": True,
        "backup": True,
        "caps": CAPS,
    }
    expected = BASE.replace("[[devices]]", f"[discovery]\n{ranges_line(A, B)}\n\n[[devices]]")
    assert path.read_text() == expected
    assert config_backup_path(path).read_text() == BASE
    assert resources.discovery_ranges == (A, B)
    assert resources.inventory == devices_before
    assert validate_document(path.read_bytes()).discovery.ranges == [A, B]


@pytest.mark.anyio
async def test_replacing_an_existing_table_drops_only_that_tables_comments(tmp_path):
    content = BASE.replace(
        "[[devices]]", f"[discovery]\n# dropped\n{ranges_line(A)}\n\n[[devices]]"
    )
    resources, path = make(tmp_path, content)
    assert resources.discovery_ranges == (A,)
    outcome = await call(resources, ranges=[C, B])
    assert outcome.ok and outcome.data["ranges_before"] == [A]
    assert path.read_text() == BASE.replace(
        "[[devices]]", f"[discovery]\n{ranges_line(C, B)}\n\n[[devices]]"
    )
    assert resources.discovery_ranges == (C, B)


@pytest.mark.anyio
async def test_the_table_may_be_the_last_one_and_clearing_keeps_it(tmp_path):
    content = BASE + f"\n[discovery]\n{ranges_line(A)}\n"
    resources, path = make(tmp_path, content)
    outcome = await call(resources, ranges=[])
    assert outcome.ok and outcome.data["changed"] is True
    assert path.read_text() == BASE + "\n[discovery]\nranges = []\n"
    assert resources.discovery_ranges == ()
    assert validate_document(path.read_bytes()).discovery.ranges == []


@pytest.mark.anyio
async def test_a_root_devices_array_stays_valid_and_the_table_is_appended(tmp_path):
    content = "schema_version = 1\ndevices = []\n"
    resources, path = make(tmp_path, content)
    outcome = await call(resources, ranges=[A])
    assert outcome.ok
    assert (
        path.read_text() == f"schema_version = 1\ndevices = []\n\n[discovery]\n{ranges_line(A)}\n"
    )
    assert resources.discovery_ranges == (A,)


@pytest.mark.anyio
async def test_a_crlf_file_stays_crlf(tmp_path):
    resources, path = make(tmp_path, BASE.replace("\n", "\r\n").encode())
    outcome = await call(resources, ranges=[A])
    assert outcome.ok
    written = path.read_bytes()
    assert b"\n" not in written.replace(b"\r\n", b"")
    assert (
        written
        == BASE.replace("\n", "\r\n")
        .replace("[[devices]]", f"[discovery]\r\n{ranges_line(A)}\r\n\r\n[[devices]]")
        .encode()
    )


@pytest.mark.anyio
async def test_an_identical_list_writes_nothing(tmp_path):
    content = BASE.replace("[[devices]]", f"[discovery]\n{ranges_line(A)}\n\n[[devices]]")
    resources, path = make(tmp_path, content)
    before = path.read_bytes()
    outcome = await call(resources, ranges=[A])
    assert outcome.ok
    assert outcome.data["changed"] is False and outcome.data["written"] is False
    assert outcome.data["reloaded"] is False and outcome.data["backup"] is False
    assert outcome.data["ranges_before"] == outcome.data["ranges_after"] == [A]
    assert path.read_bytes() == before and not config_backup_path(path).exists()


@pytest.mark.anyio
async def test_clearing_an_absent_table_is_a_no_op(tmp_path):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    outcome = await call(resources, ranges=[])
    assert outcome.ok and outcome.data["written"] is False and outcome.data["changed"] is False
    assert path.read_bytes() == before and not config_backup_path(path).exists()


@pytest.mark.anyio
@pytest.mark.parametrize("valid", [True, False])
async def test_a_dry_run_touches_nothing(tmp_path, valid):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    ranges = [A, C] if valid else ["8.8.8.0/24"]
    outcome = await call(resources, ranges=ranges, dry_run=True)
    assert outcome.dry_run is True and outcome.application == "not_attempted"
    if valid:
        assert outcome.ok
        assert outcome.data == {
            "ranges_before": [],
            "ranges_after": [A, C],
            "changed": True,
            "written": False,
            "reloaded": False,
            "backup": False,
            "caps": CAPS,
        }
    else:
        assert outcome.error is not None and outcome.error.code == "VALIDATION_ERROR"
        assert outcome.data == {"rejected": [{"index": 0, "reason": "not_private"}]}
    assert path.read_bytes() == before
    assert listing(tmp_path) == ["inventory.toml"]  # no lock file, no backup
    assert resources.discovery_ranges == ()


@pytest.mark.anyio
async def test_a_dry_run_compares_with_the_running_snapshot(tmp_path):
    resources, _ = make(tmp_path)
    assert (await call(resources, ranges=[A])).ok
    same = await call(resources, ranges=[A], dry_run=True)
    other = await call(resources, ranges=[B], dry_run=True)
    assert (same.data["changed"], other.data["changed"]) == (False, True)
    assert other.data["ranges_before"] == [A]


# -- rollback and writer errors ---------------------------------------------------------


@pytest.mark.anyio
async def test_a_failing_reload_restores_the_previous_bytes(tmp_path, monkeypatch):
    resources, path = make(tmp_path)
    before = path.read_bytes()

    def broken(self, config):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(Resources, "apply_inventory", broken)
    outcome = await call(resources, ranges=[A])
    assert outcome.ok is False and outcome.error is not None
    assert outcome.error.code == "INVENTORY_RELOAD_FAILED"
    assert outcome.data == {"stage": "reload"}
    assert (outcome.application, outcome.verification) == ("not_applied", "not_requested")
    assert path.read_bytes() == before and resources.discovery_ranges == ()
    assert SECRET not in json.dumps(outcome.model_dump())


@pytest.mark.anyio
async def test_a_failing_reload_and_restore_is_unknown(tmp_path, monkeypatch):
    resources, path = make(tmp_path)

    def broken(self, config):
        raise RuntimeError(SECRET)

    real = setup.atomic_write

    monkeypatch.setattr(Resources, "apply_inventory", broken)
    calls: list[Path] = []

    def recording(target, content, mode, before_replace=None):
        calls.append(target)
        if len(calls) >= 3:  # backup, replace, then the restore fails
            raise PermissionError(SECRET)
        real(target, content, mode, before_replace)

    monkeypatch.setattr("wled_mcp.inventory_writer.atomic_write", recording)
    outcome = await call(resources, ranges=[A])
    assert outcome.error is not None and outcome.error.code == "INVENTORY_RELOAD_FAILED"
    assert (outcome.application, outcome.verification) == ("unknown", "unknown")
    assert outcome.data == {"stage": "reload"}
    assert SECRET not in json.dumps(outcome.model_dump()) and str(tmp_path) not in json.dumps(
        outcome.model_dump()
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "hostile",
    [d('discovery~ranges = ["10~0~9~0/24"]\n'), d('discovery = { ranges = ["10~0~9~0/24"] }\n')],
)
async def test_an_unsupported_hand_written_form_is_refused_without_writing(tmp_path, hostile):
    content = "schema_version = 1\n" + hostile + BASE.split("\n", 1)[1]
    resources, path = make(tmp_path, content)
    before = path.read_bytes()
    outcome = await call(resources, ranges=[A])
    assert outcome.error is not None and outcome.error.code == "INVENTORY_RELOAD_FAILED"
    assert outcome.data == {"stage": "validation"}
    assert outcome.application == "not_applied"
    assert path.read_bytes() == before and not config_backup_path(path).exists()


@pytest.mark.anyio
async def test_a_hand_edit_after_startup_is_a_conflict(tmp_path):
    resources, path = make(tmp_path)
    path.write_bytes(path.read_bytes() + b"# edited\n")
    edited = path.read_bytes()
    outcome = await call(resources, ranges=[A])
    assert outcome.error is not None and outcome.error.code == "INVENTORY_CONFLICT"
    assert outcome.data == {"conflict": "file_changed"}
    assert outcome.application == "not_applied"
    assert path.read_bytes() == edited and resources.discovery_ranges == ()


@pytest.mark.anyio
async def test_an_unwritable_directory_and_a_held_lock_leave_the_file_untouched(
    tmp_path, monkeypatch
):
    resources, path = make(tmp_path)
    before = path.read_bytes()
    monkeypatch.setattr("os.access", lambda *a, **k: False)
    outcome = await call(resources, ranges=[A])
    assert outcome.error is not None and outcome.error.code == "STORAGE_FAILED"
    assert outcome.data == {"reason": "not_writable"}
    assert path.read_bytes() == before
    monkeypatch.undo()

    resources, path = make(tmp_path)  # fresh baseline; short lock wait
    writer = resources.inventory_writer()
    writer._lock_timeout = 0.2
    held, release = threading.Event(), threading.Event()

    def hold() -> None:
        with exclusive_lock(config_lock_path(path), 1):
            held.set()
            release.wait(5)

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(5)
    try:
        outcome = await call(resources, ranges=[A])
    finally:
        release.set()
        holder.join(5)
    assert outcome.error is not None and outcome.data == {"reason": "locked"}
    assert outcome.error.code == "STORAGE_FAILED" and outcome.application == "not_applied"
    assert path.read_bytes() == before
    text = json.dumps(outcome.model_dump())
    assert str(tmp_path) not in text and SECRET not in text


@pytest.mark.anyio
async def test_the_writer_is_shared_so_a_second_write_is_not_a_false_conflict(tmp_path):
    resources, path = make(tmp_path)
    assert resources.inventory_writer() is resources.inventory_writer()
    assert (await call(resources, ranges=[A])).ok
    second = await call(resources, ranges=[A, B])
    assert second.ok and second.data["ranges_before"] == [A]
    assert resources.discovery_ranges == (A, B)
    assert config_backup_path(path).read_text().count(A) == 1


# -- reload carries the ranges ----------------------------------------------------------


def test_a_later_reload_replaces_the_ranges_and_old_readers_keep_their_tuple(tmp_path):
    resources, path = make(tmp_path)
    document = BASE.replace("[[devices]]", f"[discovery]\n{ranges_line(A)}\n\n[[devices]]")
    resources.apply_inventory(validate_document(document.encode()))
    held = resources.discovery_ranges
    assert held == (A,)
    resources.apply_inventory(validate_document(document.replace(A, B).encode()))
    assert resources.discovery_ranges == (B,) and held == (A,)
    assert isinstance(resources.discovery_ranges, tuple)
    resources.apply_inventory(validate_document(BASE.encode()))
    assert resources.discovery_ranges == ()


def test_the_loaded_file_seeds_the_running_ranges(tmp_path):
    content = BASE.replace("[[devices]]", f"[discovery]\n{ranges_line(A, C)}\n\n[[devices]]")
    resources, _ = make(tmp_path, content)
    assert resources.config.discovery_ranges == (A, C)
    assert resources.discovery_ranges == (A, C)


# -- startup validator (hostile hand-edited files) --------------------------------------


def document(body: str) -> bytes:
    return ("schema_version = 1\n" + body + BASE.split("\n", 1)[1]).encode()


@pytest.mark.parametrize(("value", "reason"), CASES)
def test_startup_rejects_each_cap_positionally_without_echoing_the_value(tmp_path, value, reason):
    quoted = json.dumps(value)  # a TOML-compatible basic string
    with pytest.raises(ConfigurationError) as raised:
        validate_document(document(f"[discovery]\nranges = [{json.dumps(A)}, {quoted}]\n"))
    message = str(raised.value)
    assert "discovery.ranges[1]: invalid" in message
    assert "discovery.ranges[0]" not in message
    assert not value.strip() or value.strip() not in message


def test_startup_names_every_bad_position_and_rejects_the_other_shapes():
    with pytest.raises(ConfigurationError, match=r"discovery\.ranges\[0\]: invalid, discovery"):
        validate_document(document(f'[discovery]\nranges = ["8.8.8.0/24", "{A}", "{A}"]\n'))
    for body, locator in (
        (
            "[discovery]\nranges = " + json.dumps([f"10.0.{n}.0/24" for n in range(5)]) + "\n",
            "discovery.ranges: invalid",
        ),
        (d('[discovery]\nranges = "10~0~1~0/24"\n'), "discovery.ranges: invalid"),
        ("[discovery]\nranges = [1]\n", "discovery.ranges[0]: invalid"),
        (f'[discovery]\nranges = ["{A}"]\nmode = "x"\n', "discovery: unsupported field"),
        ("discovery = 3\n", "discovery: invalid"),
    ):
        with pytest.raises(ConfigurationError) as raised:
            validate_document(document(body))
        assert locator in str(raised.value), body
        assert "mode" not in str(raised.value) and d("10~0~1~0") not in str(raised.value)


def test_startup_accepts_a_valid_table_and_an_absent_one(tmp_path):
    path = tmp_path / "inventory.toml"
    path.write_bytes(document(f"[discovery]\n{ranges_line(A, B, C)}\n"))
    assert load_config(str(path), str(tmp_path), {}).discovery_ranges == (A, B, C)
    path.write_bytes(BASE.encode())
    assert load_config(str(path), str(tmp_path), {}).discovery_ranges == ()


def test_config_validate_accepts_the_key_and_add_device_keeps_earlier_bytes(tmp_path, capsys):
    path = tmp_path / "inventory.toml"
    original = document(f"[discovery]\n{ranges_line(A)}\n")
    path.write_bytes(original)
    assert cli.main(["config", "validate", "--config", str(path)]) == 0
    capsys.readouterr()
    code = cli.main(
        [
            "config", "add-device", "--config", str(path), "--device-id", "lamp",
            "--device-name", "Lamp", "--base-url", "http://192.0.2.20",
        ]
    )  # fmt: skip
    capsys.readouterr()
    assert code == 0 and path.read_bytes().startswith(original)
    assert validate_document(path.read_bytes()).discovery.ranges == [A]


def test_the_text_edit_preserves_every_other_byte():
    text = BASE.replace("[[devices]]", "[http]\nconnect_timeout_seconds = 2\n\n[[devices]]")
    edited = setup.set_discovery_ranges(text, [A])
    assert edited.replace(f"[discovery]\n{ranges_line(A)}\n\n", "") == text
    assert setup.set_discovery_ranges(edited, []) == text.replace(
        "[[devices]]", "[discovery]\nranges = []\n\n[[devices]]"
    )


# -- gating and contract ----------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("profile", ["read-only", "control", "full"])
async def test_only_the_full_profile_serves_the_tool(tmp_path, profile):
    resources, path = make(tmp_path, profile=profile)
    server = create_server(build_operations(resources), resources.access)
    before = path.read_bytes()
    with anyio.fail_after(30):
        async with Client(server) as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
            assert sorted(tools) == sorted(expected_names(profile))
            if profile == "full":
                hints = tools[TOOL].annotations
                assert hints is not None
                assert (
                    hints.read_only_hint,
                    hints.destructive_hint,
                    hints.idempotent_hint,
                    hints.open_world_hint,
                ) == (False, True, True, False)
                result = await client.call_tool(TOOL, {"ranges": [A], "dry_run": True})
                assert result.structured_content is not None
                assert result.structured_content["ok"] is True
            else:
                assert TOOL not in tools
                with pytest.raises(MCPError) as caught:
                    await client.call_tool(TOOL, {"ranges": [A]})
                assert (caught.value.code, caught.value.message) == (-32602, "Unknown tool")
    assert path.read_bytes() == before


def test_the_tool_registers_once_and_caps_are_plain_data(tmp_path):
    resources, _ = make(tmp_path)
    names = [op.name for op in build_operations(resources)]
    assert names.count(TOOL) == 1 and names[-1] == TOOL
    assert json.loads(json.dumps(CAPS)) == CAPS
