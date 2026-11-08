# Issue #16 validation: setup, configuration validation and doctor

Evidence for the first change of [#16](https://github.com/descipar/wled-mcp/issues/16):
`wled-mcp config init|add-device|validate` and the read-only `wled-mcp doctor`
(acceptance boxes AC1, AC2, AC4 and AC5; S2-SETUP-01, S2-SETUP-03, S2-T01; DEV-03 and
OPS-04 remainders). Decisions: ISSUE-16-DEC-001 and ISSUE-16-DEC-002
([decision log](../decisions/issue-16.md)). Contract: [CLI](../contract/cli.md).
Discovery (AC3, S2-SETUP-02) is the second change and has no evidence here yet.

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
| S16-T06 discovery (AC3) | Not part of this change. |
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

## Runs

Local runs on the implementation branch (Windows 11, Python 3.13):

| Command | Result |
| --- | --- |
| `uv run --frozen pytest` | all new tests pass; the only failures are the known Windows-local ones (6 failed, 5 errors in `test_inventory_client.py` and `test_hw_http_probe.py`, unchanged from `main`) |
| `uv run --frozen ruff check .` / `ruff format --check .` | pass |
| `uv run --frozen mypy` | pass (strict) |
| `python scripts/check_coverage.py` | pass; figures unchanged (W-INFO-03 lists `cli: wled-mcp doctor`, status unchanged) |
| `python scripts/check_distribution.py` | wheel, clean install, setup smoke, installed stdio and HTTP restart and uvx stdio pass; the stdio hub example step fails locally at its uvx handshake because the checkout path contains a space (known local limit); runs fully in Linux CI |

CI run evidence is recorded in the pull request.

## Limits

- Symbolic-link refusal and POSIX file modes are verified only where the platform
  supports them (skipped on the Windows run, executed in Linux CI).
- The backups check is advisory (`os.access`); hard-link support is not verified,
  because that needs a write. Snapshot-taking tools still fail closed.
- No `doctor` or `config` command was run against a real device or network; a later
  read-only observation on hardware needs its own authorization and is not required
  for these boxes.
