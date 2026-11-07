import json
import socket
import sys
from pathlib import Path

import anyio
import httpx2 as httpx
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from pydantic import ValidationError

from wled_mcp.client import ClientFailure, Deadline, Endpoint, WLEDClient
from wled_mcp.config import ConfigurationError, Device, HTTPSettings, StartupConfig, load_config
from wled_mcp.operations import ListDevicesRequest, build_operations
from wled_mcp.resources import Resources


@pytest.fixture
def anyio_backend():
    return "asyncio"


def device(identifier="desk"):
    return Device(
        id=identifier, name=f"Example {identifier}", base_url=f"http://{identifier}.invalid"
    )


def config(tmp_path, *, devices=None, **settings):
    return StartupConfig(
        tmp_path / "config.toml",
        tmp_path,
        tuple(devices if devices is not None else [device()]),
        HTTPSettings(**settings),
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.invalid:8080/",
        "https://example.invalid",
        "http://127.0.0.1:81",
        "http://[2001:db8::1]:80/",
    ],
)
def test_valid_roots(url):
    assert Device(id="strip_1", name="Example", base_url=url).base_url == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.invalid",
        "http://user:synthetic-secret@example.invalid",
        "http://example.invalid/path",
        "http://example.invalid?",
        "http://example.invalid#",
        "http://example.invalid?q=synthetic-secret",
        "http://example.invalid/#synthetic-secret",
        "http://",
        "http:///",
        "http://example.invalid:0",
        "http://example.invalid:65536",
        "http://example.invalid:",
        "http://[not-ipv6]",
        "http://exam ple.invalid",
        "http://example.invalid\\foreign.invalid",
        "http://example.invalid/%2f",
        "http://a..invalid",
        "http://-a.invalid",
    ],
)
def test_reject_urls_before_any_client(tmp_path, url):
    path = tmp_path / "inventory.toml"
    path.write_text(
        "schema_version=1\ndevices="
        + json.dumps([{"id": "desk", "name": "Example", "base_url": url}]).replace(": ", " = "),
        encoding="utf-8",
    )
    # Use TOML inline tables; malformed/credential-bearing content is always safe.
    path.write_text(
        f'schema_version=1\n[[devices]]\nid="desk"\nname="Example"\nbase_url={json.dumps(url)}',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(path), str(tmp_path), {})
    assert "synthetic-secret" not in str(caught.value)
    assert url not in str(caught.value)


@pytest.mark.parametrize(
    "suffix",
    [
        "\n[http]\nread_retries=true",
        "\n[http]\nread_retries=2",
        "\n[http]\noperation_timeout_seconds=nan",
        "\n[http]\noperation_timeout_seconds=0",
        "\n[http]\nmax_response_bytes=99999999",
        "\n[features]\nraw_state_patch=true",
        "\n[backups]\nretain_per_device=0",
        '\n[http]\nunsupported="synthetic-secret"',
    ],
)
def test_bad_settings_are_not_ignored(tmp_path, suffix):
    path = tmp_path / "inventory.toml"
    path.write_text("schema_version=1\ndevices=[]" + suffix, encoding="utf-8")
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(path), str(tmp_path), {})
    assert "synthetic-secret" not in str(caught.value)


