# Issue #200 validation: `wled_discover_devices`

Requirements: DISC-01, DISC-03, DISC-04, DISC-05 (re-check at probe time is in the engine),
DISC-06, DISC-11 to DISC-13; scenarios DISC-T02 and DISC-T04 through the tool, DISC-T05,
DISC-T07, DISC-T08 (live part, first half: partial, see the live run). Contract:
[contract/discovery.md](../contract/discovery.md). Decisions:
[ISSUE-200-DEC-001 and ISSUE-200-DEC-002](../decisions/issue-200.md).

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

## Live run: executed 2026-11-19 (partial evidence)

One owner-authorized, read-only run against the selected test controller of the local-only
inventory, over stdio, from the merged tool (#200 and #202 on `main`). Authorization and scope:
[ISSUE-200-DEC-002](../decisions/issue-200.md) (one run, one controller, read-only, used and
expired). The raw output stays local and untracked; this section holds counts and statuses only
(DEC-005).

Setup: one server over stdio with a temporary inventory outside the repository, one device, no
`[discovery]` table. Only `tools/list` (39 tools) and `wled_discover_devices` were called. All
requests the run caused were GET; nothing was written to any device.

| Check | Expected | Result |
| --- | --- | --- |
| `tools/list` | tool present, 39 tools | pass |
| Call 1 `{}` (8.2 s) | `ok` true | pass |
| Call 1 mDNS | `completed`, `no_answers` or `multicast_unavailable`, stated honestly | pass: `completed` (23 responders, 2 verified, 19 rejected) |
| Call 1 unicast | `skipped`, `no_ranges_configured` | pass |
| Call 1 `complete` and conclusion | `complete` false; `candidates_found` or `none_found_incomplete`, never `none_found_complete` | pass: false, `candidates_found` |
| Selected controller listed as `known` | `known` when it answers | fail (expectation did not hold): `address_changed`, matched by MAC, see deviation 2 |
| `proposed_ranges` holds the /24 of its address | one /24 | fail (expectation did not hold): empty, reason `host_not_ipv4_literal`, see deviation 2 |
| Call 2 `{"methods":["mdns"]}` right after | allowed, no `DISCOVERY_BUSY` | pass: `ok` true, same coverage, unicast `skipped` with `not_requested` |
| Inventory hash unchanged, no backup or lock file, empty data directory | unchanged, none | pass |
| stderr free of address, MAC and range | empty | pass (0 bytes) |

Deviations and limits, stated plainly:

1. mDNS verifies every announced private address with a read-only `GET /json/info`
   ([DISC-02](../contract/discovery.md); every announced RFC 1918 address on port 80). Call 1
   saw 23 responders, 2 verified and 19 rejected, so many LAN hosts received one read-only
   request, among them a second WLED controller outside the authorization, which was returned
   as a `new` candidate. The authorization text and the earlier procedure wording ("at most the
   bounded `GET` of the configured known devices") under-described this; the procedure below is
   corrected. No address, MAC or firmware detail of any controller is recorded here.
2. The selected controller's configured `base_url` is a host name, not an IPv4 literal. It was
   therefore reported `address_changed` (MAC match) instead of `known`, and `proposed_ranges`
   was empty (`host_not_ipv4_literal`). The expectations above assumed an IPv4-literal
   inventory. This is a limit of the evidence, not a fix; a follow-up candidate is to compare a
   resolved host name before reporting `address_changed`.
3. A run limited to one device is not achievable with the current tool (mDNS reaches the whole
   announcing LAN). The unicast path and the container deployment remain unproved live (#204).

Result for DISC-T08: the first half (read-only discovery over stdio, inventory unchanged) is
partially met. Unicast, container mode and the single enrollment (#203, #204) are not covered.
This run does not satisfy a hardware acceptance criterion by itself.

Procedure for a later run (needs its own authorization):

1. Preconditions: the authorization is recorded and names the LAN-wide mDNS verification
   (deviation 1); build from the merged head; a local-only inventory file outside the
   repository with the selected device and no `[discovery]` table, preferably with an
   IPv4-literal `base_url`; output only under an ignored directory.
2. Offline checks first: `uv run pytest tests/test_discovery_tools.py tests/test_tool_contract.py
   tests/test_access_profiles.py tests/test_tool_budget.py`, `ruff`, `mypy`.
3. Start the server over stdio with the local configuration (as `scripts/hw_read_only_probe.py`
   does) and call only `tools/list` and `wled_discover_devices`; assert that no tool of another
   class is called.
4. Call 1 with `{}`. Expected: `ok` true; mDNS `completed`, `no_answers` or
   `multicast_unavailable`, stated honestly; every announced private address gets one
   read-only `GET /json/info` and other WLED controllers on the LAN may be returned as `new`;
   unicast `skipped` with `no_ranges_configured`; the selected controller is `known` (IPv4
   literal) or `address_changed` (host name, MAC match); `proposed_ranges` holds the /24 of an
   IPv4-literal address; `complete` false; conclusion `candidates_found` or
   `none_found_incomplete`, never `none_found_complete`.
5. Call 2 within 5 s with `{"methods":["mdns"]}`: allowed (no probe gap for mDNS only).
6. Afterwards verify the inventory file hash is unchanged, no backup or lock file appeared and
   stderr holds no address, MAC or range.
7. Replace addresses and MACs with placeholders before any output enters `docs/validation/`
   (DEC-005, `scripts/check_private_identifiers.py`). Stop. Unicast and container runs are #204.
