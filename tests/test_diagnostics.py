"""Issue #20 PR B: correlation IDs, bounded call logs and ``wled_get_service_status``.

In-process tests use the mock fleet only. Console tests start the installed ``wled-mcp``
against synthetic loopback devices on ``127.0.0.1``; nothing contacts a LAN device.
Scenario IDs T20-14 to T20-17 are those of docs/validation/issue-20.md.
"""

from __future__ import annotations

import json
import logging
import re
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp import MCPError
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from tests.acceptance_support import LoopbackWLED
from tests.envelopes import (
    CORRELATION_ID,
    correlation_id_of,
    strip_correlation_id,
    without_correlation_id_text,
)
from tests.state_catalog_support import FakeClock, make_state
from tests.test_access_profiles import (
    HOSTS,
    http_arguments,
    http_client,
    make_config,
    make_router,
    tree,
    write_fleet,
)
from tests.test_http_cli import CONSOLE, TOKEN, clean_env, console, free_port, wait_ready
from tests.tool_contract import expected_names, expected_tool
from wled_mcp import __version__, cli, diagnostics
from wled_mcp.access import ToolClass
from wled_mcp.client import WLEDClient
from wled_mcp.config import ConfigurationError, HTTPSettings
from wled_mcp.diagnostics import (
    LOG_LINE_LIMIT,
    CallRecord,
    LineFormatter,
    LogSettings,
    ServiceMonitor,
    configure_logging,
    load_log_settings,
)
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import Operation, create_server, to_tool_result

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("read-only", "control", "full")
ALLOWED_FIELDS = {
    "event",
    "tool",
    "class",
    "device_id",
    "ok",
    "application",
    "verification",
    "error_code",
    "duration_ms",
    "correlation_id",
}
PLANTED = (
    "planted-secret-token",
    "http://user:hunter2@planted.example/secret",
    "Bearer planted-credential",
    "planted-scene-content",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Harness:
    """A server wired like the service: one monitor shared by the status tool and the server."""

    def __init__(self, tmp_path: Path, profile: str = "full", **caps: str) -> None:
        self.tmp_path = tmp_path
        self.config = make_config(tmp_path, profile, **caps)
        self.router = make_router()
        self.time = FakeClock()
        self.resources = Resources(self.config, self.router.transport(), self.time.clock())
        self.resources.poll_interval_seconds = 0.005
        self.server = create_server(
            build_operations(self.resources), self.config.access, self.resources.monitor
        )

    def posts(self) -> int:
        return self.router.count("POST")

    def requests(self) -> int:
        return len(self.router.calls)


async def call(client: Client, name: str, **arguments: Any) -> dict[str, Any]:
    result = await client.call_tool(name, arguments)
    assert result.structured_content is not None
    assert json.loads(result.content[0].text) == result.structured_content
    return result.structured_content


async def status(client: Client) -> dict[str, Any]:
    envelope = await call(client, "wled_get_service_status")
    assert envelope["ok"] is True, envelope
    data: dict[str, Any] = envelope["data"]
    return data


@pytest.fixture
def log_records(caplog: pytest.LogCaptureFixture) -> Iterator[list[logging.LogRecord]]:
    caplog.set_level(logging.INFO, logger="wled_mcp")
    yield [record for record in caplog.records if record.name == "wled_mcp.calls"]


def call_logs(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == "wled_mcp.calls"]


@pytest.fixture
def stderr_logging(capsys: pytest.CaptureFixture[str]) -> Iterator[None]:
    """Install the real handler for a test and take it away again afterwards."""
    before = list(logging.getLogger().handlers)
    level = logging.getLogger("wled_mcp").level
    yield
    logging.getLogger().handlers[:] = before
    logging.getLogger("wled_mcp").setLevel(level)


# ================================================== T20-14 the correlation ID on envelopes


@pytest.mark.anyio
async def test_every_served_envelope_carries_a_unique_server_generated_id(tmp_path):
    harness = Harness(tmp_path, desk="read")
    async with harness.resources, Client(harness.server) as client:
        envelopes = {
            "ok": await call(client, "wled_get_state", device_id="shelf"),
            "domain_error": await call(client, "wled_get_state", device_id="absent"),
            "validation_error": await call(client, "wled_set_state", device_id="shelf", on="yes"),
            "access_denied": await call(client, "wled_set_state", device_id="desk", on=True),
            "dry_run_denied": await call(
                client, "wled_set_state", device_id="desk", on=True, dry_run=True
            ),
        }
    assert envelopes["ok"]["ok"] is True
    assert envelopes["domain_error"]["error"]["code"] == "UNKNOWN_DEVICE"
    assert envelopes["validation_error"]["error"]["code"] == "VALIDATION_ERROR"
    assert envelopes["access_denied"]["error"]["code"] == "ACCESS_DENIED"
    ids = [correlation_id_of(envelope) for envelope in envelopes.values()]
    assert len(set(ids)) == len(ids)


@pytest.mark.anyio
async def test_a_client_cannot_choose_the_id(tmp_path):
    harness = Harness(tmp_path)
    chosen = "0123456789abcdef"
    async with harness.resources, Client(harness.server) as client:
        refused = await call(client, "wled_get_state", device_id="desk", correlation_id=chosen)
        assert harness.requests() == 0  # refused by schema validation before any I/O
        plain = await call(client, "wled_get_state", device_id="desk")
    assert refused["error"]["code"] == "VALIDATION_ERROR"
    assert correlation_id_of(refused) != chosen and correlation_id_of(plain) != chosen
    assert harness.requests() > 0


def test_the_id_is_optional_in_the_schema_and_absent_from_unserved_dumps():
    schema = Outcome.model_json_schema()
    assert "correlation_id" in schema["properties"]
    assert "correlation_id" not in schema["required"]
    assert schema["required"] == ["ok", "operation", "device_id", "application", "verification"]
    outcome = Outcome(
        ok=True, operation="wled_x", device_id=None, application="not_attempted",
        verification="not_requested",
    )  # fmt: skip
    for dump in (outcome.model_dump(), outcome.model_dump(mode="json")):
        assert "correlation_id" not in dump
    assert "correlation_id" not in json.loads(outcome.model_dump_json())
    served = outcome.model_copy(update={"correlation_id": "0123456789abcdef"})
    assert served.model_dump(mode="json")["correlation_id"] == "0123456789abcdef"
    assert Outcome.model_validate(served.model_dump(mode="json")) == served


def test_the_result_text_and_structured_content_carry_the_same_id():
    outcome = Outcome(
        ok=True, operation="wled_x", device_id=None, application="not_attempted",
        verification="not_requested",
    )  # fmt: skip
    result = to_tool_result(outcome, "0123456789abcdef")
    assert result.structured_content is not None
    assert json.loads(result.content[0].text) == result.structured_content
    assert result.structured_content["correlation_id"] == "0123456789abcdef"
    assert "correlation_id" not in (to_tool_result(outcome).structured_content or {})


def test_the_strip_helper_validates_before_it_strips():
    envelope: dict[str, Any] = {"ok": True, "correlation_id": "0123456789abcdef"}
    assert strip_correlation_id(envelope) == {"ok": True}
    assert envelope["correlation_id"] == "0123456789abcdef"  # the input is untouched
    with pytest.raises(AssertionError):
        strip_correlation_id({"ok": True, "correlation_id": "not-an-id"})
    # A served envelope without an ID fails the comparison; an unserved one opts out explicitly.
    with pytest.raises(KeyError):
        strip_correlation_id({"ok": True})
    assert strip_correlation_id({"ok": True}, served=False) == {"ok": True}


def test_the_text_helper_removes_an_id_that_contains_a_short_fragment():
    # A random ID once contained "999" and failed an absence check on a served result.
    envelope = {"ok": False, "correlation_id": "cb7f80999a123456"}
    for text in (json.dumps(envelope), repr(envelope), json.dumps(envelope, indent=2)):
        assert "999" in text
        assert "999" not in without_correlation_id_text(text)
        assert "cb7f8" not in without_correlation_id_text(text)
    assert without_correlation_id_text('{"host":"999.1.1.1"}') == '{"host":"999.1.1.1"}'


class Boom(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DeviceBoom(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64)


def crash_operation(
    secret: str, tool_class: ToolClass = ToolClass.READ, model: type[BaseModel] = Boom
) -> Operation:
    async def crash(arguments: dict[str, Any]) -> Outcome:
        raise RuntimeError(f"connection to http://user:{secret}@planted.example failed")

    return Operation(
        "wled_crash", "crashes", model, crash, ToolAnnotations(), tool_class=tool_class
    )


@pytest.mark.anyio
async def test_an_internal_failure_names_the_id_and_nothing_else(caplog):
    caplog.set_level(logging.INFO, logger="wled_mcp")
    monitor = ServiceMonitor(["desk"])
    server = create_server([crash_operation("hunter2")], monitor=monitor)
    async with Client(server) as client:
        with pytest.raises(MCPError) as caught:
            await client.call_tool("wled_crash", {})
    assert caught.value.error.code == -32603
    match = re.fullmatch(
        r"Internal operation failure \(correlation_id=([0-9a-f]{16})\)", caught.value.error.message
    )
    assert match is not None
    (record,) = call_logs(caplog)
    assert record.call_fields["correlation_id"] == match.group(1)  # type: ignore[attr-defined]
    assert record.call_fields["error_code"] == "INTERNAL_FAILURE"  # type: ignore[attr-defined]
    assert "hunter2" not in caplog.text and "planted.example" not in caplog.text
    assert "application" not in record.call_fields  # type: ignore[attr-defined]
    assert "verification" not in record.call_fields  # type: ignore[attr-defined]
    counts = monitor.call_counts()
    assert counts["internal_failure"] == 1 and counts["failed"] == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool_class", "application"),
    [
        (ToolClass.READ, None),
        (ToolClass.CONTROL, "unknown"),  # a crash cannot tell "not attempted" from "applied"
        (ToolClass.MANAGE, "unknown"),
    ],
)
async def test_an_internal_failure_logs_the_configured_device_and_an_honest_application(
    caplog, tool_class, application
):
    caplog.set_level(logging.INFO, logger="wled_mcp")
    server = create_server(
        [crash_operation("hunter2", tool_class, DeviceBoom)], monitor=ServiceMonitor(["desk"])
    )
    async with Client(server) as client:
        for device in ("desk", PLANTED[0]):  # a configured ID, then client-chosen input
            with pytest.raises(MCPError):
                await client.call_tool("wled_crash", {"device_id": device})
    configured, unconfigured = (r.call_fields for r in call_logs(caplog))  # type: ignore[attr-defined]
    assert configured["device_id"] == "desk"  # the operator knows which device to read back
    assert "device_id" not in unconfigured
    for fields in (configured, unconfigured):
        assert fields["error_code"] == "INTERNAL_FAILURE" and fields["ok"] is False
        assert fields.get("application") == application
        assert "verification" not in fields
        assert set(fields) <= ALLOWED_FIELDS
    for hidden in ("hunter2", "planted.example", PLANTED[0]):
        assert hidden not in caplog.text


@pytest.mark.anyio
async def test_an_unknown_tool_error_is_unchanged_and_the_name_is_not_logged(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="wled_mcp")
    harness = Harness(tmp_path, "read-only")
    async with harness.resources, Client(harness.server) as client:
        with pytest.raises(MCPError) as made_up:
            await client.call_tool("wled_planted-secret-token", {})
        with pytest.raises(MCPError) as disabled:  # a real tool the profile does not register
            await client.call_tool("wled_set_state", {"device_id": "desk"})
    assert made_up.value.error.message == disabled.value.error.message == "Unknown tool"
    records = call_logs(caplog)
    assert [r.call_fields["tool"] for r in records] == ["unknown_tool"] * 2  # type: ignore[attr-defined]
    assert "planted-secret-token" not in caplog.text and "wled_set_state" not in caplog.text


# ============================================================ T20-15 bounded structured logs


@pytest.mark.anyio
async def test_a_call_line_has_only_allowlisted_fields_and_no_planted_value(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="wled_mcp")
    harness = Harness(tmp_path, desk="read")
    async with harness.resources, Client(harness.server) as client:
        await call(client, "wled_get_state", device_id="desk")
        await call(client, "wled_get_state", device_id=PLANTED[0])  # unknown ID: client input
        await call(client, "wled_set_state", device_id="desk", on=True)  # ACCESS_DENIED
        await call(client, "wled_set_state", device_id="shelf", on=PLANTED[1])  # validation
        await call(client, "wled_patch_segments", device_id="shelf", note=PLANTED[2])
        await call(client, "wled_save_scene", scene={"id": PLANTED[3], "targets": PLANTED[1]})
    records = call_logs(caplog)
    assert len(records) == 6
    for record in records:
        fields = record.call_fields  # type: ignore[attr-defined]
        assert set(fields) <= ALLOWED_FIELDS
        assert {"event", "tool", "ok", "duration_ms", "correlation_id"} <= set(fields)
        assert CORRELATION_ID.match(fields["correlation_id"])
    rendered = "\n".join(
        [caplog.text, *(LineFormatter("json").format(record) for record in records)]
    )
    for planted in PLANTED:
        assert planted not in rendered
    for secret_host in HOSTS.values():
        assert secret_host not in rendered and f"http://{secret_host}" not in rendered
    by_device = [r.call_fields.get("device_id") for r in records]  # type: ignore[attr-defined]
    assert by_device == ["desk", None, "desk", None, None, None]  # validation: no device echoed


@pytest.mark.anyio
async def test_a_device_id_the_inventory_does_not_know_is_never_logged(caplog):
    caplog.set_level(logging.INFO, logger="wled_mcp")

    async def reply(arguments: dict[str, Any]) -> Outcome:
        return Outcome(
            ok=True,
            operation="wled_echo",
            device_id=PLANTED[0],  # an operation that echoes whatever ID it was given
            application="not_attempted",
            verification="not_requested",
        )

    echo = Operation("wled_echo", "echo", Boom, reply, ToolAnnotations(), tool_class=ToolClass.READ)
    async with Client(create_server([echo], monitor=ServiceMonitor(["desk"]))) as client:
        envelope = await call(client, "wled_echo")
    assert envelope["device_id"] == PLANTED[0]  # the envelope is the caller's own data ...
    (record,) = call_logs(caplog)
    assert "device_id" not in record.call_fields  # type: ignore[attr-defined]
    assert PLANTED[0] not in caplog.text  # ... the log line is not


@pytest.mark.anyio
async def test_the_line_carries_the_outcome_facts_and_class(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="wled_mcp")
    harness = Harness(tmp_path, desk="read")
    async with harness.resources, Client(harness.server) as client:
        denied = await call(client, "wled_set_state", device_id="desk", on=True)
        await call(client, "wled_get_state", device_id="shelf")
    refused, read = call_logs(caplog)
    assert refused.levelno == logging.WARNING and read.levelno == logging.INFO
    assert refused.call_fields == {  # type: ignore[attr-defined]
        "event": "tool_call",
        "tool": "wled_set_state",
        "class": "control",
        "device_id": "desk",
        "ok": False,
        "application": "not_attempted",
        "verification": "not_requested",
        "error_code": "ACCESS_DENIED",
        "duration_ms": refused.call_fields["duration_ms"],  # type: ignore[attr-defined]
        "correlation_id": denied["correlation_id"],
    }
    assert read.call_fields["class"] == "read" and read.call_fields["ok"] is True  # type: ignore[attr-defined]
    assert "error_code" not in read.call_fields  # type: ignore[attr-defined]


def test_lines_stay_within_the_bound_in_both_formats():
    worst = CallRecord(
        tool="wled_" + "x" * 40,
        correlation_id="0" * 16,
        duration_ms=10**9,
        ok=False,
        tool_class=ToolClass.MANAGE,
        device_id="d" * 64,
        application="not_attempted",
        verification="not_requested",
        error_code="WRITE_OUTCOME_UNKNOWN",
    )
    for fmt in ("text", "json"):
        record = logging.LogRecord("wled_mcp.calls", logging.WARNING, "", 0, "%s", ("x",), None)
        record.call_fields = worst.fields()  # type: ignore[attr-defined]
        line = LineFormatter(fmt).format(record)  # type: ignore[arg-type]
        assert len(line) <= LOG_LINE_LIMIT and "\n" not in line
    # Any other record of the package is bounded too, and a JSON line stays valid JSON.
    for fmt in ("text", "json"):
        long = logging.LogRecord("wled_mcp.x", logging.WARNING, "", 0, "a\nb" * 900, (), None)
        line = LineFormatter(fmt).format(long)  # type: ignore[arg-type]
        assert len(line) <= LOG_LINE_LIMIT and "\n" not in line
        if fmt == "json":
            assert json.loads(line)["logger"] == "wled_mcp.x"


@pytest.mark.anyio
async def test_the_default_level_is_silent_on_success_and_reports_failures(
    tmp_path, capsys, stderr_logging
):
    configure_logging(load_log_settings({}))
    harness = Harness(tmp_path)
    async with harness.resources, Client(harness.server) as client:
        await call(client, "wled_get_state", device_id="desk")
        quiet = capsys.readouterr()
        await call(client, "wled_get_state", device_id="absent")
    loud = capsys.readouterr()
    assert quiet.out == quiet.err == ""
    assert loud.out == ""  # stdout is reserved for stdio MCP
    (line,) = loud.err.splitlines()
    assert "WARNING" in line and "error_code=UNKNOWN_DEVICE" in line and "ok=false" in line


@pytest.mark.anyio
async def test_the_info_level_logs_successes_and_json_lines_parse(tmp_path, capsys, stderr_logging):
    configure_logging(
        load_log_settings({"WLED_MCP_LOG_LEVEL": "info", "WLED_MCP_LOG_FORMAT": "json"})
    )
    harness = Harness(tmp_path)
    async with harness.resources, Client(harness.server) as client:
        envelope = await call(client, "wled_get_state", device_id="desk")
    out = capsys.readouterr()
    assert out.out == ""
    (line,) = out.err.splitlines()
    document = json.loads(line)
    assert document["event"] == "tool_call" and document["level"] == "info"
    assert document["tool"] == "wled_get_state" and document["device_id"] == "desk"
    assert document["ok"] is True and document["correlation_id"] == envelope["correlation_id"]
    assert set(document) - {"ts", "level"} <= ALLOWED_FIELDS


def test_the_startup_event_is_visible_only_when_the_level_allows_it(
    tmp_path, capsys, stderr_logging
):
    config = make_config(tmp_path, "control", desk="read")
    configure_logging(load_log_settings({}))
    cli.announce_profile(config, "stdio")
    assert capsys.readouterr().err == ""
    configure_logging(LogSettings(level="info"))
    cli.announce_profile(config, "stdio")
    err = capsys.readouterr().err
    assert "service starting: transport=stdio profile=control capped_devices=1" in err
    assert "desk" not in err and str(tmp_path) not in err


def test_third_party_libraries_do_not_inherit_the_info_level(stderr_logging):
    configure_logging(LogSettings(level="info"))
    assert logging.getLogger("wled_mcp").getEffectiveLevel() == logging.INFO
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger().level == logging.WARNING
    handler = configure_logging(LogSettings(level="info"))
    assert [h for h in logging.getLogger().handlers if h is handler] == [handler]  # idempotent


def test_the_handler_writes_to_the_current_stderr_never_stdout(capsys, stderr_logging):
    configure_logging(LogSettings(level="info"))
    logging.getLogger("wled_mcp").info("first")
    assert "first" in capsys.readouterr().err
    logging.getLogger("wled_mcp").info("second")
    captured = capsys.readouterr()
    assert "second" in captured.err and captured.out == ""


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("WLED_MCP_LOG_LEVEL", "debug"),
        ("WLED_MCP_LOG_LEVEL", "http://planted.example/secret"),
        ("WLED_MCP_LOG_FORMAT", "xml"),
    ],
)
def test_an_invalid_log_setting_is_named_without_its_value(variable, value, capsys, monkeypatch):
    with pytest.raises(ConfigurationError) as caught:
        load_log_settings({variable: value})
    assert variable in str(caught.value) and value not in str(caught.value)
    monkeypatch.setenv(variable, value)
    assert cli.main([]) == 2
    err = capsys.readouterr().err
    assert variable in err and value not in err


