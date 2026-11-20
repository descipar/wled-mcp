# Issue #200 validation: `wled_discover_devices`

Requirements: DISC-01, DISC-03, DISC-04, DISC-05 (re-check at probe time is in the engine), DISC-06,
DISC-11 to DISC-13; scenarios DISC-T02 and DISC-T04 through the tool, DISC-T05, DISC-T07, DISC-T08
(live part, first half: partial, see the live run). Contract:
[contract/discovery.md](../contract/discovery.md). Decisions:
[ISSUE-200-DEC-001 and ISSUE-200-DEC-002](../decisions/issue-200.md).

## Mocked evidence

`tests/test_discovery_tools.py` runs the tool in process (stdio-style client and loopback Streamable
HTTP) on the real engine with a simulated multicast network and a scripted `GET /json/info`;
`tests/conftest.py` makes the real engine refuse in every other test.

| Behavior | Test (in `tests/test_discovery_tools.py` unless noted) |
| --- | --- |
| Class `read`, annotations true/false/true/true, in `read-only`, `control` and `full`; identical descriptor over HTTP | served-in-every-profile and identical-descriptor tests; `tests/test_tool_contract.py` |
| Bad parameters and range/host fields are `VALIDATION_ERROR`, nothing probed | bad-request test |
| Candidates `known` / `address_changed`, coverage and envelope fields, nothing written; suggested id unique | mapping and suggested-id tests |
| No ranges: mDNS only, `none_found_incomplete`, proposals derived and never probed | without-ranges tests |
| Ranges come from the seam per call; proposals exclude configured ranges; `propose_ranges` (merge, sort, exclude, truncate, DNS and non-private counts) | configured-ranges and `test_proposals_*` tests |
| Single flight, probe gap (not for mDNS only), release after failure and cancellation | the four `DISCOVERY_BUSY` tests |
| `DiscoveryRangeError` is `CONFIG_ERROR` without a value; bounds pass through; mDNS failure is coverage, not an error | invalid-ranges, bounds, mDNS-failure tests |
| Same envelope over both transports; call log names no address, MAC or range | parity and call-log tests |

The tool-count budget measurement is in [issue-235.md](issue-235.md#discovery-tool-200).

## Live run: executed 2026-11-19 (partial evidence)

One owner-authorized, read-only run against the selected test controller of the local-only
inventory, over stdio, from the merged tool (#200 and #202 on `main`); authorization and scope in
[ISSUE-200-DEC-002](../decisions/issue-200.md) (one run, one controller, used and expired). Raw
output stayed local and untracked (DEC-005). Setup: a temporary inventory outside the repository,
one device, no `[discovery]` table; only `tools/list` (39 tools) and `wled_discover_devices` were
called; every request was a GET and nothing was written to any device.

| Check | Expected | Result |
| --- | --- | --- |
| `tools/list` | tool present, 39 tools | pass |
| Call 1 `{}` (8.2 s) | `ok` true; mDNS stated honestly; unicast `skipped` `no_ranges_configured`; `complete` false, never `none_found_complete` | pass: mDNS `completed` (23 responders, 2 verified, 19 rejected), conclusion `candidates_found` |
| Selected controller listed as `known` | `known` | fail (expectation did not hold): `address_changed`, matched by MAC (deviation 2) |
| `proposed_ranges` holds the /24 of its address | one /24 | fail (expectation did not hold): empty, `host_not_ipv4_literal` (deviation 2) |
| Call 2 `{"methods":["mdns"]}` right after | allowed, no `DISCOVERY_BUSY` | pass: unicast `skipped` `not_requested` |
| Inventory hash unchanged, no backup or lock file, empty data directory | unchanged, none | pass |
| stderr free of address, MAC and range | empty | pass (0 bytes) |

Deviations and limits:

1. mDNS verifies every announced RFC 1918 address with a read-only `GET /json/info`
   ([DISC-02](../contract/discovery.md)). Call 1 saw 23 responders (2 verified, 19 rejected), so many
   LAN hosts received one read-only request, among them a second WLED controller outside the
   authorization, returned as a `new` candidate. The authorization text and procedure wording
   under-described this; the procedure is corrected below. No address, MAC or firmware detail is
   recorded.
2. The selected controller's `base_url` is a host name, not an IPv4 literal, so it was reported
   `address_changed` (MAC match) and `proposed_ranges` was empty. A limit of the evidence, not a fix;
   a follow-up candidate is to compare a resolved host name before reporting `address_changed`.
3. A run limited to one device is not achievable (mDNS reaches the whole announcing LAN). The unicast
   path and the container deployment remain unproved live (#204).

Result for DISC-T08: the first half (read-only discovery over stdio, inventory unchanged) is
partially met; unicast, container mode and the single enrollment (#203, #204) are not covered. This
run does not satisfy a hardware acceptance criterion by itself.

Procedure for a later run (needs its own authorization): record an authorization that names the
LAN-wide mDNS verification; build from the merged head; use a local-only inventory outside the
repository with the selected device (preferably an IPv4-literal `base_url`) and no `[discovery]`
table; run the offline discovery/contract/profile/budget tests, `ruff` and `mypy` first; start over
stdio and call only `tools/list` and `wled_discover_devices`; call 1 `{}` (every announced private
address gets one read-only `GET /json/info`, other WLED controllers may appear as `new`; the
selected controller is `known` or `address_changed`; `complete` false), call 2 within 5 s with
`{"methods":["mdns"]}` allowed; afterwards verify the inventory hash, no backup or lock file and
clean stderr; replace addresses and MACs with placeholders before anything enters `docs/validation/`
(DEC-005, `scripts/check_private_identifiers.py`). Unicast and container runs are #204.
