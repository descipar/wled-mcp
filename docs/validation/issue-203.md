# Issue #203 validation: `wled_add_device`

Requirements: DISC-08; DISC-05 (hard caps apply to the verification read), DISC-10 (reload),
DISC-T06 (writer path), DISC-T07 (gating), DISC-T08 (second half, the single enrollment: live run
below). Contract: [contract/discovery.md](../contract/discovery.md). Decisions:
[ISSUE-203-DEC-001](../decisions/issue-203.md) (technical defaults),
[ISSUE-203-DEC-002](../decisions/issue-203.md) (live-run authorization),
[DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment).

## Mocked evidence

`tests/test_add_device.py` runs the tool in process on a temporary inventory with synthetic RFC 1918
literals and a scripted `enroll_tools.fetch_info` (`tests/enroll_support.py`); `tests/conftest.py`
makes `fetch_info` refuse in every other test, so no test opens a socket.

| Behavior | Evidence in `tests/test_add_device.py` |
| --- | --- |
| Bad address, scheme, port, name, ID, MAC and unknown fields refused; nothing read or written; value never echoed | bad-address, invalid-fields and request-schema tests |
| Canonical stored address; success returns exactly the written table; prior bytes and `.bak` kept; no `max_class`; one read | canonical-form, append-one-entry, explicit-port tests |
| In-process reload; old snapshot unchanged; new ID usable | in-effect-without-restart and served-call tests |
| Default ID and name; uniqueness; explicit values verbatim | default, unique-ID, explicit-values tests |
| Duplicate ID, address, MAC (pre-read, no request); no MAC conflict without a stored MAC; `expected_mac` | duplicate and `expected_mac` tests |
| Read failures map to `UNREACHABLE`, `TIMEOUT`, `NOT_WLED`, `INVALID_RESPONSE`; one `GET /json/info` with the hard-cap timeout | failed-read and verification-read tests |
| `dry_run` reads once, checks conflicts, touches no file | dry-run tests |
| Writer failures (hand edit, storage, lock, inline array, access change, failed reload and restore) leave no partial entry | writer failure tests |
| Concurrent calls create one entry; sequential calls do not trip the baseline | concurrency tests |
| `devices[].mac` normalization, round trip; stored MAC used by discovery (tool and CLI) | config model and discovery consumer tests |
| Class `manage`, full profile only, annotations false/false/false/true, identical descriptor over HTTP | gating tests; `tests/test_tool_contract.py`, `tests/test_access_profiles.py` |
| Call log and error data free of address, MAC and name | log and error-data tests |

The tool-count budget measurement is in [issue-235.md](issue-235.md#enrollment-tool-203).

## Live enrollment (2026-11-19, two attempts)

Authority: [ISSUE-203-DEC-002](../decisions/issue-203.md), one authorization per attempt, both used
and expired. "The selected test controller"; no address, MAC, host name or firmware detail recorded
(DEC-005); raw output was kept outside the repository and deleted. Procedure as the #200 run: stdio
only, a temporary inventory outside git, the real local-only inventory never passed to the server,
no mDNS, no scan, no device write.

Attempt 1 failed on a stale address: the address came from a remembered note and the host name
resolved elsewhere, so the probe reached a non-WLED host. 41 tools listed; `wled_add_device`
annotations false/false/false/true. Call 1: `ok` false, `NOT_WLED`, `not_applied`. A second call
with the same arguments was sent after the failure and made a second `GET /json/info` to the same
wrong host: one request beyond the authorized one (read-only, no state changed, no controller
reached). Temporary and real inventory hashes unchanged, no `.bak`, no lock file, stderr clean. The
tool behaved as specified; the attempt proves no acceptance criterion and was not repeated blindly.

Attempt 2 succeeded: the address was resolved at run time from the host name in the local-only
inventory (one RFC 1918 IPv4 result) and passed to one call; only `tools/list` and
`wled_add_device` were used.

| Check | Result |
| --- | --- |
| 1 `tools/list` shows `wled_add_device`, class `manage`, full profile | pass (annotations as expected; the class is not in the descriptor and was read from the call log, `class=manage`) |
| 2 `dry_run` call | not run, by authorization (extra request); mock-covered only |
| 3 real call `ok` true, `application` `not_attempted`, `verification` `not_requested`; returned entry (`id`, `name`, `base_url`, `mac`) equals the one new file table; `mac` stored; temporary file hash changed; `.bak` equals the previous bytes; `data` `written`, `reloaded` true, `inventory_size` 1 | pass. The previous bytes were the initial two-line file, so the backup is shown for that content only, not for a populated inventory |
| 3 new ID usable by a read-only tool in the same process | not run, by authorization; mock-covered only |
| 4 repeat after success: `INVENTORY_CONFLICT`, nothing changed, no request | pass: conflict kind `base_url` with the known device ID, `not_attempted`, file unchanged; no second request reached the controller (inferred from the pre-read rule and the mock test, no network trace) |
| 5 stderr free of address, MAC and name | pass (one WARNING line, the call log of the repeat) |
| 6 real inventory unchanged; temporary inventory deleted | pass |
| Requests to the selected controller | one `GET /json/info` by design; not independently counted (no packet capture) |

DISC-T08, second half (single enrollment, live): **met** for the writer and verification path over
stdio: one verified read, one inventory write with the exact entry returned, MAC stored, backup
kept, duplicate refused. Not shown live (mock-covered): `dry_run`, use of the new ID by a read-only
tool, the MAC-conflict rule, and restore from `.bak` of a populated inventory. #204 keeps unicast
discovery, container deployment, migration notes and further live evidence.

Procedure hints for a later run: start from a minimal inventory (`schema_version = 1`,
`devices = []`; a literally empty file is refused at startup); resolve the live address at run time
instead of reusing a remembered one; record a failed call and do not repeat it; and state in the
authorization how many calls and requests are allowed, including the repeat.