def test_log_settings_default_and_parse_case_insensitively():
    assert load_log_settings({}) == LogSettings("warning", "text")
    assert load_log_settings({"WLED_MCP_LOG_LEVEL": " INFO ", "WLED_MCP_LOG_FORMAT": "Json"}) == (
        LogSettings("info", "json")
    )
    assert load_log_settings({"WLED_MCP_LOG_LEVEL": ""}).level == "warning"


# -------------------------------------- the installed console: stdout stays MCP-only


def test_the_stdio_console_keeps_stdout_clean_at_info_level(tmp_path):
    fake = LoopbackWLED()
    try:
        config = write_fleet(tmp_path, {"desk": (fake, None)})
        params = StdioServerParameters(
            command=str(CONSOLE),
            cwd=tmp_path,
            args=["--config", str(config), "--data-dir", str(tmp_path)],
            env=clean_env(WLED_MCP_LOG_LEVEL="info", WLED_MCP_LOG_FORMAT="json"),
        )

        async def run() -> None:
            with anyio.fail_after(90):
                # A polluted stdout would break the JSON-RPC framing of this client.
                async with Client(params, mode="legacy", read_timeout_seconds=30) as client:
                    ok = await call(client, "wled_get_state", device_id="desk")
                    bad = await call(client, "wled_get_state", device_id="absent")
                    data = await status(client)
                    assert ok["ok"] is True and bad["ok"] is False
                    assert data["service"]["transport"] == "stdio"

        anyio.run(run)
    finally:
        fake.close()