def test_full_example_and_duplicate_inventory(tmp_path):
    example = Path(__file__).parents[1] / "examples/devices.example.toml"
    loaded = load_config(str(example.resolve()), str(tmp_path), {})
    assert [item.id for item in loaded.devices] == ["desk", "shelf"]
    with pytest.raises(ValidationError):
        loaded.devices[0].name = "changed"
    duplicate = tmp_path / "duplicate.toml"
    duplicate.write_text(
        "schema_version=1\n"
        + "\n".join(
            '[[devices]]\nid="desk"\nname="Example"\nbase_url="http://desk.invalid"'
            for _ in range(2)
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        load_config(str(duplicate), str(tmp_path), {})


# Issue #61: underscores inside DNS host labels (ISSUE-61-DEC-001/002).
LONG_LABEL = "a" * 30 + "_" + "b" * 32  # 63 characters, interior underscore
LONG_HOST = ".".join(["a_" + "b" * 60] * 4) + ".ab"  # 254 characters


@pytest.mark.parametrize(
    "url",
    [
        "http://wled_desk.example.invalid",
        "http://WLED_Desk.example.invalid:8080/",
        "http://wled_desk",
        "http://desk.wled_lan",
        "http://a_b-c.example.invalid",
        "http://a__b.example.invalid",
        f"http://{LONG_LABEL}.example.invalid",
    ],
)
def test_underscore_host_labels_accepted(url):
    assert Device(id="desk", name="Example", base_url=url).base_url == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        # S61-2: label rules
        "http://_wled.example.invalid",
        "http://wled_.example.invalid",
        "http://_.example.invalid",
        "http://a._.invalid",
        "http://wled_desk.invalid_",
        f"http://{LONG_LABEL}c.example.invalid",
        f"http://{LONG_HOST}",
        "http://wled_desk.invalid.",
        # S61-3: underscore hosts combined with otherwise forbidden parts
        "http://user:synthetic-secret@wled_desk.invalid",
        "http://wled_desk.invalid?q=synthetic-secret",
        "http://wled_desk.invalid/#synthetic-secret",
        "http://wled_desk.invalid/path",
        "http://wled%5Fdesk.invalid",
        "ftp://wled_desk.invalid",
        "http://wled_desk.invalid:0",
        "http://wled_desk.invalid\\x.invalid",
    ],
)
def test_underscore_host_rule_stays_fail_closed(tmp_path, url):
    with pytest.raises(ValidationError):
        Device(id="desk", name="Example", base_url=url)
    path = tmp_path / "inventory.toml"
    path.write_text(
        f'schema_version=1\n[[devices]]\nid="desk"\nname="Example"\nbase_url={json.dumps(url)}',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(path), str(tmp_path), {})
    message = str(caught.value)
    assert "synthetic-secret" not in message and url not in message
    assert "wled_desk" not in message and "devices[0].base_url: invalid" in message


def test_rejected_label_lengths_are_real_boundaries():
    assert len(LONG_LABEL) == 63
    assert len(LONG_HOST) == 254
    Device(id="desk", name="Example", base_url=f"http://{LONG_LABEL}.example.invalid")
    Device(id="desk", name="Example", base_url=f"http://{LONG_HOST[:-1]}")


def write_inventory(path, entries):
    lines = ["schema_version = 1"]
    for entry in entries:
        lines.append("[[devices]]")
        lines.extend(f"{key} = {json.dumps(value)}" for key, value in entry.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def entry(identifier, base_url=None, **extra):
    values = {"id": identifier, "name": f"Synthetic {identifier} name"}
    if base_url is not False:
        values["base_url"] = base_url or f"http://{identifier}.invalid"
    return values | extra


SECRET_URL = "http://user:synthetic-secret@wled_x.invalid"


def located_error(tmp_path, entries):
    path = write_inventory(tmp_path / "inventory.toml", entries)
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(path), str(tmp_path), {})
    message = str(caught.value)
    for value in ("synthetic-secret", SECRET_URL, "wled_x", "Synthetic", "synthetic_secret"):
        assert value not in message
    for item in entries:
        assert f"http://{item['id']}" not in message
    return message


def test_rejected_inventory_names_device_entry_without_values(tmp_path):
    message = located_error(
        tmp_path, [entry("desk"), entry("synthetic-id-1", SECRET_URL), entry("shelf")]
    )
    assert "devices[1].base_url: invalid" in message
    assert "devices[0]" not in message and "devices[2]" not in message
    assert "synthetic-id-1" not in message
    assert message.startswith("Invalid inventory configuration (")
    assert "credential-free HTTP(S) root URLs" in message


def test_rejected_inventory_names_every_bad_entry_in_order(tmp_path):
    message = located_error(
        tmp_path,
        [
            entry("desk"),
            entry("bad-one", SECRET_URL),
            entry("shelf"),
            entry("bad-two", "http://_wled_x.invalid"),
        ],
    )
    assert message.index("devices[1].base_url: invalid") < message.index(
        "devices[3].base_url: invalid"
    )


