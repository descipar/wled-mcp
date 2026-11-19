# Issue #203 validation: `wled_add_device`

Requirements: DISC-08; DISC-05 (the hard caps apply to the verification read), DISC-10 (reload),
DISC-T06 (writer path), DISC-T07 (gating), DISC-T08 (second half, the single enrollment: pending
live). Contract: [contract/discovery.md](../contract/discovery.md). Decisions:
[ISSUE-203-DEC-001](../decisions/issue-203.md) (proposed technical defaults),
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

## Live enrollment: pending

Status: not run. It needs a new, explicit owner authorization; [ISSUE-200-DEC-002](../decisions/issue-200.md)
expired and cannot be reused. The authorization must name the reach (the lesson of the #200 run).
Issue #203 stays open until this evidence exists (DISC-T08, second half).

Reach, stated up front:

- One `GET /json/info` of the one explicit address of the selected test controller (a literal
  RFC 1918 IPv4 address given by the owner at run time and not written into the repository).
- One inventory write, on a copy or the local inventory as the owner chooses.
- No mDNS, no range scan, no other host and no write to any device; over stdio, from the merged
  tool.

Inventory target (the owner chooses): a temporary copy of the local-only inventory outside the
repository (preferred, deleted afterwards), or the local inventory itself with its `.bak`. The
selected controller may be configured by host name there, so the duplicate-address rule cannot be
shown against it; the MAC rule is exercised only through an entry that stores `mac`, which the
enrollment itself creates.

Expected live checks:

1. `tools/list` shows `wled_add_device` (class `manage`, full profile).
2. `dry_run` call: `ok` true, entry shown, `written` false, inventory hash unchanged.
3. The real call: `ok` true, the returned entry equals the new file table, `mac` stored, hash
   changed, `.bak` equals the previous bytes, the new ID usable in the same process by a
   read-only tool (a read, no write).
4. Repeating the call: `INVENTORY_CONFLICT` (`base_url` or `mac`), nothing changed.
5. stderr and the committed record free of address, MAC and name.
6. Restore: the copy deleted, or the local inventory restored from `.bak` (hash equals the
   pre-run hash); no device state changed.

When executed, the record keeps counts and statuses only (DEC-005); raw output stays local and
untracked. A final row marks DISC-T08 second half as pass or names the observed deviation.

| Check | Expected | Result |
| --- | --- | --- |
| Live enrollment (checks 1 to 6) | as listed | pending, not run |