def test_the_http_console_logs_one_bounded_json_line_per_call(tmp_path):
    fake = LoopbackWLED()
    try:
        config = write_fleet(tmp_path, {"desk": (fake, None)})
        port = free_port()
        env = clean_env(
            WLED_MCP_HTTP_TOKEN=TOKEN, WLED_MCP_LOG_LEVEL="info", WLED_MCP_LOG_FORMAT="json"
        )
        seen: dict[str, Any] = {}

        async def run() -> None:
            with anyio.fail_after(90):
                async with http_client(port) as client:
                    seen["ok"] = await call(client, "wled_get_state", device_id="desk")
                    seen["bad"] = await call(client, "wled_get_state", device_id=PLANTED[0])
                    seen["status"] = await status(client)

        with console(config, tmp_path, *http_arguments(port), env=env) as (process, lines):
            startup = wait_ready(lines, port)
            anyio.run(run)
            assert process.poll() is None
            collected: list[str] = []
            while not lines.empty():
                collected.append(lines.get())
        text = "".join([*startup, *collected])
        events = [json.loads(line) for line in text.splitlines() if line.startswith("{")]
        assert any("service starting" in e.get("message", "") for e in events)
        calls = [e for e in events if e.get("event") == "tool_call"]
        assert [c["tool"] for c in calls[:2]] == ["wled_get_state", "wled_get_state"]
        assert calls[0]["correlation_id"] == seen["ok"]["correlation_id"]
        assert calls[1]["error_code"] == "UNKNOWN_DEVICE" and "device_id" not in calls[1]
        assert all(len(line) <= LOG_LINE_LIMIT for line in text.splitlines())
        for planted in (*PLANTED, TOKEN, fake.base_url):
            assert planted not in text
        assert seen["status"]["service"]["transport"] == "streamable-http"
    finally:
        fake.close()


