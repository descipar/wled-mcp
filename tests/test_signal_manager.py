"""Signal manager behaviour (issue #28, S3-T02): lifecycle, conflicts, failures, shutdown.

Mock controllers and a controlled clock only; nothing waits in real time and nothing contacts a
LAN device. Scenario IDs T28-xx are those of docs/validation/issue-28.md.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

import anyio
import pytest

from tests.signal_support import (
    BASE_COLOR,
    SOLID,
    WIPE,
    FakeController,
    host_of,
    make_env,
    signal_env,
    tree,
)
from wled_mcp.access import CURRENT_TOOL_CLASS, ToolClass


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def paused(env: Any, identifier: str) -> None:
    """Wait until the first restore attempt failed and the retry pause is the pending wait."""
    await env.until(
        lambda: (
            env.signals.get(identifier).status == "restoring"
            and [due for due, _ in env.timer.waiters] == [env.clock.t + 5]
        )
    )


def lit(controller: FakeController) -> tuple[bool, list[int], int]:
    segment = controller.segment(0)
    return controller.state["on"], segment["col"][0], segment["fx"]


# ------------------------------------------------------------- T28-02 expiry, unchanged state


@pytest.mark.anyio
async def test_expiry_restores_only_the_owned_fields(tmp_path):
    async with signal_env(tmp_path) as env:
        before = env.ctl.snapshot()
        started = await env.start(duration_seconds=10)
        assert started.ok and started.application == "applied"
        identifier = started.data["operation_id"]
        assert isinstance(identifier, str) and identifier.startswith("sig-")
        assert lit(env.ctl) == (True, [255, 0, 0, 0], SOLID)
        assert [f["field"] for f in started.data["owned"]] == ["on", "col0", "fx"]  # type: ignore[union-attr]
        assert env.ctl.state["bri"] == 47  # unowned: never written
        assert (await env.status(identifier))["status"] == "active"

        # Unowned fields changed by someone else during the wait are not a conflict.
        env.ctl.edit(bri=200, transition=3)
        env.ctl.edit_segment(0, sx=9, ix=8, pal=2, bri=100, n="renamed")

        await env.advance(9)
        assert (await env.status(identifier))["status"] == "active" and len(env.ctl.posts) == 1
        final = await env.advance_until_ended(1, identifier)
        assert final["status"] == "restored" and final["ended_by"] == "expired"
        assert final["restoration"]["application"] == "applied"
        assert final["started_at"] < final["expires_at"] <= final["ended_at"]

        assert len(env.ctl.posts) == 2  # apply and restore, nothing else
        assert set(env.ctl.posts[1]) <= {"on", "seg"}
        assert set(env.ctl.posts[1]["seg"][0]) == {"id", "col", "fx"}
        assert lit(env.ctl) == (False, BASE_COLOR, WIPE)
        # Everything the signal did not own survived, including the external edits.
        assert env.ctl.state["bri"] == 200 and env.ctl.state["transition"] == 3
        assert env.ctl.segment(0)["sx"] == 9 and env.ctl.segment(0)["pal"] == 2
        assert env.ctl.segment(0)["n"] == "renamed" and env.ctl.segment(0)["bri"] == 100
        assert before["seg"][0]["col"][1:] == env.ctl.segment(0)["col"][1:]
        assert env.signals.active_count() == 0 and env.timer.waiters == []


# ------------------------------------------------------------------------- T28-03 cancel


@pytest.mark.anyio
async def test_cancel_restores_at_once_is_idempotent_and_races_expiry_once(tmp_path):
    async with signal_env(tmp_path) as env:
        started = await env.start(duration_seconds=60)
        identifier = started.data["operation_id"]
        cancelled = await env.call("wled_cancel_signal", operation_id=identifier)
        assert cancelled.ok and cancelled.application == "applied"
        assert cancelled.data["signal"]["status"] == "restored"  # type: ignore[index]
        assert cancelled.data["signal"]["ended_by"] == "cancelled"  # type: ignore[index]
        assert lit(env.ctl) == (False, BASE_COLOR, WIPE) and len(env.ctl.posts) == 2

        again = await env.call("wled_cancel_signal", operation_id=identifier)
        assert again.ok and again.application == "not_attempted"
        assert "already ended" in again.warnings[0] and len(env.ctl.posts) == 2

        unknown = await env.call("wled_cancel_signal", operation_id="sig-0123456789abcdef")
        assert not unknown.ok and unknown.data["reason"] == "unknown_signal"
        assert unknown.error is not None and unknown.error.code == "VALIDATION_ERROR"

        # Cancel and expiry arriving together produce exactly one restore.
        raced = (await env.start(duration_seconds=5)).data["operation_id"]
        env.timer.advance(5)
        result = await env.call("wled_cancel_signal", operation_id=raced)
        assert result.ok and len(env.ctl.posts) == 4
        await env.advance(0)
        assert len(env.ctl.posts) == 4 and env.signals.active_count() == 0


# ------------------------------------------------------------- T28-04 overlap and limits


@pytest.mark.anyio
async def test_overlap_is_rejected_deterministically_and_limits_hold(tmp_path):
    ids = [f"d{i}" for i in range(9)]
    async with signal_env(tmp_path, device_ids=ids) as env:
        first = await env.start(device_id="d0", duration_seconds=60)
        active = first.data["operation_id"]
        posts = len(env.controller("d0").posts)
        again = await env.start(device_id="d0")
        assert not again.ok and again.application == "not_attempted"
        assert (
            again.data["reason"] == "signal_active" and again.data["active_operation_id"] == active
        )
        assert len(env.controller("d0").posts) == posts

        # Also while the first one is restoring (its restore waits for the device lock).
        async with anyio.create_task_group() as group:
            async with env.resources.locks["d0"]:
                group.start_soon(lambda: env.call("wled_cancel_signal", operation_id=active))
                await env.until(lambda: env.signals.get(active).status == "restoring")
                during = await env.start(device_id="d0")
                assert during.data["reason"] == "signal_active"
        assert env.signals.get(active).status == "restored"

        # Two concurrent starts on one device: exactly one wins.
        results: list[Any] = []

        async def racer() -> None:
            results.append(await env.start(device_id="d1", duration_seconds=60))

        async with anyio.create_task_group() as group:
            group.start_soon(racer)
            group.start_soon(racer)
        assert sorted(r.ok for r in results) == [False, True]
        assert {r.data.get("reason") for r in results if not r.ok} == {"signal_active"}

        # Different devices are independent; the ninth concurrent signal is refused.
        for identifier in ids[2:9]:
            assert (await env.start(device_id=identifier, duration_seconds=60)).ok
        assert env.signals.active_count() == 8
        refused = await env.start(device_id="d0")
        assert refused.data["reason"] == "signal_limit" and len(env.controller("d0").posts) == 2

        # A terminal result frees the slot, and so does a start that failed before dispatch.
        ended = (
            results[0].data["operation_id"] if results[0].ok else results[1].data["operation_id"]
        )
        await env.call("wled_cancel_signal", operation_id=ended)
        env.controller("d0").offline = True
        failed = await env.start(device_id="d0")
        assert failed.error is not None and failed.error.code == "UNREACHABLE"
        env.controller("d0").offline = False
        assert (await env.start(device_id="d0", duration_seconds=60)).ok


# ----------------------------------------------------------- T28-05 intervening external edit


def _other_segment(ctl: FakeController) -> None:
    ctl.state["seg"] = [ctl.segment(0) | {"id": 1}]


CONFLICTS: dict[str, tuple[Any, str]] = {
    "colour": (lambda c: c.edit_segment(0, col=[[1, 2, 3, 0]] * 3), "col0"),
    "effect": (lambda c: c.edit_segment(0, fx=1), "fx"),
    "master_off": (lambda c: c.edit(on=False), "on"),
    "segment_off": (lambda c: c.edit_segment(0, on=False), "on"),
    "resized": (lambda c: c.edit_segment(0, stop=20), "geometry_changed"),
    "removed": (_other_segment, "segment_missing"),
    "playlist": (lambda c: c.edit(pl=2), "playlist"),
    "nightlight": (lambda c: c.edit(nl={"on": True}), "nightlight"),
    "realtime": (lambda c: c.info.update(live=True), "realtime"),
}


@pytest.mark.anyio
@pytest.mark.parametrize("case", CONFLICTS)
async def test_an_intervening_edit_is_a_conflict_and_nothing_is_overwritten(tmp_path, case):
    edit, field = CONFLICTS[case]
    # The segment-power case needs a segment the signal switched on; the others use the default.
    controller = (
        FakeController(master_on=True, segments=[_off_segment()])
        if case == "segment_off"
        else FakeController()
    )
    async with signal_env(tmp_path, {host_of("desk"): controller}) as env:
        identifier = (await env.start(duration_seconds=10)).data["operation_id"]
        edit(controller)
        edited = controller.snapshot()
        final = await env.advance_until_ended(10, identifier)
        assert final["status"] == "skipped_conflict" and final["ended_by"] == "expired"
        restoration = final["restoration"]
        assert restoration["application"] == "not_attempted" and restoration["attempts"] == 1
        assert field in {d["field"] for d in restoration["differences"]}
        assert len(controller.posts) == 1 and controller.snapshot() == edited


@pytest.mark.anyio
async def test_cancel_after_an_external_edit_reports_the_conflict_as_success(tmp_path):
    async with signal_env(tmp_path) as env:
        identifier = (await env.start(duration_seconds=60)).data["operation_id"]
        env.ctl.edit_segment(0, col=[[9, 9, 9, 0]] * 3)
        result = await env.call("wled_cancel_signal", operation_id=identifier)
        assert result.ok and result.application == "not_attempted" and result.warnings
        restoration = result.data["signal"]["restoration"]  # type: ignore[index]
        assert restoration["result"] == "skipped_conflict"
        assert restoration["differences"] == [
            {
                "scope": "segment",
                "id": 0,
                "field": "col0",
                "expected": [255, 0, 0],
                "observed": [9, 9, 9, 0],
            }
        ]
        assert len(env.ctl.posts) == 1 and env.ctl.segment(0)["col"][0] == [9, 9, 9, 0]


def _off_segment() -> dict[str, Any]:
    from tests.state_catalog_support import make_segment

    return make_segment(0, 0, 30, on=False, fx=WIPE)


# ------------------------------------------------------------------ T28-06 offline at expiry


@pytest.mark.anyio
async def test_offline_at_expiry_retries_once_after_a_pause_and_never_replays(tmp_path):
    async with signal_env(tmp_path) as env:
        identifier = (await env.start(duration_seconds=10)).data["operation_id"]
        env.ctl.offline = True
        env.timer.advance(10)
        await paused(env, identifier)  # the 5 second pause, not a poll
        await env.advance(5)
        final = await env.advance_until_ended(0, identifier)
        restoration = final["restoration"]
        assert final["status"] == "uncertain" and restoration["error_code"] == "UNREACHABLE"
        assert restoration["write_attempted"] is False and restoration["attempts"] == 2
        assert env.ctl.post_attempts == 1  # the apply only; the restore never left

        # The device comes back later: still nothing is replayed.
        env.ctl.offline = False
        await env.advance(600)
        assert env.ctl.post_attempts == 1 and lit(env.ctl)[0] is True
        # The captured values stay available for an explicit restore.
        assert {f["field"]: f["captured"] for f in final["owned"]}["fx"] == WIPE


@pytest.mark.anyio
async def test_a_second_attempt_that_succeeds_is_reported_as_restored_with_a_warning(tmp_path):
    async with signal_env(tmp_path) as env:
        identifier = (await env.start(duration_seconds=10)).data["operation_id"]
        env.ctl.offline = True
        env.timer.advance(10)
        await paused(env, identifier)
        env.ctl.offline = False
        final = await env.advance_until_ended(5, identifier)
        assert final["status"] == "restored" and final["restoration"]["attempts"] == 2
        assert lit(env.ctl) == (False, BASE_COLOR, WIPE)
        outcome = await env.call("wled_get_signal_status", operation_id=identifier)
        assert any("second attempt" in warning for warning in outcome.warnings)


@pytest.mark.anyio
async def test_cancel_offline_makes_one_attempt_and_reports_uncertain(tmp_path):
    async with signal_env(tmp_path) as env:
        identifier = (await env.start(duration_seconds=60)).data["operation_id"]
        env.ctl.offline = True
        result = await env.call("wled_cancel_signal", operation_id=identifier)
        assert not result.ok and result.error is not None and result.error.code == "UNREACHABLE"
        assert result.application == "not_attempted" and env.timer.waiters == []
        assert result.data["signal"]["restoration"]["attempts"] == 1  # type: ignore[index]
        assert env.ctl.post_attempts == 1


# ------------------------------------------------- T28-07 indeterminate restore POST


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "code", "verification"),
    [
        ("apply_unreadable", "WRITE_OUTCOME_UNKNOWN", "unknown"),
        ("ack_only", "VERIFICATION_MISMATCH", "mismatch"),
    ],
)
async def test_an_unverified_restore_is_uncertain_and_never_retried(
    tmp_path, mode, code, verification
):
    async with signal_env(tmp_path) as env:
        identifier = (await env.start(duration_seconds=10)).data["operation_id"]
        env.ctl.next_posts(mode)
        final = await env.advance_until_ended(10, identifier)
        restoration = final["restoration"]
        assert final["status"] == "uncertain" and restoration["error_code"] == code
        assert restoration["application"] == "unknown"
        assert restoration["verification"] == verification
        assert restoration["write_attempted"] is True and restoration["attempts"] == 1
        await env.advance(600)
        assert len(env.ctl.posts) == 2 and env.timer.waiters == []  # no retry, no replay
        assert {f["field"] for f in final["owned"]} == {"on", "col0", "fx"}  # captured kept


# ------------------------------------------------------------ T28-08 failed or uncertain apply


@pytest.mark.anyio
async def test_a_failed_start_leaves_no_record_and_an_uncertain_one_is_never_restored(tmp_path):
    async with signal_env(tmp_path) as env:
        baseline = env.ctl.snapshot()
        env.ctl.offline = True
        offline = await env.start()
        assert offline.error is not None and offline.error.code == "UNREACHABLE"
        assert offline.application == "not_attempted" and "operation_id" not in offline.data
        env.ctl.offline = False
        env.ctl.edit(pl=3)
        refused = await env.start()
        assert refused.data["reason"] == "playlist_active" and not env.ctl.posts
        env.ctl.edit(pl=-1)
        assert env.signals.listing() == [] and env.signals.active_count() == 0

        modes = (
            ("apply_unreadable", "WRITE_OUTCOME_UNKNOWN"),
            ("ack_only", "VERIFICATION_MISMATCH"),
        )
        for mode, code in modes:
            env.ctl.unreadable_state = False
            env.ctl.state = copy.deepcopy(baseline)
            env.ctl.next_posts(mode)
            result = await env.start(duration_seconds=10)
            assert not result.ok and result.error is not None and result.error.code == code
            assert result.application == "unknown" and result.data["reason"] == "apply_unverified"
            assert result.data["no_replay"] is True and result.data["captured"]
            final = await env.status(result.data["operation_id"])  # type: ignore[arg-type]
            assert final["status"] == "uncertain" and final["expires_at"] is None
            assert final["restoration"]["result"] == "not_attempted"
            assert env.timer.waiters == [] and env.signals.active_count() == 0
            posts = len(env.ctl.posts)
            await env.advance(600)
            assert len(env.ctl.posts) == posts  # no automatic restore after an uncertain apply
        env.ctl.unreadable_state = False


# ----------------------------------------------------------- T28-09 cancelled caller


@pytest.mark.anyio
async def test_a_cancelled_start_request_still_registers_and_restores_at_expiry(tmp_path):
    async with signal_env(tmp_path) as env:
        async with anyio.create_task_group() as group:
            scope = anyio.CancelScope()

            async def caller() -> None:
                with scope:
                    await env.start(duration_seconds=10)

            group.start_soon(caller)
            await env.until(lambda: len(env.ctl.posts) == 1)  # the POST has left
            scope.cancel()  # the request is dropped, e.g. a lost connection
        await env.until(lambda: len(env.signals.listing()) == 1)
        record = env.signals.listing()[0]
        assert record.status == "active" and len(env.ctl.posts) == 1  # no write at the drop
        final = await env.advance_until_ended(10, record.operation_id)
        assert final["status"] == "restored" and len(env.ctl.posts) == 2
        assert lit(env.ctl) == (False, BASE_COLOR, WIPE)


# ------------------------------------------------------------------------- T28-10 shutdown


@pytest.mark.anyio
async def test_orderly_shutdown_restores_every_active_signal_once_with_the_control_class(tmp_path):
    ids = ["desk", "shelf", "lamp"]
    env = make_env(tmp_path, device_ids=ids)
    with anyio.fail_after(30):
        async with env.resources:
            plain = (await env.start(device_id="desk", duration_seconds=300)).data["operation_id"]
            edited = (await env.start(device_id="shelf", duration_seconds=300)).data["operation_id"]
            await env.start(device_id="lamp", duration_seconds=300)
            env.controller("lamp").offline = True
            env.controller("shelf").edit_segment(0, fx=1)  # an external edit before the stop
        # Leaving the context is the shutdown; nothing else wakes the signals.
        records = {r.device_id: r for r in env.signals.listing()}
        assert records["desk"].status == "restored" and records["desk"].ended_by == "shutdown"
        assert lit(env.controller("desk")) == (False, BASE_COLOR, WIPE)
        assert len(env.controller("desk").posts) == 2
        assert env.signals.get(plain).restoration["attempts"] == 1  # type: ignore[index]
        # A conflict at shutdown is skipped, an unreachable device is one attempt, no retry.
        assert env.signals.get(edited).status == "skipped_conflict"
        assert len(env.controller("shelf").posts) == 1
        assert (
            records["lamp"].status == "uncertain" and records["lamp"].restoration["attempts"] == 1
        )  # type: ignore[index]
        assert env.controller("lamp").post_attempts == 1 and env.timer.waiters == []
        # Delayed work ran as an explicit control operation, apply and restore alike.
        assert set(env.controller("desk").classes) == {ToolClass.CONTROL}
        assert env.signals.active_count() == 0


@pytest.mark.anyio
async def test_shutdown_refuses_new_signals_and_abandons_work_beyond_its_budget(tmp_path, caplog):
    env = make_env(tmp_path, device_ids=["desk", "shelf"])
    caplog.set_level(logging.INFO, logger="wled_mcp.signals")
    with anyio.fail_after(30):
        async with env.resources:
            env.signals.shutdown_budget_seconds = 0.2
            stuck = (await env.start(device_id="desk", duration_seconds=300)).data["operation_id"]
            await env.start(device_id="shelf", duration_seconds=300)
            env.ctl.hang = True  # the device stops answering
            started_at = anyio.current_time()
            await env.signals.shutdown()
            assert anyio.current_time() - started_at < 3  # bounded by the budget, not the device
            late = await env.start(device_id="shelf")
            assert late.data["reason"] == "shutting_down" and late.application == "not_attempted"
        record = env.signals.get(stuck)
        assert record.status == "uncertain" and record.restoration is not None
        assert record.restoration["reason"] == "shutdown_abandoned"
        assert "event=shutdown_incomplete abandoned=1" in caplog.text
        assert len(env.controller("shelf").posts) == 2  # the healthy device was still restored


# -------------------------------------------------------------- T28-11 restart and recovery


@pytest.mark.anyio
async def test_nothing_is_persisted_or_recovered_after_a_restart(tmp_path):
    first = make_env(tmp_path)
    before = tree(tmp_path)
    with anyio.fail_after(30):
        await first.resources.__aenter__()
        identifier = (await first.start(duration_seconds=300)).data["operation_id"]
        applied = first.ctl.snapshot()
        # A crash: the process dies without the orderly shutdown, so nothing is restored.
        await first.signals.close()
        assert first.ctl.snapshot() == applied and len(first.ctl.posts) == 1

        second = make_env(tmp_path, first.fleet.controllers)
        async with second.resources:
            listing = await second.call("wled_get_signal_status")
            assert listing.data["signals"] == [] and listing.data["active_count"] == 0
            unknown = await second.call("wled_get_signal_status", operation_id=identifier)
            assert unknown.data["reason"] == "unknown_signal"
            cancelled = await second.call("wled_cancel_signal", operation_id=identifier)
            assert cancelled.data["reason"] == "unknown_signal"
            await second.advance(1000)
            assert len(first.ctl.posts) == 1  # nothing replayed, nothing written at startup
        assert first.ctl.snapshot() == applied  # the device stays as the signal left it
    # No metadata, journal or snapshot file came into existence.
    assert tree(tmp_path) == before
    await first.resources.client.aclose()


# --------------------------------------------------------------------- T28-12 access contexts


@pytest.mark.anyio
async def test_delayed_restores_run_as_control_under_a_restricted_deployment(tmp_path):
    env = make_env(tmp_path, profile="control", caps={"desk": "control"})
    with anyio.fail_after(30):
        async with env.resources:
            # (a) timer, cancel and shutdown wakeups all restore under the restriction.
            first = (await env.start(duration_seconds=10)).data["operation_id"]
            assert (await env.advance_until_ended(10, first))["status"] == "restored"
            second = (await env.start(duration_seconds=60)).data["operation_id"]
            assert (await env.call("wled_cancel_signal", operation_id=second)).ok
            third = (await env.start(duration_seconds=60)).data["operation_id"]
            assert lit(env.ctl)[0] is True
        assert env.signals.get(third).status == "restored"
        assert lit(env.ctl) == (False, BASE_COLOR, WIPE) and len(env.ctl.posts) == 6
        assert set(env.ctl.classes) == {ToolClass.CONTROL}

        # (b) fail-closed contrast: the same policy refuses a write that has no class.
        (tmp_path / "again").mkdir()
        env = make_env(tmp_path / "again", profile="control", caps={"desk": "control"})
        async with env.resources:
            before = len(env.ctl.posts)
            bare = await env.resources.write_verified(
                "desk", "bare", _unused_prepare, lambda s: True
            )
            assert bare.error is not None and bare.error.code == "ACCESS_DENIED"
            assert len(env.ctl.posts) == before
            # The signal task does not inherit the caller's class: even a caller whose ambient
            # class is "read" or unknown gets a working apply and restore.
            from wled_mcp.signals import SignalSpec

            token = CURRENT_TOOL_CLASS.set(ToolClass.READ)
            try:
                started = await env.signals.start(SignalSpec("desk", (0,), (0, 0, 255), 5))
            finally:
                CURRENT_TOOL_CLASS.reset(token)
            assert started.kind == "started" and started.record is not None, started.outcome
            await env.advance_until_ended(5, started.record.operation_id)
            assert lit(env.ctl) == (False, BASE_COLOR, WIPE)


async def _unused_prepare(context: Any) -> dict[str, Any]:
    raise AssertionError("a refused write never prepares")


# ------------------------------------------------------------ T28-13 bounded cleanup, T28-17


@pytest.mark.anyio
async def test_ended_records_are_bounded_and_no_task_or_waiter_is_left(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="wled_mcp.signals")
    async with signal_env(tmp_path) as env:
        for _ in range(40):
            started = await env.start(duration_seconds=60)
            await env.call("wled_cancel_signal", operation_id=started.data["operation_id"])
        listing = await env.call("wled_get_signal_status")
        assert listing.data["count"] == 32 and listing.data["active_count"] == 0
        assert env.signals._running == {} and env.signals._reserved == {}
        assert env.timer.waiters == [] and len(env.ctl.posts) == 80

        # The delayed restore is attributable to this server (evidence for wled_explain_lighting).
        last = env.resources.monitor.last_control.latest("desk")
        assert last is not None and last.operation == "wled_signal_restore"
        assert (last.application, last.verification) == ("applied", "verified")

    # T28-16: one bounded line per event; no address, colour or body, the configured ID only.
    lines = [r.getMessage() for r in caplog.records if r.name == "wled_mcp.signals"]
    assert len(lines) == 80 and all("sig-" in line and "device_id=desk" in line for line in lines)
    # The random operation IDs are hex and may contain "255" by chance: look at the rest only.
    rest = [re.sub(r"sig-[0-9a-f]{16}", "sig-", line) for line in lines]
    assert not any("invalid" in line or "255" in line or "col" in line for line in rest)
