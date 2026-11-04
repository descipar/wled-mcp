import json
import sys
from pathlib import Path

import anyio
import httpx2 as httpx
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from pydantic import ValidationError

from wled_mcp.client import ClientFailure, Deadline, Endpoint
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


@pytest.mark.anyio
async def test_inventory_no_probe_zero_http_and_independent_probes(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.host == "desk.invalid":
            return httpx.Response(200, json={"ver": "0.15.1"})
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


@pytest.mark.anyio
async def test_one_total_deadline_and_bounded_read_retry(tmp_path):
    calls = []

    async def handler(request):
        calls.append(request)
        await anyio.sleep(0.04)
        raise httpx.ReadTimeout("synthetic-secret")

    async with Resources(
        config(tmp_path, operation_timeout_seconds=0.05), httpx.MockTransport(handler)
    ) as resources:
        start = anyio.current_time()
        with pytest.raises(ClientFailure) as caught:
            await resources.client.read(device(), Endpoint.INFO, Deadline.after(0.05))
        assert caught.value.error.code == "TIMEOUT"
        assert len(calls) == 2
        assert anyio.current_time() - start < 0.5


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