# ===================================================== T20-16 wled_get_service_status


@pytest.mark.anyio
@pytest.mark.parametrize("profile", PROFILES)
async def test_the_status_tool_is_listed_in_every_profile_and_sends_nothing(tmp_path, profile):
    harness = Harness(tmp_path, profile, shelf="read")
    before = tree(tmp_path)
    async with harness.resources, Client(harness.server) as client:
        names = [tool.name for tool in (await client.list_tools()).tools]
        assert "wled_get_service_status" in names
        assert names == expected_names(profile)
        assert names[1] == "wled_get_service_status"
        for _ in range(3):
            data = await status(client)
    assert harness.requests() == 0
    assert tree(tmp_path) == before
    assert data["access"]["profile"] == profile
    devices = {entry["device_id"]: entry for entry in data["access"]["devices"]}
    assert devices["shelf"]["max_class"] == "read" and devices["shelf"]["effective_class"] == "read"
    assert devices["desk"]["max_class"] is None
    expected_desk = {"read-only": "read", "control": "control", "full": "manage"}[profile]
    assert devices["desk"]["effective_class"] == expected_desk


def test_the_status_tool_is_a_read_class_tool_with_read_annotations(tmp_path):
    async def collect() -> tuple[Operation, ...]:
        async with Harness(tmp_path).resources as resources:
            return build_operations(resources)

    operation = {op.name: op for op in anyio.run(collect)}["wled_get_service_status"]
    contract = expected_tool("wled_get_service_status")
    assert operation.tool_class is ToolClass.READ and contract.tool_class.value == "read"
    assert contract.destructive is False
    hints = operation.annotations
    assert (hints.read_only_hint, hints.destructive_hint) == (True, False)
    assert (hints.idempotent_hint, hints.open_world_hint) == (True, False)
    assert operation.request_model.model_json_schema().get("properties", {}) == {}


