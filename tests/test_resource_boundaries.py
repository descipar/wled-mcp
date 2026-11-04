import anyio
import httpx2 as httpx
import pytest

from tests.test_inventory_client import config, device
from wled_mcp.client import ClientFailure, Deadline, Endpoint
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_probe_worker_bound_and_independent_failures(tmp_path):
    active = maximum = calls = 0
    eight_entered, release = anyio.Event(), anyio.Event()

    async def handler(request):
        nonlocal active, maximum, calls
        active += 1
        calls += 1
        maximum = max(maximum, active)
        if active == 8:
            eight_entered.set()
        await release.wait()
        active -= 1
        return httpx.Response(200, json={"ver": "0.15.1"})

    async with Resources(
        config(tmp_path, devices=[device(f"strip{i}") for i in range(17)]),
        httpx.MockTransport(handler),
    ) as resources:

        async def probe():
            result = await build_operations(resources)[0].execute({"probe": True})
            assert len(result.data["devices"]) == 17

        async with anyio.create_task_group() as group:
            group.start_soon(probe)
            with anyio.fail_after(1):
                await eight_entered.wait()
                assert maximum == 8
                release.set()
        assert maximum == 8 and calls == 17


@pytest.mark.anyio
async def test_lock_covers_prepare_write_and_readback_across_sessions(tmp_path):
    readback_entered, release, second_post, other_done = (anyio.Event() for _ in range(4))
    posts = []

    async def handler(request):
        if request.method == "POST":
            posts.append(request.url.host)
            if posts.count("desk.invalid") == 2:
                second_post.set()
            return httpx.Response(200, json={"success": True})
        if request.url.host == "desk.invalid" and posts.count("desk.invalid") == 1:
            readback_entered.set()
            await release.wait()
        return httpx.Response(200, json={"on": True})

    async def prepare(context):
        assert context.client is resources.client
        assert context.deadline.remaining() <= resources.config.http.operation_timeout_seconds
        return {"on": True}

    async with Resources(
        config(tmp_path, devices=[device(), device("shelf")]), httpx.MockTransport(handler)
    ) as resources:

        async def first():
            result = await resources.write_verified(
                "desk", "test", prepare, lambda state: state["on"] is True
            )
            assert result.ok

        async def second():
            await readback_entered.wait()
            result = await resources.write_verified(
                "desk", "test", prepare, lambda state: state["on"] is True
            )
            assert result.ok

        async def independent():
            await readback_entered.wait()
            result = await resources.write_verified(
                "shelf", "test", prepare, lambda state: state["on"] is True
            )
            assert result.ok
            other_done.set()

        async with anyio.create_task_group() as group:
            group.start_soon(first)
            group.start_soon(second)
            group.start_soon(independent)
            with anyio.fail_after(1):
                await other_done.wait()
                assert not second_post.is_set()
                release.set()
        assert posts.count("desk.invalid") == 2 and posts.count("shelf.invalid") == 1


@pytest.mark.anyio
async def test_preparation_errors_and_exhausted_budget_no_write(tmp_path):
    calls = []
    async with Resources(
        config(tmp_path, operation_timeout_seconds=0.05),
        httpx.MockTransport(lambda request: calls.append(request)),
    ) as resources:

        async def invalid(context):
            raise ValueError("synthetic-secret")

        async def expired(context):
            # Deliberately consume the entire *same* deadline before dispatch.
            await anyio.sleep_forever()

        for prepare in (invalid, expired):
            result = await resources.write_verified("desk", "test", prepare, lambda state: True)
            assert not result.ok and result.application == "not_attempted"
            assert "synthetic-secret" not in result.model_dump_json()
        assert calls == []


@pytest.mark.anyio
async def test_read_status_parse_never_retry_and_request_bytes_guard(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"secret": "synthetic-secret"})

    async with Resources(
        config(tmp_path, max_request_bytes=128), httpx.MockTransport(handler)
    ) as resources:
        with pytest.raises(ClientFailure):
            await resources.client.read(device(), Endpoint.STATE, Deadline.after(1))
        assert len(calls) == 1
        for body in (b"{" + b" " * 200 + b"}", b"[]", b'{"a":Infinity}'):
            with pytest.raises(ClientFailure):
                await resources.client.post_state(device(), body, Deadline.after(1))
        assert len(calls) == 1


@pytest.mark.anyio
async def test_all_resources_same_identity_and_close_once(tmp_path):
    class CountingTransport(httpx.MockTransport):
        closes = 0

        async def aclose(self):
            self.closes += 1
            await super().aclose()

    transport = CountingTransport(lambda request: httpx.Response(200, json={}))
    async with Resources(config(tmp_path), transport) as resources:
        one = build_operations(resources)[0].execute.__closure__[0].cell_contents
        two = build_operations(resources)[0].execute.__closure__[0].cell_contents
        assert one is two is resources
        assert one.client is two.client
        assert one.metadata_cache is two.metadata_cache
        assert one.backups is two.backups
        assert one.locks["desk"] is two.locks["desk"]
    assert transport.closes == 1