def test_unknown_key_and_missing_field_are_categorized(tmp_path):
    message = located_error(
        tmp_path,
        [
            entry("desk", synthetic_secret_key="v", other_synthetic_secret_key="w"),
            entry("shelf", base_url=False),
        ],
    )
    assert message.count("devices[0]: unsupported field") == 1
    assert "devices[1].base_url: missing" in message


def test_device_locators_are_capped(tmp_path):
    message = located_error(
        tmp_path, [entry(f"bad-{index}", f"http://_wled_x{index}.invalid") for index in range(8)]
    )
    assert "devices[4].base_url: invalid" in message
    assert "devices[5]" not in message
    assert "and 3 more" in message


@pytest.mark.parametrize(
    "content",
    [
        "schema_version = true\ndevices = []",
        'schema_version = "2"\ndevices = []',
        "schema_version = 1\ndevices = []\n[http]\nread_retries = 2",
        "schema_version = 1\n"
        + '[[devices]]\nid = "desk"\nname = "Example"\nbase_url = "http://wled_desk.invalid"\n' * 2,
        'schema_version = 1\n[[devices]]\nid = "desk\nbase_url = "http://wled_x.invalid"',
    ],
)
def test_non_device_errors_keep_generic_message(tmp_path, content):
    path = tmp_path / "inventory.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(path), str(tmp_path), {})
    message = str(caught.value)
    assert message.startswith("Invalid inventory configuration: check schema version")
    assert "devices[" not in message and "wled_" not in message


@pytest.mark.parametrize(
    ("version", "downgrade_hint"), [(2, True), (99, True), (0, False), (-1, False)]
)
def test_unsupported_integer_schema_version_is_named(tmp_path, version, downgrade_hint):
    # Issue #21 (TD-21-5, A21-06): the reader names the version it cannot read.
    path = tmp_path / "inventory.toml"
    path.write_text(f"schema_version = {version}\ndevices = []\n", encoding="utf-8")
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(path), str(tmp_path), {})
    message = str(caught.value)
    assert message.startswith(
        f"Unsupported inventory configuration schema_version {version}; "
        "this server reads schema_version 1."
    )
    assert ("newer server version" in message) is downgrade_hint


@pytest.mark.anyio
async def test_underscore_host_reaches_transport_and_host_header_unchanged():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ver": "16.0.1"})

    item = Device(id="desk", name="Example", base_url="http://WLED_Desk.example.invalid:8080/")
    client = WLEDClient(HTTPSettings(), httpx.MockTransport(handler))
    try:
        assert await client.read(item, Endpoint.INFO, Deadline.after(1)) == {"ver": "16.0.1"}
    finally:
        await client.aclose()
    (request,) = requests
    assert request.url.host == "wled_desk.example.invalid"
    assert request.url.port == 8080 and request.url.path == "/json/info"
    assert request.headers["Host"] == "wled_desk.example.invalid:8080"


@pytest.mark.anyio
async def test_underscore_host_reaches_resolver_without_idna(monkeypatch):
    resolved = []

    def fake_getaddrinfo(host, *args, **kwargs):
        resolved.append(host)
        raise socket.gaierror(socket.EAI_NONAME, "synthetic resolver failure")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    item = Device(id="desk", name="Example", base_url="http://wled_desk.example.invalid")
    client = WLEDClient(HTTPSettings(read_retries=0))
    try:
        with pytest.raises(ClientFailure) as caught:
            await client.read(item, Endpoint.INFO, Deadline.after(2))
    finally:
        await client.aclose()
    assert caught.value.error.code == "UNREACHABLE"
    assert resolved and all(
        host in ("wled_desk.example.invalid", b"wled_desk.example.invalid") for host in resolved
    )