@pytest.mark.anyio
async def test_an_unobserved_device_is_unknown_never_healthy(tmp_path):
    harness = Harness(tmp_path)
    async with harness.resources, Client(harness.server) as client:
        data = await status(client)
    readiness = data["readiness"]
    assert readiness["counts"] == {"unknown": 3, "reachable": 0, "failed": 0}
    assert [d["state"] for d in readiness["devices"]] == ["unknown"] * 3
    assert all("age_seconds" not in d and "error_code" not in d for d in readiness["devices"])
    flattened = json.dumps(data)
    for aggregate in ('"healthy"', '"ready"', '"all_ok"'):
        assert aggregate not in flattened


@pytest.mark.anyio
async def test_a_failed_read_is_reported_with_its_code_and_age(tmp_path):
    harness = Harness(tmp_path)
    harness.router.set(HOSTS["desk"], "/json/state", httpx.ConnectError("planted refused"))
    async with harness.resources, Client(harness.server) as client:
        failed = await call(client, "wled_get_state", device_id="desk")
        assert failed["error"]["code"] == "UNREACHABLE"
        harness.time.advance(42)
        data = await status(client)
    by_id = {d["device_id"]: d for d in data["readiness"]["devices"]}
    assert by_id["desk"] == {
        "device_id": "desk",
        "state": "failed",
        "age_seconds": 42,
        "error_code": "UNREACHABLE",
    }
    assert by_id["shelf"]["state"] == by_id["lamp"]["state"] == "unknown"
    assert data["readiness"]["counts"] == {"unknown": 2, "reachable": 0, "failed": 1}
    assert "planted refused" not in json.dumps(data)


