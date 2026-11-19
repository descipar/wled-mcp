# Issue #203 validation: `wled_add_device`

Requirements: DISC-08; DISC-05 (the hard caps apply to the verification read), DISC-10 (reload),
DISC-T06 (writer path), DISC-T07 (gating), DISC-T08 (second half, the single enrollment: live
run recorded below). Contract: [contract/discovery.md](../contract/discovery.md). Decisions:
[ISSUE-203-DEC-001](../decisions/issue-203.md) (proposed technical defaults),
[ISSUE-203-DEC-002](../decisions/issue-203.md) (the live-run authorization),
[DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment).

## Mocked evidence

`tests/test_add_device.py` runs the tool in process on a temporary inventory with synthetic
RFC 1918 literals and a scripted `enroll_tools.fetch_info` (`tests/enroll_support.py`).
`tests/conftest.py` makes `fetch_info` refuse in every other test, so no test opens a socket.

| Behavior | Test |
| --- | --- |
| Bad address, scheme, port, name, ID, MAC and unknown fields refused; nothing read or written; value never echoed | `test_a_bad_address_is_refused_before_any_read`, `test_invalid_fields_and_unknown_arguments_are_refused`, `test_the_request_schema_names_no_range_host_or_candidate_field` |
| Canonical stored address; success returns exactly the written table; prior bytes and `.bak` kept; no `max_class`; one read | `test_the_canonical_stored_form`, `test_success_appends_one_entry_and_returns_exactly_it`, `test_an_explicit_port_is_kept_and_probed` |
| In-process reload; old snapshot unchanged; new ID usable; file loads | `test_the_new_entry_is_in_effect_without_a_restart`, `test_a_served_call_returns_the_envelope_and_the_new_id_is_usable` |
| Default ID and name; uniqueness; explicit values verbatim | `test_defaults_come_from_the_reported_name_else_the_mac`, `test_a_default_id_is_unique_against_the_existing_ids`, `test_explicit_id_and_name_are_used_verbatim` |
| Duplicate ID, address, MAC; pre-read checks make no request; no MAC conflict without a stored MAC; `expected_mac` | `test_a_duplicate_id_is_refused_before_any_read`, `test_an_equal_address_is_refused_before_any_read`, `test_an_equal_mac_at_another_address_is_refused_and_never_rewritten`, `test_an_entry_without_a_stored_mac_gives_no_mac_conflict`, `test_expected_mac_mismatch_and_match` |
| Read failures map to `UNREACHABLE`, `TIMEOUT`, `NOT_WLED`, `INVALID_RESPONSE`; the real transport issues one `GET /json/info` with the hard-cap timeout | `test_a_failed_read_writes_nothing`, `test_the_verification_read_is_one_get_of_json_info_with_the_hard_caps` |
| `dry_run` reads once, checks conflicts, touches no file | `test_a_dry_run_reads_once_and_changes_nothing`, `test_a_dry_run_reports_conflicts_and_failures_too` |
| Writer failures (hand edit, storage, lock, inline array, access change, failed reload and restore) leave no partial entry | the writer failure tests of `tests/test_add_device.py` |
| Concurrent calls create one entry; sequential calls do not trip the baseline | `test_two_concurrent_calls_for_one_address_create_one_entry`, `test_two_different_addresses_both_succeed_in_sequence` |
| `devices[].mac` normalization, locator, round trip; stored MAC used by discovery (tool and CLI) | the config model and discovery consumer tests of `tests/test_add_device.py` |
| Class `manage`, full profile only, annotations false/false/false/true, identical descriptor over HTTP | the gating tests of `tests/test_add_device.py`, `tests/test_tool_contract.py`, `tests/test_access_profiles.py` |
| Call log and error data free of address, MAC and name | `test_the_call_log_names_no_address_mac_or_name`, `test_error_data_carries_fixed_text_and_ids_only` |