@pytest.mark.anyio
async def test_inventory_no_probe_zero_http_and_independent_probes(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.host == "desk.invalid":
            return httpx.Response(200, json={"ver": "16.0.1"})
        raise httpx.ReadTimeout("synthetic-secret http://shelf.invalid")

    async with Resources(
        config(tmp_path, devices=[device(), device("shelf")]), httpx.MockTransport(handler)
    ) as resources:
        operation = build_operations(resources)[0]
        result = await operation.execute({"probe": False})
        assert calls == []
        assert all(item["probe_status"] == "untested" for item in result.data["devices"])
        assert "base_url" not in result.model_dump_json()
        result = await operation.execute({"probe": True})
        assert result.ok
        assert [item["probe_status"] for item in result.data["devices"]] == ["reachable", "failed"]
        assert "synthetic-secret" not in result.model_dump_json()
        assert all(
            request.method == "GET" and request.url.path == "/json/info" for request in calls
        )
        assert len(calls) == 3  # one desk read, shelf read plus the single safe read retry
        with pytest.raises(ClientFailure, match="Unknown"):
            resources.resolve("http://foreign.invalid")
        assert len(calls) == 3
    for value in (1, "true", None):
        with pytest.raises(ValidationError):
            ListDevicesRequest(probe=value)


@pytest.mark.anyio
async def test_proxy_redirect_and_endpoint_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://synthetic-secret@foreign.invalid")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "http://foreign.invalid/json/info"})

    async with Resources(config(tmp_path), httpx.MockTransport(handler)) as resources:
        assert resources.client.http.trust_env is False
        with pytest.raises(ClientFailure) as caught:
            await resources.client.read(device(), Endpoint.INFO, Deadline.after(1))
        assert caught.value.error.code == "INVALID_RESPONSE"
        assert len(calls) == 1
        for endpoint in ("http://foreign.invalid", "/json/info?x=1", "/%2e%2e/config"):
            with pytest.raises(ClientFailure):
                await resources.client.read(device(), endpoint, Deadline.after(1))
        assert len(calls) == 1
    assert resources.client.http.is_closed


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks, self.closed = chunks, False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body,headers",
    [
        ([b"{}"], {"content-type": "text/html"}),
        ([b"synthetic-secret"], {"content-type": "application/json"}),
        ([b"\xff"], {"content-type": "application/json"}),
        ([b"[]"], {"content-type": "application/json"}),
        ([b'{"x":NaN}'], {"content-type": "application/json"}),
        (
            [b"{" + b" " * 100, b" " * 100 + b"}"],
            {"content-type": "application/json", "content-length": "1"},
        ),
        ([b"{}"], {"content-type": "application/json", "content-encoding": "gzip"}),
    ],
)
async def test_response_validation_stream_closure_and_no_retry(tmp_path, body, headers):
    stream = Chunks(body)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers=headers, stream=stream)

    async with Resources(
        config(tmp_path, max_response_bytes=128), httpx.MockTransport(handler)
    ) as resources:
        with pytest.raises(ClientFailure) as caught:
            await resources.client.read(device(), Endpoint.INFO, Deadline.after(1))
        assert caught.value.error.code == "INVALID_RESPONSE"
        assert "synthetic-secret" not in str(caught.value)
        assert len(calls) == 1 and stream.closed


@pytest.fixture
def shifted_clock(monkeypatch):
    """Controlled time (as in the T09 budget test): `Deadline` reads `anyio.current_time`,
    so advancing the offset consumes the shared budget without wall-clock sleeps. This keeps
    the deadline/retry tests independent of OS timer granularity (issue #55)."""
    offset = {"value": 0.0}
    real_time = anyio.current_time
    monkeypatch.setattr(anyio, "current_time", lambda: real_time() + offset["value"])
    return offset


