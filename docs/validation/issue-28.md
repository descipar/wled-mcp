# Issue #28 validation: temporary signals with conflict-aware restoration

Evidence for [#28](https://github.com/descipar/wled-mcp/issues/28) (acceptance scenario S3-T02,
requirements S3-SIGNAL-01 and S3-SIGNAL-02); contract in [contract/signals.md](../contract/signals.md),
decisions in [ISSUE-28-DEC-001 and -002](../decisions/issue-28.md).

**Status: software evidence complete; live evidence recorded below** (two runs on the one selected
test controller under ISSUE-28-DEC-001, on candidate `0b3e6c688abda967b64212a6449097cd157ef258`;
later commits of the pull request change documentation only).

## Software evidence (mock, fixture and loopback only)

Timing is driven by a controlled clock (`FakeClock`, `tests/signal_support.py`); no test waits in
real time. The device is a stateful mock controller behind `httpx.MockTransport` that applies POST
bodies and can be edited externally, taken offline or made to drop, ignore or not answer a write.
The console test uses the loopback fake of `tests/acceptance_support.py` on `127.0.0.1`. No LAN
device and no real data directory was used.

### Scenario to test map

| Scenario | Evidence |
| --- | --- |
| T28-01 Plan, owned fields, rejections, dry run | `tests/test_signals.py`: `test_the_owned_fields_are_exactly_the_written_ones`, `test_unsupported_states_are_refused_before_any_write_with_a_stable_reason`; `tests/test_signal_tools.py` `test_dry_run_returns_the_real_plan_and_reserves_nothing`, `test_profiles_and_ceilings_gate_start_and_cancel_but_not_the_status` |
| T28-02 Expiry with unchanged state | `tests/test_signal_manager.py` `test_expiry_restores_only_the_owned_fields` |
| T28-03 Cancel, idempotence, race with expiry | `test_cancel_restores_at_once_is_idempotent_and_races_expiry_once` |
| T28-04 Overlap and limits | `test_overlap_is_rejected_deterministically_and_limits_hold` |
| T28-05 Intervening external edit | `test_an_intervening_edit_is_a_conflict_and_nothing_is_overwritten` (nine cases), `test_cancel_after_an_external_edit_reports_the_conflict_as_success`; `tests/test_signals.py` compare tests |
| T28-06 Offline at expiry | `test_offline_at_expiry_retries_once_after_a_pause_and_never_replays`, `test_cancel_offline_makes_one_attempt_and_reports_uncertain` |
| T28-07 Indeterminate restore POST | `test_an_unverified_restore_is_uncertain_and_never_retried` |
| T28-08 Failed or uncertain apply | `test_a_failed_start_leaves_no_record_and_an_uncertain_one_is_never_restored` |
| T28-09 Lost connection / cancelled caller | `test_a_cancelled_start_request_still_registers_and_restores_at_expiry`; HTTP leg in `tests/test_signal_tools.py` |
| T28-10 Shutdown | `test_orderly_shutdown_restores_every_active_signal_once_with_the_control_class`, `test_shutdown_refuses_new_signals_and_abandons_work_beyond_its_budget` |
| T28-11 Restart, no persistence | `test_nothing_is_persisted_or_recovered_after_a_restart` |
| T28-12 Access contexts, both cases | `test_delayed_restores_run_as_control_under_a_restricted_deployment`; `tests/test_signal_tools.py` ceiling test |
| T28-13 Bounded cleanup | `test_ended_records_are_bounded_and_no_task_or_waiter_is_left`, `test_the_start_schema_enforces_every_bound` |
| T28-14 Registry and contract | `tests/tool_contract.py`, `tests/test_tool_contract.py`, `tests/test_access_profiles.py`, `test_descriptions_state_the_limits_and_every_property_is_described` |
| T28-15 Both transports share the manager | `test_in_process_and_loopback_http_share_the_manager_and_survive_a_dropped_client`; `tests/test_acceptance_parity.py::test_a_signal_start_status_cancel_gives_identical_results_over_stdio_and_http` (exactly two POSTs) |
| T28-16 Privacy and logs (Should) | `test_ended_records_are_bounded_and_no_task_or_waiter_is_left` (log lines carry no address or colour) |
| T28-17 Feeds the explanation evidence (Should) | same test: after a restore `last_control` shows `wled_signal_restore` applied and verified |

## Live evidence (ISSUE-28-DEC-001)

One owner-authorized session on 2026-11-12, through an actual MCP stdio client against a local build
of the candidate (profile `full`, throw-away data directory removed afterwards; hub not touched).
Scope and limits: [ISSUE-28-DEC-001](../decisions/issue-28.md). Controller: the test controller of the
earlier runs, WLED 16.0.1, ESP32-C3, 133 LEDs, one RGB segment, 37 tools served.

Baseline (read-only, saved before the first write): master off, brightness 47, transition 7, no
playlist, preset or nightlight, segment 0 on, colour slot 0 `[138,189,255]`, effect Solid, speed 128,
intensity 128, palette 11; preset list held exactly slot 1. The read-only dry run returned `ok`
without a write.

| Step | Result |
| --- | --- |
| Run A: start, segment 0, green, 10 s | `applied`/`verified`; readback showed master on, brightness 47, slot 0 green, other fields unchanged; status `active`. |
| Run A: expiry | `restoring` then `restored`, `ended_by` `expired`, verified 10.36 s after start. Readback and preset list equalled the baseline. |
| Run B: start, 60 s; external `wled_patch_segments` (slot 0 to blue) 3 s later | Both `applied`/`verified`. |
| Run B: `wled_cancel_signal` | `ok`, `skipped_conflict`, `ended_by` `cancelled`; no restore write, the external blue colour stayed. |
| Run B: baseline restoration by the coordinator | Explicit `wled_patch_segments` and `wled_set_state` (`on` false), both `applied`/`verified`; readback equalled the baseline. |

No write failed or was retried; no reboot, firmware, settings or preset change. Final state equals
the baseline. No difference from the mock assumptions was observed. The baseline effect was already
Solid and had no running preset marker, so an effect change and the clearing of that marker were not
exercised.

## Limits

- Mock evidence only: offline or timing-out controller during restore, shutdown restore, restart and
  crash behavior, a non-Solid prior effect, RGBW and multi-segment devices, the HTTP transport (the
  live run used stdio) and any other controller.
- Not confirmed on a controller: that speed, intensity and palette survive a real effect change, and
  that a state write clears the running preset marker.
- Nothing is persisted: a crash, kill or power loss leaves an active signal applied and its ID unknown
  ([contract](../contract/signals.md#shutdown-and-restart)).
- Timing is best effort; no exact duration is claimed, in particular not across an outage.
- A write by another client between the comparison read and the restore POST is not detected.
- The console parity test runs one scenario; timer-driven, failure and shutdown paths are tested in
  process with the controlled clock.