@pytest.mark.anyio
async def test_a_good_read_after_a_failure_is_reachable_with_a_fresh_age(tmp_path):
    harness = Harness(tmp_path)
    flaky = {"fail": True}

    def state() -> Any:
        if flaky["fail"]:
            raise httpx.ReadTimeout("planted")
        return make_state()

    harness.router.set(HOSTS["desk"], "/json/state", state)
    async with harness.resources, Client(harness.server) as client:
        await call(client, "wled_get_state", device_id="desk")
        timed_out = {d["device_id"]: d for d in (await status(client))["readiness"]["devices"]}
        flaky["fail"] = False
        harness.time.advance(300)
        stale = {d["device_id"]: d for d in (await status(client))["readiness"]["devices"]}
        await call(client, "wled_get_state", device_id="desk")
        fresh = {d["device_id"]: d for d in (await status(client))["readiness"]["devices"]}
    assert timed_out["desk"]["state"] == "failed" and timed_out["desk"]["error_code"] == "TIMEOUT"
    assert stale["desk"]["state"] == "failed" and stale["desk"]["age_seconds"] == 300
    assert fresh["desk"] == {"device_id": "desk", "state": "reachable", "age_seconds": 0}


@pytest.mark.anyio
async def test_polling_the_status_never_refreshes_an_observation_or_sends_a_request(tmp_path):
    harness = Harness(tmp_path)
    async with harness.resources, Client(harness.server) as client:
        await call(client, "wled_get_state", device_id="desk")
        sent = harness.requests()
        first = (await status(client))["readiness"]
        second = (await status(client))["readiness"]
        harness.time.advance(120)
        aged = (await status(client))["readiness"]
        for _ in range(5):
            await status(client)
    assert first == second
    assert {d["device_id"]: d for d in aged["devices"]}["desk"]["age_seconds"] == 120
    assert {d["device_id"]: d for d in aged["devices"]}["shelf"]["state"] == "unknown"
    assert harness.requests() == sent  # nothing but the one explicit read ever left the process


@pytest.mark.anyio
async def test_writes_and_probes_are_observed_like_reads(tmp_path):
    harness = Harness(tmp_path)
    harness.router.set(HOSTS["shelf"], "/json/info", httpx.Response(500))
    async with harness.resources, Client(harness.server) as client:
        await call(client, "wled_list_devices", probe=True)
        probed = {d["device_id"]: d for d in (await status(client))["readiness"]["devices"]}
        await call(client, "wled_set_state", device_id="lamp", on=True)
        written = {d["device_id"]: d for d in (await status(client))["readiness"]["devices"]}
    assert probed["desk"]["state"] == "reachable"
    assert (
        probed["shelf"]["state"] == "failed" and probed["shelf"]["error_code"] == "INVALID_RESPONSE"
    )
    assert probed["lamp"]["state"] == "reachable"
    assert written["lamp"]["state"] == "reachable"