TOTAL_SECONDS = 5.0
# Real time spent in the mocked path is milliseconds; budget checks tolerate a full second.
WALL_CLOCK_MARGIN = 1.0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "consumed,expected_calls",
    [
        pytest.param((4.9, 0.0), 2, id="shared_remainder"),
        pytest.param((1.0, 1.0), 2, id="retry_bound"),
        pytest.param((5.1,), 1, id="expired_before_retry"),
    ],
)
async def test_one_total_deadline_and_bounded_read_retry(
    tmp_path, shifted_clock, consumed, expected_calls
):
    calls, budgets = [], []

    async def handler(request):
        calls.append(request)
        budgets.append(request.extensions["timeout"]["read"])
        shifted_clock["value"] += consumed[len(calls) - 1]
        raise httpx.ReadTimeout("synthetic-secret")

    async with Resources(
        config(tmp_path, operation_timeout_seconds=TOTAL_SECONDS), httpx.MockTransport(handler)
    ) as resources:
        with pytest.raises(ClientFailure) as caught:
            await resources.client.read(device(), Endpoint.INFO, Deadline.after(TOTAL_SECONDS))
    assert caught.value.error.code == "TIMEOUT"
    assert "synthetic-secret" not in str(caught.value)
    # At most one retry, and none once the shared deadline has expired.
    assert len(calls) == expected_calls
    assert TOTAL_SECONDS - WALL_CLOCK_MARGIN < budgets[0] <= TOTAL_SECONDS
    if expected_calls == 2:
        # The retry gets the remainder of the same deadline, not a fresh full budget.
        remainder = TOTAL_SECONDS - consumed[0]
        assert max(0.0, remainder - WALL_CLOCK_MARGIN) < budgets[1] <= remainder


@pytest.mark.anyio
async def test_hanging_read_retry_is_cut_at_shared_deadline(tmp_path, shifted_clock):
    calls, cancelled = [], []

    async def handler(request):
        calls.append(request)
        if len(calls) == 1:
            shifted_clock["value"] += TOTAL_SECONDS - 0.1
            raise httpx.ReadTimeout("synthetic-secret")
        try:
            await anyio.sleep_forever()
        except anyio.get_cancelled_exc_class():
            cancelled.append(True)
            raise

    async with Resources(
        config(tmp_path, operation_timeout_seconds=TOTAL_SECONDS), httpx.MockTransport(handler)
    ) as resources:
        start = anyio.current_time()
        with pytest.raises(ClientFailure) as caught:
            await resources.client.read(device(), Endpoint.INFO, Deadline.after(TOTAL_SECONDS))
        real_elapsed = anyio.current_time() - start - shifted_clock["value"]
    assert caught.value.error.code == "TIMEOUT"
    assert "synthetic-secret" not in str(caught.value)
    assert len(calls) == 2 and cancelled == [True]
    # About 0.1 s of shared budget remained; a fresh per-attempt deadline would hang ~5 s.
    assert real_elapsed < 2.0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure,readback,expected",
    [
        ("timeout", "match", (True, "applied", "verified")),
        ("reset", "match", (True, "applied", "verified")),
        ("timeout", "mismatch", (False, "unknown", "mismatch")),
        ("reset", "unavailable", (False, "unknown", "unknown")),
        ("slow", "match", (True, "applied", "verified")),
        ("ack", "mismatch", (False, "unknown", "mismatch")),
    ],
)
async def test_write_once_reconciliation_and_reserve(tmp_path, failure, readback, expected):
    calls = []

    async def handler(request):
        calls.append(request)
        if request.method == "POST":
            if failure == "slow":
                await anyio.sleep_forever()
            if failure == "timeout":
                raise httpx.WriteTimeout("synthetic-secret")
            if failure == "reset":
                raise httpx.ReadError("synthetic-secret")
            return httpx.Response(200, json={"success": True})
        if readback == "unavailable":
            raise httpx.ConnectError("synthetic-secret")
        return httpx.Response(200, json={"on": readback == "match"})

    async def prepare(context):
        return {"on": True}

    async with Resources(
        config(tmp_path, operation_timeout_seconds=0.2), httpx.MockTransport(handler)
    ) as resources:
        result = await resources.write_verified(
            "desk", "synthetic_write", prepare, lambda state: state.get("on") is True
        )
        assert (result.ok, result.application, result.verification) == expected
        assert sum(request.method == "POST" for request in calls) == 1
        assert "synthetic-secret" not in result.model_dump_json()
        if result.error:
            assert result.error.write_retryable is False


