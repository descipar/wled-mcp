# Issue #16 validation: setup, configuration validation, doctor and discovery

Evidence for [#16](https://github.com/descipar/wled-mcp/issues/16). First change:
`wled-mcp config init|add-device|validate` and the read-only `wled-mcp doctor` (AC1, AC2, AC4, AC5;
S2-SETUP-01, S2-SETUP-03, S2-T01; DEV-03 and OPS-04 remainders). Second change: `wled-mcp discover`
(AC3, S2-SETUP-02). Decisions ISSUE-16-DEC-001 and ISSUE-16-DEC-002
([decision log](../decisions/issue-16.md)). Contract: [CLI](../contract/cli.md). WLED mDNS facts:
[SOURCES.md](../SOURCES.md#issue-16-wled-mdns-discovery-evidence).

All evidence is automated with synthetic values, temporary directories, mock transports and loopback
services only. No command was run against a LAN device or real network; no hardware evidence is
claimed or needed for these boxes.

## Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| S16-T01 fresh user (AC1, S2-T01) | `tests/test_setup_cli.py::test_fresh_user_setup_validate_serve_both_transports_and_doctor`: installed console, temporary directory: `config init`, `config validate`, `doctor --format json`, stdio and Streamable HTTP serving, `wled_get_state` over both, `doctor --endpoint`; zero device POSTs. `scripts/check_distribution.py` (`setup_smoke`) repeats init, validate and `doctor --offline` from the clean wheel. |
| S16-T02 atomic config writes (AC2) | `tests/test_setup_cli.py`: `config init` writes only the selected file (0600 on POSIX), refuses existing target without `--force`, missing directory, relative path, partial options and invalid values; `config add-device` keeps every original byte as prefix and refuses duplicate ID, equal normalized URL, invalid value, over 64 KiB, invalid file, symbolic links, concurrent change and failed replace, leaving the directory byte-identical; TOML escaping round-trips; base URLs never printed. |
| S16-T03 stage-1 configuration (AC5) | `test_shipped_and_retained_configurations_validate_unchanged`: shipped examples and the retained `0.1.0` config pass `config validate` byte-identical; `schema_version = 2` rejected; no schema change, no migration note; `tests/test_upgrade_compat.py` unchanged. |
| S16-T04 doctor categories (AC4, S2-T01) | `tests/test_doctor.py`: configuration path problems, invalid entry (value-free message), data directory, advisory backups check, unreachable, timeout, non-JSON and version-less responses, firmware warnings (`0.15.1`, `16.0.0-b1`, unrecognized; exit 0), unknown capabilities, endpoint failures (connect, 403/421 Host, 401, non-MCP, 404, timeout, invalid URL). A healthy run sends only GET requests, changes no file and runs no tool; `doctor.py` imports neither `readmodels` nor `capabilities`. |
| S16-T05 sanitized export (AC4) | `test_export_contains_only_allowlisted_facts`: planted ID, name, host, port, address, MAC, BSSID, SSID, token, token-file path, configuration path and endpoint host are absent; `test_console_export_and_exit_codes`. |
| S16-T06 discovery (AC3) | `tests/test_discovery.py` with an injected fake socket and simulated clock (an autouse guard fails on any real socket): one PTR question for `_wled._tcp.local` to 224.0.0.251:5353, at most one follow-up, only multicast datagrams, no HTTP client; default window 3 s, `--timeout 10` accepted, invalid values exit 2 before a socket; 70 instances give 64 candidates and `truncated`; duplicates merged by TXT `mac` or address; `--config` marks configured devices and the configuration stays byte-identical; socket failures give `MULTICAST_UNAVAILABLE`, silence `NO_CANDIDATES`. Untrusted answers: 14 malformed datagram classes dropped, 3000 seeded corruptions never raise, control characters and shell metacharacters never reach output, unusable addresses give no URL. `test_discovery_is_never_used_outside_the_discover_command`. |
| S16-T07 validate (DEV-03) | `tests/test_setup_cli.py`: `config validate` returns the exact startup message for invalid entries, unknown keys and broken TOML (socket guard); `--data-dir` and `--check-backups` validated without creating anything; DEPLOYMENT.md "Changing the inventory" is copy, edit, validate, restart. |
| S16-T08 OPS-04 | `test_every_ops04_condition_maps_to_a_doctor_result_with_an_action`; `test_serve_prints_one_backups_advisory_and_still_starts` and `test_serve_is_silent_when_backups_are_writable`; tool-level `BACKUP_FAILED` tests unchanged. |
| S16-T09 console compatibility | Existing `test_bootstrap.py` and `test_http_cli.py` pass unchanged; `test_parser_exposes_the_subcommands_to_the_coverage_check`; unknown actions and options exit 2, internal failure exit 3 without traceback. `tests/test_acceptance_parity.py` checks every documented console flag against the `--help` of its (sub)command, with a negative control. |

## Coordinator-accepted deviations

Accepted by the coordinator on 2026-11-08 (not owner decisions): `tests/test_acceptance_parity.py`
(outside the packet path list) was extended rather than weakened; interpretations of TD-16-1/TD-16-5: a
missing required path option exits 2, a relative or unusable path exits 1, `doctor` reports a missing
path as a failed check (exit 1), `doctor --endpoint` without a credential fails without sending a
request, `ENDPOINT_OTHER_SERVER` marks an MCP endpoint that is not wled-mcp, the export maps
`firmware.version`/`build_id`/`arch` to `ver`/`vid`/`arch`.

## Review round 1 (2026-11-08)

Independent review of `16e01ee`; each finding fixed with a test that was checked to fail on the unfixed
source (10 of 14 selected cases; the rest platform-skipped or already rejected):

- M1 unsearchable data directory crashed serve, `doctor` and `validate --check-backups`: any `OSError`
  now means not writable, mapped to `DATA_DIR_NOT_FOUND`.
- S1 failed directory fsync after `os.replace` is best-effort (documented); S2 per-command codes
  `CHECK_FAILED` and `INVALID_TEXT` instead of `WRITE_FAILED`.
- N1 `allow_abbrev=False`; N2 only `YYYY-MM-DD` protocol versions shown, else `ENDPOINT_PROTOCOL_ERROR`;
  N3 `--export` and `--format` exclusive; N7/N8 documentation (run as the service user; use https or
  loopback for credentials).

## Second change: discovery (AC3)

Contract: [CLI](../contract/cli.md#discover). TD-16-8 with these interpretations (agent, for
coordinator review): upper-case codes `MULTICAST_UNAVAILABLE` and `NO_CANDIDATES`; a one-shot query from
an ephemeral port (RFC 6762 section 5.1), port 5353 never bound; a candidate without IPv4 is listed
without URL or command (exit 0 needs one with a URL); the printed command uses a literal `<CONFIG>`
placeholder. Upper-case codes and `<CONFIG>` were coordinator-accepted on 2026-11-08, not owner decisions.

Carried nits from review 1: `config init` distinguishes `PARENT_MISSING` from `PARENT_INACCESSIBLE`;
an inline `devices = [{...}]` array is refused with `INLINE_DEVICES_ARRAY`.
`tests/test_coverage.py` now uses a synthetic unknown command (outside the packet path list, needed
because `discover` exists).

### Review round 1 of the second change (2026-11-08)

Independent review of `548dce8`, no must-fix items; fixes with tests checked to fail on the unfixed
source (S1, S2, N1 mutants):

- S1 non-encodable answer text no longer breaks output (ASCII-only printing).
- S2 datagrams not from IPv4 port 5353 are dropped and counted toward the datagram bound.
- S3 scope test now an AST check of every import form across `src/wled_mcp`, with a negative control.
- N1 leading dashes removed from suggested names; N2 bounds tests (timeout lower bound, TXT string and
  datagram bounds, no unicast follow-up for known addresses); N3 `0.0.0.0/8` and `240.0.0.0/4` not
  suggested; N4/N6 documentation (junk can fill collections early; default multicast interface only).

## Runs

Implementation branch, Windows 11, Python 3.13:

| Command | Result |
| --- | --- |
| `uv run --frozen pytest` (first change) | new tests pass; only the known Windows-local failures (6 failed, 5 errors in `test_inventory_client.py` and `test_hw_http_probe.py`, unchanged from `main`) |
| ruff, `mypy` (strict), `check_coverage.py` | pass |
| `check_distribution.py` | wheel, clean install, setup smoke, stdio, HTTP restart, uvx pass; the stdio hub example step fails locally because the checkout path contains a space (known local limit, runs in Linux CI) |
| Second change `pytest` | 1899 passed, 23 skipped; same Windows-local failures |
| `check_coverage.py --update` (W-INFO-09 supported, after merging main with #19) | 47 % overall (41.5 of 89), 58 % planned scope (41.5 of 71); no planned row left |
| `check_traceability.py`, `check_private_identifiers.py`, `sync_agents.py --check`, `uv lock --check` | pass |

`wled-mcp discover` was never run against a real network. CI evidence is recorded in the pull request.

## Limits

- Symbolic-link refusal and POSIX file modes verified only where supported (skipped on Windows,
  executed in Linux CI). The backups check is advisory (`os.access`); snapshot tools still fail closed.
- No `doctor`, `config` or `discover` command was run against a real device or network; a read-only
  hardware observation needs its own authorization and is not required for these boxes.
- Discovery is verified against a fake socket only: whether WLED responders answer a one-shot query
  from an ephemeral port per RFC 6762 section 5.1, and how host firewalls treat the unicast answers, is
  not observed. IPv6 mDNS, empty mDNS names and networks without multicast are documented limits.