The tool-count budget measurement is in [issue-235.md](issue-235.md#enrollment-tool-203).

## Live enrollment (2026-11-19, two attempts)

Authority: [ISSUE-203-DEC-002](../decisions/issue-203.md) (one authorization per attempt, both
used and expired). The controller is "the selected test controller"; no address, MAC, host
name or firmware detail is recorded (DEC-005). Raw output stayed in a scratch directory
outside the repository and was deleted. The procedure of the #200 run was followed: stdio
only, a temporary inventory outside git, the real local-only inventory never passed to the
server, no mDNS, no scan, no write to any device.

### Attempt 1: failed on a stale address (`NOT_WLED`)

The address given for the run came from a remembered local note and was stale: the host name
that the local inventory uses for the selected test controller resolves to a different
address. The probe therefore went to another host, which was not WLED.

| Fact | Result |
| --- | --- |
| Tools listed; `wled_add_device` annotations | 41; false / false / false / true |
| Call 1 | `ok` false, `NOT_WLED`, `application` `not_applied`, 157 ms |
| Call 2 (sent after the failure, same arguments) | `ok` false, `NOT_WLED`, `not_applied`, 30 ms |
| Temporary inventory hash before and after | unchanged; no `.bak`, no lock file |
| Real inventory hash before and after | unchanged |
| stderr; temporary file | free of address, MAC and name; deleted |
| Request to the selected test controller | none |

Deviation, stated plainly: the second call was a repeat after a failure and made a second
`GET /json/info` to the same wrong host. That is one request beyond the authorized reach
(authorized: one). It was read-only, changed no state and reached no controller. The tool
behaved as specified (a non-WLED answer is `NOT_WLED`, nothing written). The attempt proves no
acceptance criterion and was not repeated blindly.

### Attempt 2: succeeded

The address was resolved at run time from the host name in the local-only inventory (one DNS
lookup, one IPv4 result, RFC 1918) and passed to one call. Tools were `tools/list` and
`wled_add_device` only.

| Check | Expected | Result |
| --- | --- | --- |
| 1 `tools/list` shows `wled_add_device`, class `manage`, full profile | present; false / false / false / true; class `manage` | pass. Annotations as expected; the class is not in the descriptor and was read from the server's call log (`class=manage`, seen on the repeat call). Full profile is the default of the run. |
| 2 `dry_run` call | not run | not run, by authorization (it would be an extra request); mock-covered only (`test_a_dry_run_reads_once_and_changes_nothing`) |
| 3 real call: `ok` true | true | pass (one call; `application` `not_attempted`, `verification` `not_requested`) |
| 3 returned entry equals the new file table | equal | pass (entry keys `id`, `name`, `base_url`, `mac`; the parsed file holds exactly that one table) |
| 3 `mac` stored | present | pass |
| 3 hash of the temporary file changed | changed | pass |
| 3 `.bak` equals the previous bytes | equal | pass. The previous bytes were the initial two-line file (`schema_version = 1`, `devices = []`), so this shows the writer's backup of that content, not of a populated inventory. |
| 3 `data`: `written`, `reloaded`, `inventory_size` | true, true, 1 | pass |
| 3 new ID usable by a read-only tool in the same process | optional | not run, by authorization (extra requests); mock-covered only (`test_a_served_call_returns_the_envelope_and_the_new_id_is_usable`) |
| 4 repeat after success | `INVENTORY_CONFLICT`, nothing changed, no request | pass: `INVENTORY_CONFLICT`, conflict kind `base_url` with the known device ID, `application` `not_attempted`; temporary file bytes unchanged. Refused before any read, so no second request reached the controller (inferred from the pre-read rule and the mocked test; the run had no network trace). |
| 5 stderr free of address, MAC and name | free | pass (one WARNING line, the call log of the repeat; no address-like, MAC-like or name text) |
| 6 real inventory hash before and after | unchanged | pass (bytes and directory listing equal) |
| 6 temporary inventory | deleted | pass (it held the entry, a `.bak` and the writer's lock file until deleted) |
| Requests to the selected test controller | one `GET /json/info` | one by design; not independently counted (no packet capture) |

DISC-T08, second half (single enrollment, live): **met** for the writer and verification path
with the selected test controller over stdio: one verified read, one inventory write with the
exact entry returned, the MAC stored, the backup kept and the duplicate refused. Not shown
live: the `dry_run` path, the use of the new ID by a read-only tool, the MAC-conflict rule
(the selected controller was not in the temporary inventory under another address), and the
restore from `.bak` of a populated inventory (the temporary file was simply deleted); all four
stay mock-covered. #204 keeps unicast discovery, the container deployment, the migration notes
and any further live evidence.

### Procedure hints for a later run

- An empty inventory is not a literally empty file (startup refuses it): start from
  `schema_version = 1` plus `devices = []`.
- Resolve the live address at run time (a DNS lookup of the host name in the local-only
  inventory). Do not reuse a remembered address; it can be stale. A failed call is recorded
  and not repeated; only a successful call is followed by the duplicate repeat.
- Say in the authorization how many calls and requests are allowed, including the repeat.