@pytest.mark.anyio
async def test_validation_and_oversize_before_send(tmp_path):
    calls = []
    async with Resources(
        config(tmp_path, max_request_bytes=128),
        httpx.MockTransport(lambda request: calls.append(request)),
    ) as resources:
        for payload in ({"secret": "x" * 200}, {"x": float("nan")}, {1: "x"}):

            async def prepare(context, payload=payload):
                return payload

            result = await resources.write_verified(
                "desk", "synthetic", prepare, lambda state: True
            )
            assert not result.ok and result.application == "not_attempted"
            assert result.error.code == "VALIDATION_ERROR"
        assert calls == []


@pytest.mark.anyio
async def test_same_device_full_workflow_lock_other_devices_progress_and_cancel(tmp_path):
    entered, release, second, other = (anyio.Event() for _ in range(4))
    async with Resources(config(tmp_path, devices=[device(), device("shelf")])) as resources:

        async def first():
            async with resources.operation("desk"):
                entered.set()
                await release.wait()
                assert not second.is_set()

        async def following():
            await entered.wait()
            async with resources.operation("desk"):
                second.set()

        async def independent():
            await entered.wait()
            async with resources.operation("shelf"):
                other.set()

        async with anyio.create_task_group() as group:
            group.start_soon(first)
            group.start_soon(following)
            group.start_soon(independent)
            with anyio.fail_after(1):
                await other.wait()
                assert not second.is_set()
                release.set()
        assert second.is_set()
        with anyio.move_on_after(0.01):
            async with resources.operation("desk"):
                await anyio.sleep_forever()
        async with resources.operation("desk"):
            assert resources.locks["desk"].locked()


@pytest.mark.anyio
async def test_lock_wait_deadline_and_shared_session_resource_lifetime(tmp_path):
    async with Resources(config(tmp_path, operation_timeout_seconds=0.05)) as resources:
        first, second = build_operations(resources), build_operations(resources)
        assert first[0].execute is not second[0].execute
        assert first[0].execute.__closure__[0].cell_contents is resources
        assert second[0].execute.__closure__[0].cell_contents is resources
        assert not resources.backups.directory.exists()
        held, release = anyio.Event(), anyio.Event()

        async def holder():
            async with resources.locks["desk"]:
                held.set()
                await release.wait()

        async with anyio.create_task_group() as group:
            group.start_soon(holder)
            await held.wait()
            with pytest.raises(ClientFailure) as caught:
                async with resources.operation("desk"):
                    pytest.fail("Lock cannot be entered before the deadline")
            assert caught.value.error.code == "TIMEOUT"
            release.set()
    assert resources.client.http.is_closed


@pytest.mark.anyio
async def test_real_stdio_inventory_schema_and_mock_probes():
    root = Path(__file__).resolve().parents[1]
    with anyio.fail_after(15):
        params = StdioServerParameters(
            command=sys.executable, cwd=root, args=["-m", "tests.inventory_fixture"]
        )
        async with Client(params, mode="legacy", read_timeout_seconds=5) as client:
            tool = (await client.list_tools()).tools[0]
            assert tool.name == "wled_list_devices"
            assert tool.annotations.read_only_hint
            assert tool.input_schema["additionalProperties"] is False
            for probe in (False, True):
                result = await client.call_tool(tool.name, {"probe": probe})
                envelope = result.structured_content
                assert json.loads(result.content[0].text) == envelope
                assert not result.is_error
                assert [item["id"] for item in envelope["data"]["devices"]] == ["desk", "shelf"]
                assert "base_url" not in json.dumps(envelope)
            result = await client.call_tool(tool.name, {"probe": 1})
            assert result.is_error
            result = await client.call_tool(tool.name, {"host": "http://foreign.invalid"})
            assert result.is_error


# Issue #74: IPv4-like hosts (ISSUE-74-DEC-001/002). Every test below is offline: hosts
# are validated locally, requests go to httpx.MockTransport or an in-process MCP client,
# and the ``no_network`` guard fails any resolution or socket connect attempt.


@pytest.fixture
def no_network(monkeypatch):
    attempts = []

    def refuse(*args, **kwargs):
        attempts.append(args[:1])
        raise AssertionError("issue #74 tests must not resolve names or open connections")

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    yield attempts
    assert attempts == []