@pytest.mark.anyio
async def test_the_status_data_names_no_url_host_path_or_credential(tmp_path):
    harness = Harness(tmp_path, "control", desk="read")
    async with harness.resources, Client(harness.server) as client:
        await call(client, "wled_get_state", device_id="shelf")
        data = await status(client)
    text = json.dumps(data)
    for host in HOSTS.values():
        assert host not in text
    for fragment in ("http://", "https://", str(tmp_path), "config.toml", "token", "Bearer"):
        assert fragment not in text, fragment
    assert data["service"]["name"] == "wled-mcp" and data["service"]["version"] == __version__
    assert set(data) == {"service", "access", "liveness", "readiness", "calls", "backups"}
    assert data["liveness"]["status"] == "alive"
    assert "TCP connect" in data["liveness"]["definition"]
    assert "ping" in data["liveness"]["definition"]


@pytest.mark.anyio
async def test_call_counters_are_bounded_by_fixed_keys_and_exclude_the_current_call(tmp_path):
    harness = Harness(tmp_path, "read-only")
    async with harness.resources, Client(harness.server) as client:
        first = await status(client)
        await call(client, "wled_get_state", device_id="desk")
        await call(client, "wled_get_state", device_id="absent")
        await call(client, "wled_get_state", device_id=PLANTED[0])
        await call(client, "wled_get_state", device_id="desk", bogus=PLANTED[1])
        with pytest.raises(MCPError):
            await client.call_tool("wled_set_state", {})
        with pytest.raises(MCPError):
            await client.call_tool(PLANTED[2], {})
        counts = (await status(client))["calls"]
    assert first["calls"]["total"] == 0  # the status call counts only after it answered
    assert counts["total"] == 7 and counts["ok"] == 2  # the first status call and one read
    assert counts["failed"] == 5 and counts["unknown_tool"] == 2
    assert counts["by_class"] == {"read": 5, "control": 0, "manage": 0}  # unknown tools: none
    assert counts["by_error_code"] == {
        "UNKNOWN_DEVICE": 2,
        "UNKNOWN_TOOL": 2,
        "VALIDATION_ERROR": 1,
    }
    assert set(counts["by_error_code"]) <= diagnostics.LOGGED_ERROR_CODES
    assert PLANTED[0] not in json.dumps(counts) and PLANTED[2] not in json.dumps(counts)


def test_the_last_control_store_keeps_one_bounded_allowlisted_entry_per_device():
    """S3-EXPLAIN-01 (#30): configured devices only, latest entry, fixed error vocabulary."""
    from datetime import UTC, datetime

    ticks = iter(datetime(2026, 1, 1, 0, 0, n, tzinfo=UTC) for n in range(10))
    store = diagnostics.LastControlStore(["desk"], lambda: next(ticks))
    store.record("absent", "wled_set_state", "applied", "verified", None)
    store.record(None, "wled_set_state", "applied", "verified", None)
    store.record("desk", "wled_set_state", "applied", "verified", None)
    store.record("desk", "wled_patch_segments", "unknown", "mismatch", "http://secret.invalid")
    latest = store.latest("desk")
    assert latest is not None and store.latest("absent") is None
    assert (latest.operation, latest.error_code) == ("wled_patch_segments", None)
    assert latest.finished_at.second == 1  # the second accepted record replaced the first
    assert ServiceMonitor(["desk"]).last_control.latest("desk") is None


def test_the_monitor_ignores_unconfigured_devices_and_keeps_bounded_state():
    tick = [0.0]
    monitor = ServiceMonitor(["desk"], lambda: tick[0])
    monitor.observe("planted-device", None)
    for _ in range(500):
        monitor.observe("planted-device", "TIMEOUT")
        monitor.record_call(ToolClass.READ, False, "VALIDATION_ERROR")
        tick[0] += 1
    assert [d["state"] for d in monitor.device_states()] == ["unknown"]
    assert monitor._observed == {}  # nothing is stored for a device that is not configured
    assert len(monitor.call_counts()["by_error_code"]) == 1
    monitor.observe("desk", "TIMEOUT")
    tick[0] += 7
    assert monitor.device_states() == [
        {"device_id": "desk", "state": "failed", "age_seconds": 7, "error_code": "TIMEOUT"}
    ]
    assert monitor.uptime_seconds() == 507
    assert monitor.backups_writable is None  # never claimed without a startup check


@pytest.mark.anyio
async def test_the_client_observer_sees_only_requests_that_reached_the_transport(tmp_path):
    router = make_router()
    router.set(HOSTS["desk"], "/json/info", httpx.TimeoutException("planted"))
    router.set(HOSTS["shelf"], "/json/info", httpx.InvalidURL("planted"))
    seen: list[tuple[str, str | None]] = []
    config = make_config(tmp_path)
    client = WLEDClient(
        HTTPSettings(operation_timeout_seconds=0.5),
        router.transport(),
        observer=lambda device_id, code: seen.append((device_id, code)),
    )
    from wled_mcp.client import ClientFailure, Deadline, Endpoint

    devices = {device.id: device for device in config.devices}
    try:
        for name in ("desk", "shelf", "lamp"):
            try:
                await client.read(devices[name], Endpoint.INFO, Deadline.after(2))
            except ClientFailure:
                pass
        sent = len(router.calls)
        with pytest.raises(ClientFailure):
            await client.read(devices["lamp"], Endpoint.INFO, Deadline(anyio.current_time() - 1))
        assert len(router.calls) == sent  # an expired deadline sent nothing ...
    finally:
        await client.aclose()
    assert ("desk", "TIMEOUT") in seen  # a timeout is an observation
    assert ("lamp", "TIMEOUT") not in seen  # an exhausted deadline is not
    assert all(device_id != "shelf" for device_id, _ in seen)  # a rejected address is not
    assert seen.count(("lamp", None)) == 1  # ... and was not observed either


