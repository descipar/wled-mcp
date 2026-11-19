# Issue #200 validation: `wled_discover_devices`

Requirements: DISC-01, DISC-03, DISC-04, DISC-05 (re-check at probe time is in the engine),
DISC-06, DISC-11 to DISC-13; scenarios DISC-T02 and DISC-T04 through the tool, DISC-T05,
DISC-T07, DISC-T08 (live part, first half). Contract:
[contract/discovery.md](../contract/discovery.md). Decisions:
[ISSUE-200-DEC-001](../decisions/issue-200.md).

## Mocked evidence

`tests/test_discovery_tools.py` runs the tool in process (stdio-style client and the loopback
Streamable HTTP harness) on the real engine with the simulated multicast network and a scripted
`GET /json/info`. `tests/conftest.py` makes the real engine refuse in every other test, so no
test opens a multicast socket. Evidence per behavior:

| Behavior | Test |
| --- | --- |
| Class `read`, annotations true/false/true/true, in `read-only`, `control` and `full`; identical descriptor over HTTP | `test_the_tool_is_served_in_every_profile_as_a_read_tool`, `test_the_served_descriptor_is_identical_over_streamable_http`, `tests/test_tool_contract.py` |
| Bad parameters and range/host fields are `VALIDATION_ERROR`, nothing probed | `test_a_bad_request_is_rejected_before_anything_is_probed` |
| Candidates `known` / `address_changed`, coverage and envelope fields, nothing written | `test_candidates_coverage_and_envelope_are_mapped_and_nothing_is_written` |
| Suggested id unique against the inventory | `test_a_suggested_id_never_repeats_an_inventory_id` |
| No ranges: mDNS only, `none_found_incomplete`, proposals derived and never probed | `test_without_ranges_only_mdns_runs_and_proposals_are_never_probed`, `test_unicast_only_without_ranges_is_not_looked_and_still_ok` |
| Ranges come from the seam per call; proposals exclude configured ranges | `test_configured_ranges_reach_the_engine_per_call_and_exclude_proposals` |
| `propose_ranges` (merge, sort, exclude, truncate, DNS and non-private counts) | `test_proposals_*`, `test_more_than_four_proposals_*`, `test_the_wrapper_reports_omitted_and_unproposed_in_the_coverage` |
| Single flight, probe gap (not for mDNS only), release after failure and cancellation | the four `DISCOVERY_BUSY` tests and `test_a_run_without_ranges_is_not_a_probe_phase` |
| `DiscoveryRangeError` is `CONFIG_ERROR` without a value; bounds pass through; mDNS failure is coverage, not an error | `test_invalid_stored_ranges_*`, `test_bounds_are_passed_through_*`, `test_mdns_failure_is_reported_*` |
| Same envelope over both transports; the call log names no address, MAC or range | `test_stdio_style_and_streamable_http_return_the_same_envelope`, `test_the_call_log_names_no_address_mac_or_range` |

The tool-count budget measurement is in [issue-235.md](issue-235.md#discovery-tool-200).

## Live run: pending owner authorization

Not run. It needs a separate owner authorization for one explicitly selected controller of
the local-only test inventory (ISSUE-200-DEC-002 once given): read-only, mDNS plus at most the
bounded `GET /json/info` of the configured known devices (up to 16), no ranges stored, no
unicast sweep, no write, no other target. The unicast path of the tool is mock-tested only
until #202 (ranges key) and #204 (live proof).

Procedure (do not execute without that authorization):

1. Preconditions: the authorization is recorded; build from the PR head; a local-only inventory
   file outside git with exactly the selected device and no `[discovery]` table; output only
   under an ignored directory.
2. Offline checks first: `uv run pytest tests/test_discovery_tools.py tests/test_tool_contract.py
   tests/test_access_profiles.py tests/test_tool_budget.py`, `ruff`, `mypy`.
3. Start the server over stdio with the local configuration (as `scripts/hw_read_only_probe.py`
   does) and call only `tools/list` and `wled_discover_devices`; assert that no tool of another
   class is called.
4. Call 1 with `{}`. Expected: `ok` true; mDNS `completed`, `no_answers` or
   `multicast_unavailable`, stated honestly; unicast `skipped` with `no_ranges_configured`;
   the selected controller listed as `known` when it answers (`address_changed` is never claimed
   without a MAC match); `proposed_ranges` holds the /24 of its address; `complete` false;
   conclusion `candidates_found` or `none_found_incomplete`, never `none_found_complete`.
5. Call 2 within 5 s with `{"methods":["mdns"]}`: allowed (no probe gap for mDNS only).
6. Afterwards verify the inventory file hash is unchanged, no backup or lock file appeared and
   stderr holds no address, MAC or range.
7. Replace addresses and MACs with placeholders before any output enters `docs/validation/`
   (DEC-005, `scripts/check_private_identifiers.py`). Stop. Unicast and container runs are #204.