@pytest.mark.parametrize(
    "url",
    [
        "http://192.0.2.10",
        "http://198.51.100.255:8080/",
        "http://127.0.0.1:81",
        "http://123.example.invalid",
        "http://1.2.3.4.example.invalid",
        "http://0xdesk.example.invalid",
        "http://desk.1a",
        "http://wled_1.example.invalid",
        "http://1e3",
    ],
)
def test_ipv4_rule_keeps_canonical_addresses_and_dns_names(url):
    """S74-1: canonical dotted quads and names with a non-numeric last label pass."""
    assert Device(id="desk", name="Example", base_url=url).base_url == url.rstrip("/")


NON_CANONICAL_HOSTS = [
    "999.1.1.1",
    "1.2.3",
    "256.0.0.1",
    "01.2.3.4",
    "1.2.3.04",
    "0.0.0.256",
    "1.2.3.4.5",
    "127.1",
    "0x7f.1",
    "0X7F.0.0.1",
    "0x7f000001",
    "017700000001",
    "2130706433",
    "4294967296",
    "123",
    "0xface",
    "desk.123",
    "wled.0x1",
    "wled.0x",
    "wled_1.2",
]


@pytest.mark.parametrize(
    "url", [f"http://{host}" for host in NON_CANONICAL_HOSTS] + ["http://999.1.1.1:8080/"]
)
def test_non_canonical_numeric_hosts_rejected_with_fixed_text(tmp_path, url):
    """S74-2: hosts ending in a number must be canonical dotted-quad IPv4 addresses."""
    with pytest.raises(ValidationError) as caught:
        Device(id="desk", name="Example", base_url=url)
    (error,) = caught.value.errors(include_url=False, include_input=False)
    assert error["loc"] == ("base_url",)
    assert error["msg"] == "Value error, Invalid host"
    host = url.removeprefix("http://").split(":")[0].rstrip("/")
    assert host not in error["msg"] and host.lower() not in error["msg"]
    path = write_inventory(tmp_path / "inventory.toml", [entry("desk", url)])
    with pytest.raises(ConfigurationError) as config_error:
        load_config(str(path), str(tmp_path), {})
    assert "devices[0].base_url: invalid" in str(config_error.value)
    assert host not in str(config_error.value)


S74_INVENTORY = [entry("desk"), entry("bad", "http://203.0.113.777"), entry("shelf")]


def test_numeric_host_locator_without_echo_and_suppressed_context(tmp_path):
    """S74-3 / TD-74-4: #61 locator, no host text and no chained original exception."""
    path = write_inventory(tmp_path / "inventory.toml", S74_INVENTORY)
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(path), str(tmp_path), {})
    message = str(caught.value)
    assert "devices[1].base_url: invalid" in message
    assert "devices[0]" not in message and "devices[2]" not in message
    assert "777" not in message and "203.0.113" not in message
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


BAD_HOSTS = ["999.1.1.1", "01.2.3.4", "0.0.0.256"]


def unvalidated(host, identifier="bad"):
    """Defense in depth: a Device that bypassed inventory validation."""
    return Device.model_construct(id=identifier, name="Example bad", base_url=f"http://{host}")


def assert_no_host(text, host):
    for value in (host, "999", "01.2.3.4", "0.0.0.256", "http://"):
        assert value not in text


@pytest.mark.anyio
@pytest.mark.parametrize("host", BAD_HOSTS)
async def test_invalid_url_maps_to_config_error_before_any_send(no_network, host):
    """S74-5: httpx2 InvalidURL becomes CONFIG_ERROR, without retry, send or host echo."""
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ver": "16.0.1"})

    client = WLEDClient(HTTPSettings(read_retries=1), httpx.MockTransport(handler))
    try:
        failures = []
        with pytest.raises(ClientFailure) as caught:
            await client.read(unvalidated(host), Endpoint.INFO, Deadline.after(2))
        failures.append(caught.value)
        with pytest.raises(ClientFailure) as caught:
            await client.post_state(unvalidated(host), b'{"on":true}', Deadline.after(2))
        failures.append(caught.value)
    finally:
        await client.aclose()
    assert calls == []
    for failure in failures:
        assert failure.error.code == "CONFIG_ERROR"
        assert failure.error.read_retryable is False
        assert "no request was sent" in failure.error.message
        assert_no_host(failure.error.model_dump_json(), host)
        assert_no_host(str(failure), host)
        assert failure.__cause__ is None
        assert failure.__suppress_context__ is True


