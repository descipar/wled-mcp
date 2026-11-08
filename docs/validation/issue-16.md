# Issue #16 validation: setup, configuration validation, doctor and discovery

Evidence for [#16](https://github.com/descipar/wled-mcp/issues/16). First change:
`wled-mcp config init|add-device|validate` and the read-only `wled-mcp doctor`
(acceptance boxes AC1, AC2, AC4 and AC5; S2-SETUP-01, S2-SETUP-03, S2-T01; DEV-03 and
OPS-04 remainders). Second change: `wled-mcp discover` (AC3, S2-SETUP-02). Decisions: ISSUE-16-DEC-001 and ISSUE-16-DEC-002
([decision log](../decisions/issue-16.md)). Contract: [CLI](../contract/cli.md).
WLED mDNS facts: [SOURCES.md](../SOURCES.md#issue-16-wled-mdns-discovery-evidence).

All evidence is automated and uses synthetic values, temporary directories, mock
transports and loopback services only. No command was run against a LAN device or a
real network; no hardware evidence is claimed or needed for these boxes.

## Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| S16-T01 fresh user (AC1, S2-T01) | `tests/test_setup_cli.py::test_fresh_user_setup_validate_serve_both_transports_and_doctor`: the installed console, stdin closed, all paths in a temporary directory: `config init` for one controller (a synthetic loopback WLED), `config validate`, `doctor --format json` (device reachable), stdio serving and Streamable HTTP serving with the unchanged serve invocation, `wled_get_state` over both, `doctor --endpoint` against the running service; zero device POSTs; only the configuration file and the empty data directory exist afterwards. `scripts/check_distribution.py` (`setup_smoke`) repeats `config init`, `config validate` and `doctor --offline --format json` from the clean wheel install. |
| S16-T02 atomic config writes (AC2) | `tests/test_setup_cli.py`: `config init` writes only the selected file (no data or backups directory, mode 0600 on POSIX), refuses an existing target without `--force`, a missing directory, a relative path, partial device options (exit 2) and invalid values; `config add-device` keeps every original byte as prefix, refuses duplicate ID, equal normalized URL (case, default port, trailing slash), invalid value (positional message, planted credential absent), a result over 64 KiB, an invalid existing file, symbolic links (skipped where links are unavailable), a file changed between read and replace, and a failed replace, each leaving the directory byte-identical with no temporary file; the file mode is kept (POSIX); TOML escaping round-trips quotes, backslashes, non-ASCII text and control characters. Base URLs are never printed. |
| S16-T03 stage-1 configuration (AC5) | `test_shipped_and_retained_configurations_validate_unchanged`: `examples/bootstrap.toml`, `examples/devices.example.toml`, `examples/h01-h02.devices.example.toml` and the retained `tests/fixtures/compat/0.1.0/config.toml` pass `config validate` and stay byte-identical; `schema_version = 2` is rejected naming the version, file untouched; `config add-device` on a copy of the retained file keeps it as byte prefix. No schema change, so no migration note. `tests/test_upgrade_compat.py` passes unchanged. |
| S16-T04 doctor categories (AC4, S2-T01) | `tests/test_doctor.py`: (a) missing, relative, absent and non-file configuration paths; (b) invalid entry with the positional, value-free message; (c) missing, relative and absent data directory; (d) backups not writable (advisory `os.access`, nothing created); (e) unreachable, (f) timeout, (g) non-JSON and version-less responses; (h) `0.15.1`, `16.0.0-b1` and an unrecognized version are warnings with the `compat.support_warning` text, exit 0; (i) unknown capabilities are a warning; (j) endpoint connect failure; (k) 403/421 Host rejection against the loopback service; (l) 401 credential rejection; (m) non-MCP, 404 and timeout answers; plus endpoint OK, missing or invalid credential and invalid URL without any request. The healthy run sends only GET requests (the mock fails any other method) to `/json/state` and `/json/info`, changes no file and runs no tool on the HTTP service. A source check shows `doctor.py` imports neither `readmodels` nor `capabilities`. |
| S16-T05 sanitized export (AC4) | `test_export_contains_only_allowlisted_facts`: planted device ID, name, host, port, address, MAC, BSSID, SSID, token, token-file path, configuration path and endpoint host are all absent; `devices[0]` carries only the allowlisted firmware facts and unknown-capability names; checks carry only category, status, code and device position. `test_console_export_and_exit_codes` covers the console output and exit codes. |
| S16-T06 discovery (AC3) | `tests/test_discovery.py` (second change), every exchange through an injected fake socket and a simulated clock; an autouse guard fails on any real socket: one PTR question for `_wled._tcp.local`, class IN with the QU bit cleared, to 224.0.0.251:5353 (`test_first_query_is_one_ptr_question_for_the_wled_service`); at most one follow-up asking only for the missing SRV/TXT or A records, never a third datagram (`test_follow_up_asks_once_for_missing_records`, `test_never_more_than_one_follow_up_even_without_answers`); every datagram goes to the group, none to a candidate, and no HTTP client is involved (`assert_only_multicast` in each exchange); default window 3 s, `--timeout 10` accepted, 10.5, 0, -1, NaN, infinity and text exit 2 before a socket is opened; 70 answering instances give 64 candidates and `truncated`; duplicates merged by TXT `mac` (case folded) and, without one, by address; `--config` marks a candidate configured by address or `.local` name, suppresses its command and steers the suggested ID away from configured IDs, and the configuration directory stays byte-identical (`test_configured_devices_are_marked_and_the_inventory_is_not_written`); an invalid or missing `--config` is refused before any traffic; socket and send failures give `MULTICAST_UNAVAILABLE`, silence gives `NO_CANDIDATES`, both naming VLANs, bridge networks, multicast and `config add-device`; bounded receive errors. Untrusted answers: 14 malformed datagram classes (pointer to itself, forward pointer, pointer cycle, name over 255 bytes, reserved label type, truncations, overruns, too many records, non-response, error code, oversized) are dropped without stopping valid answers, 3000 seeded random corruptions never raise, compressed names are followed, control/format characters in instance and host names never reach the output, the suggested name and command contain no shell metacharacters, unusable addresses (unspecified, loopback, multicast, broadcast) give no URL. `test_default_socket_is_ipv4_udp_on_an_ephemeral_port` (recording stand-in, no traffic) and `test_discovery_is_never_used_outside_the_discover_command` (only `cli.py` imports `discovery`; no other module names the mDNS group). |
| S16-T07 validate (DEV-03) | `tests/test_setup_cli.py`: `config validate` returns the exact startup message (`load_config`) for invalid entries, unknown keys and broken TOML with a socket guard that fails on any socket; validates `--data-dir` and `--check-backups` (needs `--data-dir`, exit 2 otherwise) without creating anything; environment paths work like the server. docs/DEPLOYMENT.md "Changing the inventory" is now copy, edit, validate, restart. |
| S16-T08 OPS-04 | `test_every_ops04_condition_maps_to_a_doctor_result_with_an_action`: each condition (bad configuration, unsupported firmware, unavailable backup storage, offline device, invalid response) is produced and reported with a code from `OPS04_CONDITIONS` and a non-empty action. `test_serve_prints_one_backups_advisory_and_still_starts` and `test_serve_is_silent_when_backups_are_writable`: one stderr line, no path, serving continues. Tool-level `BACKUP_FAILED` tests are unchanged. |
| S16-T09 console compatibility | All existing `tests/test_bootstrap.py` and `tests/test_http_cli.py` cases pass unchanged; `test_parser_exposes_the_subcommands_to_the_coverage_check` (`scripts/check_coverage.py` reads `config`, `config init`, `config add-device`, `config validate`, `doctor` through `cli.build_parser()`); serve options with a subcommand, unknown actions and options exit 2 with the fixed message; an internal failure exits 3 without traceback or values. `tests/test_acceptance_parity.py` now checks every documented console flag against the `--help` of the (sub)command it is written after, with the negative control `test_subcommand_flags_are_checked_against_their_own_command`. |

## Coordinator-accepted deviations

Accepted by the coordinator on 2026-11-08 (not owner decisions):

1. `tests/test_acceptance_parity.py`, outside the packet's path list, was extended
   instead of weakened: documented console flags are checked against the `--help` of
   the (sub)command they follow, with a negative control.
2. Interpretations of TD-16-1/TD-16-5: a missing required path option of a `config`
   subcommand exits 2, a relative or unusable path exits 1; `doctor` reports a missing
   path as a failed check (exit 1), not a usage error; `doctor --endpoint` without a
   configured credential fails the check without sending a request; the added warning
   code `ENDPOINT_OTHER_SERVER` marks an MCP endpoint that is not wled-mcp; the export
   maps the envelope's `firmware.version`/`build_id`/`arch` to `ver`/`vid`/`arch`.

## Review round 1 (2026-11-08)

Findings of the independent review of `16e01ee` and their fixes:

| Finding | Fix | Test |
| --- | --- | --- |
| M1 unsearchable data directory crashed serve, `doctor` and `validate --check-backups` | `backups_writable` treats any `OSError` as not writable; `data_dir_usable` maps an inaccessible data directory to `DATA_DIR_NOT_FOUND` in `doctor`, `validate` and `init` | `tests/test_doctor.py`: `test_unsearchable_data_dir_still_serves_with_the_advisory`, `test_unsearchable_data_dir_is_reported_not_crashed`, `test_inaccessible_data_dir_maps_to_the_documented_code` (simulated EACCES), `test_real_unsearchable_data_dir` (real mode 0600, POSIX non-root, runs in Linux CI) |
| S1 failed directory fsync after `os.replace` reported as not written | directory fsync is best-effort after a successful replace; documented in the CLI contract | `test_directory_fsync_failure_after_replace_reports_written` |
| S2 generic `WRITE_FAILED` for the read-only `validate` and for invalid text | per-command codes `CHECK_FAILED` (validate) and `INVALID_TEXT` (device values checked before anything else) | `test_validate_io_failure_is_a_check_failure_not_a_write_failure`, `test_surrogate_in_device_value_is_an_input_error` |
| N1 abbreviated subcommand options accepted | `allow_abbrev=False` on every subparser | `test_subcommand_options_cannot_be_abbreviated` |
| N2 unsanitized server protocol version | only `YYYY-MM-DD` is shown or exported, otherwise `ENDPOINT_PROTOCOL_ERROR` | `test_endpoint_protocol_version_must_be_a_date` |
| N3 `--export` with `--format` | mutually exclusive (exit 2) | `test_export_and_format_are_mutually_exclusive` |
| N7, N8 | DEPLOYMENT.md: run the commands as the service user; cli.md: the credential goes to the given URL, use https or loopback | documentation |

The new tests were checked to fail on the unfixed source (10 of 14 selected cases;
the others are platform-skipped or already-rejected argument forms).

## Second change: discovery (AC3)

Contract: [CLI](../contract/cli.md#discover). TD-16-8 as recorded, with these
interpretations (agent, for coordinator review):

- The problem codes are upper case like every other CLI code: `MULTICAST_UNAVAILABLE`
  and `NO_CANDIDATES` (the packet wrote them in lower case).
- The query is a one-shot query from an ephemeral port (RFC 6762 section 5.1), so
  answers come back as unicast to that port and port 5353 is never bound; this keeps
  the command usable next to a running mDNS daemon. Answers to the query are from the
  devices; the command itself sends nothing but the two multicast datagrams.
- A candidate without an IPv4 address after the follow-up is listed without a URL or
  command; exit 0 needs at least one candidate with a suggested URL.
- The printed command uses a literal `<CONFIG>` placeholder instead of the configured
  path, keeping the rule that command output names no path.

The upper-case codes and the `<CONFIG>` placeholder were coordinator-accepted on
2026-11-08, not an owner decision.

Carried nits from the first-change review:

| Nit | Fix | Test |
| --- | --- | --- |
| `config init` reported an inaccessible directory as missing | `PARENT_MISSING` only for a missing or non-directory parent; `PARENT_INACCESSIBLE` when it cannot be inspected or is not writable | `test_init_names_a_missing_parent`, `test_init_reports_an_unwritable_parent_accurately`, `test_init_reports_an_uninspectable_parent_accurately` |
| N6 inline `devices = [{...}]` array | `config add-device` refuses with `INLINE_DEVICES_ARRAY` and the hint to use `[[devices]]` tables; file unchanged | `test_add_device_hints_at_an_inline_devices_array` |

`tests/test_coverage.py::test_unknown_cli_command_fails_c3_and_a_known_one_passes`
used `discover` as its example of an unknown command; it now uses a synthetic name and
still checks that `discover` passes in a context that has it (outside the packet path
list, needed because the command now exists).

## Second change: review round 1 (2026-11-08)

Findings of the independent review of `548dce8` and their fixes (no must-fix items):

| Finding | Fix | Test |
| --- | --- | --- |
| S1 non-encodable answer text made `discover` exit 3 with empty stdout on a non-UTF-8 stdout | answer text is printed as ASCII only (one rule for text and JSON: other characters become `?`) | `test_non_encodable_answer_text_does_not_hide_other_candidates` (invalid UTF-8 and an emoji, cp1252 stdout, text and json, other candidates still printed), `test_safe_text_is_ascii_printable_only` |
| S2 answer source never checked | datagrams not from IPv4 port 5353 are dropped and counted (`dropped_datagrams`, also toward the datagram bound); other addresses with port 5353 stay accepted; no on-link/TTL check, documented | `test_answers_not_from_ipv4_port_5353_are_dropped`, `test_other_source_address_with_port_5353_stays_accepted`, `test_dropped_datagrams_count_toward_the_datagram_bound` |
| S3 scope test bypassable with `from wled_mcp.discovery import ...` | AST check of Import, ImportFrom (absolute, relative, `from wled_mcp import discovery`) and module-path string constants across all of `src/wled_mcp` | `test_scope_check_detects_every_import_form` (negative control: planted import in a scratch copy of a module), `test_discovery_is_never_used_outside_the_discover_command` |
| N1 leading dash in a name read as an option | leading dashes removed from the suggested name | `test_leading_dashes_in_a_name_cannot_become_an_option` |
| N2 missing bounds tests | lower timeout bound, `MAX_TXT_STRINGS`, `MAX_DATAGRAMS`, follow-up with known addresses sends nothing unicast, malformed cases assert their own reason (not truncation) | `test_lower_timeout_bound_is_accepted_and_just_below_is_not`, `test_txt_string_count_is_bounded`, `test_datagram_bound_stops_a_flood`, `test_known_addresses_with_a_follow_up_send_nothing_to_candidates`, `test_malformed_answers_are_dropped` (reason match) |
| N3 `0.0.0.0/8` and `240.0.0.0/4` suggested | filtered | `test_this_network_and_reserved_ranges_are_not_suggested` |
| N4, N6 | long line wrapped; limits sentences added (junk can fill the collections early; default multicast interface only) | documentation |

The new tests were checked to fail on the unfixed source (S1, S2 and N1 mutants).

## Runs

Local runs on the implementation branch (Windows 11, Python 3.13):

| Command | Result |
| --- | --- |
| `uv run --frozen pytest` | all new tests pass; the only failures are the known Windows-local ones (6 failed, 5 errors in `test_inventory_client.py` and `test_hw_http_probe.py`, unchanged from `main`) |
| `uv run --frozen ruff check .` / `ruff format --check .` | pass |
| `uv run --frozen mypy` | pass (strict) |
| `python scripts/check_coverage.py` | pass; figures unchanged (W-INFO-03 lists `cli: wled-mcp doctor`, status unchanged) |
| `python scripts/check_distribution.py` | wheel, clean install, setup smoke, installed stdio and HTTP restart and uvx stdio pass; the stdio hub example step fails locally at its uvx handshake because the checkout path contains a space (known local limit); runs fully in Linux CI |

Second change, same platform:

| Command | Result |
| --- | --- |
| `uv run --frozen pytest` | 1899 passed, 23 skipped (after review round 1); only the known Windows-local failures (6 failed, 5 errors in `test_inventory_client.py` and `test_hw_http_probe.py`) |
| `uv run --frozen ruff check .` / `ruff format --check .` / `mypy` | pass |
| `python scripts/check_coverage.py --update`, then without `--update` | W-INFO-09 supported; after merging main with #19: 47 % overall (41.5 of 89), 58 % planned scope (41.5 of 71); INFO 4 supported, 0 planned; no planned row is left |
| `check_traceability.py`, `check_private_identifiers.py`, `sync_agents.py --check`, `uv lock --check` | pass |

`wled-mcp discover` was never run against a real network, neither by the tests nor
manually.

CI run evidence is recorded in the pull request.

## Limits

- Symbolic-link refusal and POSIX file modes are verified only where the platform
  supports them (skipped on the Windows run, executed in Linux CI).
- The backups check is advisory (`os.access`); hard-link support is not verified,
  because that needs a write. Snapshot-taking tools still fail closed.
- No `doctor`, `config` or `discover` command was run against a real device or
  network; a later read-only observation on hardware needs its own authorization and
  is not required for these boxes.
- Discovery is verified against a fake socket only. Whether the WLED responder
  libraries answer a one-shot query from an ephemeral port as RFC 6762 section 5.1
  describes, and how host firewalls treat those unicast answers, is not observed.
  IPv6 mDNS, controllers with an empty mDNS name and networks without multicast are
  documented limits.