@pytest.mark.anyio
async def test_a_failing_observer_cannot_change_the_outcome_of_a_request(tmp_path):
    router = make_router()
    router.set(HOSTS["shelf"], "/json/info", httpx.TimeoutException("planted"))
    calls: list[str] = []

    def broken(device_id: str, code: str | None) -> None:
        calls.append(device_id)
        raise RuntimeError("planted observer fault")

    from wled_mcp.client import ClientFailure, Deadline, Endpoint

    config = make_config(tmp_path)
    devices = {device.id: device for device in config.devices}
    client = WLEDClient(HTTPSettings(operation_timeout_seconds=0.5), router.transport(), broken)
    try:
        written = await client.post_state(devices["desk"], b'{"on":true}', Deadline.after(2))
        read = await client.read(devices["desk"], Endpoint.INFO, Deadline.after(2))
        with pytest.raises(ClientFailure) as failed:
            await client.read(devices["shelf"], Endpoint.INFO, Deadline.after(2))
    finally:
        await client.aclose()
    assert written == {"success": True}  # the write result is what the device answered
    assert isinstance(read, dict)
    assert failed.value.error.code == "TIMEOUT"  # not replaced by the observer's exception
    assert router.count("POST") == 1  # and nothing was replayed
    assert "desk" in calls and "shelf" in calls  # the observer really was called


@pytest.mark.anyio
async def test_the_startup_backups_check_is_made_once_and_passed_on(tmp_path, monkeypatch):
    harness = Harness(tmp_path)
    checked: list[Path] = []

    def spy(data_dir: Path) -> bool:
        checked.append(data_dir)
        return True

    monkeypatch.setattr(cli.setup, "backups_writable", spy)
    async with harness.resources:
        cli.attach_monitor(harness.resources, "stdio", False)
        assert harness.resources.monitor.backups_writable is False and checked == []
        cli.attach_monitor(harness.resources, "stdio")  # no result handed over: checks here
        assert harness.resources.monitor.backups_writable is True and checked == [tmp_path]


# ============================================== T20-17 no outbound traffic, no polling


@pytest.mark.anyio
async def test_a_full_tool_pass_opens_no_connection_besides_the_configured_devices(
    tmp_path, monkeypatch
):
    attempts: list[str] = []

    def refuse(*args: Any, **kwargs: Any) -> Any:
        attempts.append("socket")
        raise AssertionError("a tool pass must not open sockets or resolve names")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    harness = Harness(tmp_path)
    async with harness.resources, Client(harness.server) as client:
        for tool in (await client.list_tools()).tools:
            properties = tool.input_schema.get("properties", {})
            arguments: dict[str, Any] = {"device_id": "desk"} if "device_id" in properties else {}
            await client.call_tool(tool.name, arguments)
    assert attempts == []
    hosts = {host for _method, host, _path in harness.router.calls}
    assert hosts <= set(HOSTS.values())  # every request went to a configured device


@pytest.mark.anyio
async def test_nothing_runs_in_the_background_between_calls(tmp_path):
    harness = Harness(tmp_path)
    async with harness.resources, Client(harness.server) as client:
        await call(client, "wled_get_state", device_id="desk")
        sent = harness.requests()
        harness.time.advance(3600)
        await anyio.sleep(0.05)  # an hour of fake time and real scheduling passes
        assert harness.requests() == sent
        data = await status(client)
    assert {d["device_id"]: d for d in data["readiness"]["devices"]}["desk"]["age_seconds"] == 3600
    assert data["readiness"]["counts"]["unknown"] == 2


# ===================================================== TD-20-12 rotation and tenancy docs


def read_text(relative: str) -> str:
    return " ".join((ROOT / relative).read_text(encoding="utf-8").split())


def test_the_contract_states_restart_based_rotation_and_no_tenancy():
    contract = read_text("docs/contract/diagnostics.md")
    assert "Credential rotation is restart-based" in contract
    assert "no per-credential scopes" in contract
    assert "does not give tenant isolation" in contract
    assert "deployment setting, not a tenancy boundary" in contract
    assert "no unauthenticated health route" in contract
    assert "no outbound telemetry" in contract
    deployment = read_text("docs/DEPLOYMENT.md")
    assert "shared credential" in deployment and "tenant" in deployment


def test_the_documents_link_the_diagnostics_contract_and_the_validation_file():
    tool_contract = read_text("docs/TOOL-CONTRACT.md")
    assert "contract/diagnostics.md" in tool_contract
    assert "wled_get_service_status" in tool_contract and "correlation_id" in tool_contract
    assert "validation/issue-20.md" in read_text("docs/VALIDATION.md")
    assert "wled_get_service_status" in read_text("docs/WLED-COVERAGE.md")