@pytest.mark.anyio
async def test_invalid_url_mapping_is_narrow(no_network):
    """S74-6: other outcomes keep their existing codes; unrelated errors are not remapped."""
    item = Device(id="desk", name="Example", base_url="http://192.0.2.10")
    outcomes = iter(["json", "connect", "malformed", "unrelated"])

    def handler(request):
        outcome = next(outcomes)
        if outcome == "connect":
            raise httpx.ConnectError("synthetic", request=request)
        if outcome == "unrelated":
            raise RuntimeError("synthetic unrelated")
        if outcome == "malformed":
            return httpx.Response(200, content=b"{", headers={"Content-Type": "application/json"})
        return httpx.Response(200, json={"ver": "16.0.1"})

    client = WLEDClient(HTTPSettings(read_retries=0), httpx.MockTransport(handler))
    try:
        assert await client.read(item, Endpoint.INFO, Deadline.after(2)) == {"ver": "16.0.1"}
        with pytest.raises(ClientFailure) as caught:
            await client.read(item, Endpoint.INFO, Deadline.after(2))
        assert caught.value.error.code == "UNREACHABLE"
        assert caught.value.error.read_retryable is True
        with pytest.raises(ClientFailure) as caught:
            await client.read(item, Endpoint.INFO, Deadline.after(2))
        assert caught.value.error.code == "INVALID_RESPONSE"
        with pytest.raises(RuntimeError, match="synthetic unrelated"):
            await client.read(item, Endpoint.INFO, Deadline.after(2))
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_invalid_url_gives_envelopes_and_probe_entries_at_tool_level(tmp_path, no_network):
    """S74-7: read, write and probe tools return domain results, never a protocol error."""
    from mcp import MCPError

    from wled_mcp.server import create_server

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ver": "16.0.1"})

    good = Device(id="desk", name="Example desk", base_url="http://192.0.2.10")
    inventory = config(tmp_path, devices=[unvalidated("999.1.1.1"), good])
    async with Resources(inventory, httpx.MockTransport(handler)) as resources:
        server = create_server(build_operations(resources))
        async with Client(server, mode="legacy", read_timeout_seconds=10) as client:
            results = []
            for tool, arguments in [
                ("wled_get_state", {"device_id": "bad"}),
                ("wled_set_state", {"device_id": "bad", "on": True}),
            ]:
                try:
                    result = await client.call_tool(tool, arguments)
                except MCPError as exc:  # the regression being guarded
                    pytest.fail(f"{tool} raised a protocol error: {exc}")
                assert result.is_error is True
                envelope = result.structured_content
                assert envelope["ok"] is False
                assert envelope["operation"] == tool
                assert envelope["application"] == "not_attempted"
                assert envelope["error"]["code"] == "CONFIG_ERROR"
                results.append(result)
            assert calls == []
            probe = await client.call_tool("wled_list_devices", {"probe": True})
            assert probe.is_error is False
            assert probe.structured_content["ok"] is True
            bad_entry, good_entry = probe.structured_content["data"]["devices"]
            assert bad_entry["probe_status"] == "failed"
            assert bad_entry["error"]["code"] == "CONFIG_ERROR"
            assert good_entry["probe_status"] == "reachable"
            results.append(probe)
    assert [request.method for request in calls] == ["GET"]
    assert all(request.url.host == "192.0.2.10" for request in calls)
    for result in results:
        assert_no_host(json.dumps(result.structured_content), "999.1.1.1")
        assert_no_host(json.dumps([item.model_dump() for item in result.content]), "999.1.1.1")
