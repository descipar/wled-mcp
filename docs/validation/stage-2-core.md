# Validation: stage 2 core features (issues #16 to #20)

## Issue #16 validation: setup, configuration validation, doctor and discovery

Evidence for [#16](https://github.com/descipar/wled-mcp/issues/16). First change:
`wled-mcp config init|add-device|validate` and the read-only `wled-mcp doctor` (AC1, AC2, AC4, AC5;
S2-SETUP-01, S2-SETUP-03, S2-T01; DEV-03 and OPS-04 remainders). Second change: `wled-mcp discover`
(AC3, S2-SETUP-02). Decisions ISSUE-16-DEC-001 and ISSUE-16-DEC-002
([decision log](../decisions/stage-2.md)). Contract: [CLI](../contract/cli.md). WLED mDNS facts:
[SOURCES.md](../SOURCES.md#issue-16-wled-mdns-discovery-evidence).

All evidence is automated with synthetic values, temporary directories, mock transports and loopback
services only. No command was run against a LAN device or real network; no hardware evidence is
claimed or needed for these boxes.

### Scenario to evidence

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

### Coordinator-accepted deviations

Accepted by the coordinator on 2026-11-08 (not owner decisions): `tests/test_acceptance_parity.py`
(outside the packet path list) was extended rather than weakened; interpretations of TD-16-1/TD-16-5: a
missing required path option exits 2, a relative or unusable path exits 1, `doctor` reports a missing
path as a failed check (exit 1), `doctor --endpoint` without a credential fails without sending a
request, `ENDPOINT_OTHER_SERVER` marks an MCP endpoint that is not wled-mcp, the export maps
`firmware.version`/`build_id`/`arch` to `ver`/`vid`/`arch`.

### Review round 1 (2026-11-08)

Independent review of `16e01ee`; each finding fixed with a test that was checked to fail on the unfixed
source (10 of 14 selected cases; the rest platform-skipped or already rejected):

- M1 unsearchable data directory crashed serve, `doctor` and `validate --check-backups`: any `OSError`
  now means not writable, mapped to `DATA_DIR_NOT_FOUND`.
- S1 failed directory fsync after `os.replace` is best-effort (documented); S2 per-command codes
  `CHECK_FAILED` and `INVALID_TEXT` instead of `WRITE_FAILED`.
- N1 `allow_abbrev=False`; N2 only `YYYY-MM-DD` protocol versions shown, else `ENDPOINT_PROTOCOL_ERROR`;
  N3 `--export` and `--format` exclusive; N7/N8 documentation (run as the service user; use https or
  loopback for credentials).

### Second change: discovery (AC3)

Contract: [CLI](../contract/cli.md#discover). TD-16-8 with these interpretations (agent, for
coordinator review): upper-case codes `MULTICAST_UNAVAILABLE` and `NO_CANDIDATES`; a one-shot query from
an ephemeral port (RFC 6762 section 5.1), port 5353 never bound; a candidate without IPv4 is listed
without URL or command (exit 0 needs one with a URL); the printed command uses a literal `<CONFIG>`
placeholder. Upper-case codes and `<CONFIG>` were coordinator-accepted on 2026-11-08, not owner decisions.

Carried nits from review 1: `config init` distinguishes `PARENT_MISSING` from `PARENT_INACCESSIBLE`;
an inline `devices = [{...}]` array is refused with `INLINE_DEVICES_ARRAY`.
`tests/test_coverage.py` now uses a synthetic unknown command (outside the packet path list, needed
because `discover` exists).

#### Review round 1 of the second change (2026-11-08)

Independent review of `548dce8`, no must-fix items; fixes with tests checked to fail on the unfixed
source (S1, S2, N1 mutants):

- S1 non-encodable answer text no longer breaks output (ASCII-only printing).
- S2 datagrams not from IPv4 port 5353 are dropped and counted toward the datagram bound.
- S3 scope test now an AST check of every import form across `src/wled_mcp`, with a negative control.
- N1 leading dashes removed from suggested names; N2 bounds tests (timeout lower bound, TXT string and
  datagram bounds, no unicast follow-up for known addresses); N3 `0.0.0.0/8` and `240.0.0.0/4` not
  suggested; N4/N6 documentation (junk can fill collections early; default multicast interface only).

### Runs

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

### Limits

- Symbolic-link refusal and POSIX file modes verified only where supported (skipped on Windows,
  executed in Linux CI). The backups check is advisory (`os.access`); snapshot tools still fail closed.
- No `doctor`, `config` or `discover` command was run against a real device or network; a read-only
  hardware observation needs its own authorization and is not required for these boxes.
- Discovery is verified against a fake socket only: whether WLED responders answer a one-shot query
  from an ephemeral port per RFC 6762 section 5.1, and how host firewalls treat the unicast answers, is
  not observed. IPv6 mDNS, empty mDNS names and networks without multicast are documented limits.

## Issue #17 validation: device groups, scenes, plan, apply and sharing

Evidence for [#17](https://github.com/descipar/wled-mcp/issues/17); contract in
[contract/groups-scenes.md](../contract/groups-scenes.md), decisions in
[ISSUE-17-DEC-001 and -002](../decisions/stage-2.md). Pull request A (definitions, store,
sharing, `wled_plan_scene`) and pull request B (`wled_apply_scene`, executor, policy, aggregate
outcome) are covered.

**All evidence is mock evidence.** The fleet is `tests/scene_support.py` (several stateful
`FakeWLED` devices behind one router with failure injections, request log and in-flight gauges);
console tests use the loopback fake of `tests/acceptance_support.py`. Stores use `tmp_path`. No
LAN device or hardware was used; no multi-device or synchronization behavior of real controllers
is claimed.

### Scenario to test map

| Scenario | Evidence |
| --- | --- |
| AC-17-01 group definitions: unknown device, duplicates, bounds, ID pattern, overwrite, zero device I/O, listing flags a member that left the inventory | `tests/test_groups.py`; `tests/test_scene_tools.py` `test_save_group_*`, `test_list_groups_*`, `test_delete_group_*` |
| AC-17-02 scene format 1: strict parse, `format_version` named, newer file untouched and counted, save/delete refuse unreadable files | `tests/test_scenes.py`; `tests/test_scene_store.py` (newer-version and unusable-file tests); `tests/test_scene_tools.py` (version and overwrite dry-run tests) |
| AC-17-03 store durability: atomic save, failed write keeps the previous file, permissions, unwritable directory, `dry_run`, bounds, path-safe IDs, symlinks | `tests/test_scene_store.py` (failed replace/fsync, 0700/0600 on POSIX, dry run, path-safe IDs, symlink refusal, no names/paths in diagnostics, concurrent saves) |
| AC-17-04 plan: exact targets with origin and order, per-device reachability, real planners, names per device, bounded ambiguity candidates, refusals equal to the single-device tools, offline device, zero POST | `tests/test_scene_tools.py` `test_plan_*`, `test_planner_refusals_equal_the_single_device_tool_refusals` (six refusals compared message by message), `test_plan_requests_are_reads_only_and_never_a_post` |
| AC-17-05 duplicate policy | `tests/test_scenes.py` (device once after expansion, same group twice); `tests/test_scene_tools.py` (duplicate refuses the whole plan before any I/O, group changed after saving is rechecked) |
| AC-17-06 ordering and concurrency (at most four devices in flight, results in expansion order, per-device lock) | read: `tests/test_scene_tools.py` (8 devices, gauge exactly 4; 16 plan, 17 refused); write: `tests/test_scene_apply.py` (gauge exactly 4 inside the POST, per-host gauge 1, master then segments, one POST for one target kind) |
| AC-17-07 policy: `strict` writes nothing if any preflight fails, `best_effort` skips only failing devices, a write-phase failure never stops the others | `tests/test_scene_apply.py` `test_strict_*`, `test_best_effort_*`, `test_a_device_failing_in_the_write_phase_never_stops_or_undoes_another`, per-device unknown-device and below-control refusals |
| AC-17-08 outcomes pass through unchanged; no replay; aggregate mapping; no compensation; "not atomic, not synchronized" | `tests/test_scene_apply.py` (lost readback `unknown/unknown`, ignored/failed POST `unknown/mismatch`, uncertain segment step never replayed, timed-out write never retried, partial device `applied/mismatch`, aggregate mapping over 258 combinations, strict block marks devices not written, stopped scene, bug-after-send stays unknown, no logging of names/content) |
| AC-17-09 `wled_apply_scene dry_run=true` equals the plan and sends no POST | `tests/test_scene_apply.py` `test_apply_dry_run_*`; `tests/test_scene_parity.py` real-transport apply |
| AC-17-10 sharing: placeholders, host-token refusal, `include_targets`, `target_map` validation, all or nothing, round trip, retained example | `tests/test_scenes.py` (`export_*`, `target_map_*`, retained example); `tests/test_scene_tools.py` (export carries no inventory identity and equals `examples/contracts/scene.json`, host-name refusal, round trip, all-or-nothing) |
| AC-17-11 classification | `tests/tool_contract.py` (eight scene tools, 26 in total) vs. registry in `tests/test_tool_contract.py`; `tests/test_scene_apply.py` apply is `control`, not destructive; `tests/test_access_profiles.py`; apply reaches devices only through the write engine guarded by #20 (`require_access` once per expanded device, G3 refusal with zero POST, profile cap) |
| AC-17-12 transport parity | `tests/test_scene_parity.py`: eighteen ordered steps over stdio and loopback Streamable HTTP, identical envelopes; only the two real applies send POSTs |
| AC-17-13 contract evolution | `tests/test_upgrade_compat.py` passes without a migration note (additive tools and `STORAGE_FAILED`); no existing schema changed |
| AC-17-14 hardware honesty | Mocks only; no hardware claim |

### Carried items of the pull request A review

| Item | Evidence |
| --- | --- |
| Store-level ID check is the refusal (mutant M16) | `tests/test_scene_store.py` `test_the_store_id_check_is_the_refusal_not_a_missing_file` |
| Windows device names are not group or scene IDs | `test_windows_device_names_are_not_usable_ids`, `test_names_that_only_resemble_a_device_name_stay_valid` |
| One store lock per directory | `test_two_store_instances_over_one_directory_cannot_create_the_same_id` |
| Leak check scans every exported string | `tests/test_scenes.py` and `tests/test_scene_tools.py` export-scan tests |
| `bundles.py` uses the shared `format_version` helper | `tests/test_bundles.py` unchanged and passing |
| Doc corrections (`DESTRUCTIVE` comment, segment `effect_name`/`palette_name` wording) | `docs/TOOL-CONTRACT.md` |

### Reading choices

Choices where the packet or the technical defaults leave room.

#### Reading choices (pull request B)

1. A device that is "unknown" aggregates as `application=unknown` (`unknown/unknown` +
   `WRITE_OUTCOME_UNKNOWN`, TD-17-10); device entries keep the exact verification.
2. `wled_apply_scene dry_run=true` includes the per-device `control` ceiling check; the read-class
   `wled_plan_scene` does not. Otherwise identical.
3. A proven master step followed by a segment step refused before sending is `applied/mismatch`.
4. Master and segments are two `write_verified` calls; another writer can interleave between them.
5. An aggregate that wrote nothing returns the first refusal in expansion order, device named.
6. A stopped call returns no result; the contract states untouched versus uncertain devices.
7. The apply annotations are a local constant in `scene_tools.py` (`operations.py` imports it).

#### Reading choices (pull request A)

1. `wled_save_group` takes typed arguments; `wled_save_scene` an inline document (TD-17-4, -5).
2. Plan-time device check is per device (`UNKNOWN_DEVICE` preflight failure, no I/O); unknown
   groups, duplicates, limits and ids-less members refuse the whole request (TD-17-7).
3. Plan envelope `ok=true` when something would be written under the mode; always `dry_run=true`.
4. Saving validates references and expansion against the groups stored at that moment.
5. `placeholders` exists only in a shared document.
6. Explicit `ids` in a group target apply to every member; omitted `ids` use the designation.
7. Local definition tools report `application=not_attempted`.
8. The store write lock is a `threading.Lock` inside the store.
9. Coordination with #20: scene tools are plain `Operation` constructions appended to the registry;
   the guard is in the write engines and `Resources.require_access`, not `Resources.operation`.
10. `docs/TOOL-CONTRACT.md` segment sections were corrected (numeric IDs only).

### Commands run

Windows 11, `uv run --frozen`, candidate after merging `main` (#116); CI results in the PR.

| Command | Result |
| --- | --- |
| `pytest` (all except two known-problem files) | 2491 passed, 25 skipped |
| `pytest tests/test_inventory_client.py tests/test_hw_http_probe.py` | 171 passed, 6 failed, 5 errors: known Windows-only, unrelated |
| #17 tests (`test_groups`, `test_scenes`, `test_scene_store`, `test_scene_tools`, `test_scene_parity`, `test_scene_apply`) | 658 passed, 2 skipped (POSIX permission bits, directory symlink) |
| `ruff check`, `ruff format --check`, `mypy` (strict) | clean; no issues in 43 source files |
| traceability, coverage (`--update`), `sync_agents --check`, private identifiers, agent setup | pass |
| `scripts/check_distribution.py` | fails locally only at the `uvx` stdio handshake (checkout path contains a space); CI authoritative |
| hand mutation spot checks on apply code and carried items | every mutant killed |

### Known limits

- Mock evidence only; no multi-device or synchronization behavior of real controllers is claimed
  and hardware acceptance of #17 is not part of this evidence. A single-controller scene smoke
  needs its own authorization.
- Several server processes on one data directory are not coordinated.
- Plan results are a snapshot; the apply plans again under each device lock.
- A stopped call leaves unstarted devices untouched and in-flight writes uncertain; the HTTP drain
  (operation timeout plus two seconds) is shorter than a 16-device scene can take.
- Master and segments of one device are two write operations.
- Directory-symlink and POSIX permission tests run only on POSIX hosts (CI).

## Issue #18 validation evidence

Evidence for [issue #18](https://github.com/descipar/wled-mcp/issues/18). Contract:
[contract/presets.md](../contract/presets.md). Requirements: PRE-03, PRE-04 (restore execution),
PLAY-01 and S2-PRESET-01 to -03 of [STAGE-2.md](../STAGE-2.md).

Mock transport and `tmp_path` only; no LAN, device or hardware access. The stateful fakes
(`tests/preset_support.py`, `tests/bundle_support.py`) model the WLED v16.0.1 write routes recorded
in [SOURCES.md](../SOURCES.md#issue-18-wled-16-preset-write-evidence) (firmware set explicitly).
Nothing here is hardware acceptance.

### First pull request: restore, supplied-state save, snapshot listing

| Scenario | Evidence |
| --- | --- |
| A18-01 state route: supplied state stored verbatim and verified, live effect in plan and result, firmware-removed keys excluded, one POST | `tests/test_preset_writes.py` (apply-then-store with one POST, dry run, any stored difference is a mismatch, minimal state) |
| A18-02 unknown/control keys, out-of-range segments, bad names refused with zero POSTs; occupied ID without `overwrite` is a conflict; snapshot before the POST; backup failure sends nothing | `tests/test_preset_writes.py` (schema, name rules, overwrite ID, range, color capability, conflict, snapshot-before-POST, backup failure, unknown device) |
| A18-03 state restore to own free ID, explicit other ID, occupied ID (overwrite plus new snapshot); firmware mismatch, api-command/unknown snapshot, destination changed after planning; dry run sends nothing, creates no file | `tests/test_restore.py` (`test_state_snapshot_*`, occupied destination, firmware mismatch, refused snapshot kinds, changed destination, dry run, bad backup IDs) |
| A18-04 playlist restore through the playlist route, semantic verification, unreproducible playlist fields block in the preview, playback effect named | `tests/test_restore.py` (`test_playlist_*`) |
| A18-05 timeout with unreadable readback is `unknown`, no resend | `tests/test_preset_writes.py` and `tests/test_restore.py` timeout tests |
| A18-06 `wled_list_snapshots` newest first, counts invalid files, reads no device | `tests/test_restore.py::test_list_snapshots_*` |
| A18-14 transport parity for the new tools | `tests/test_preset_writes.py::test_protocol_envelope_and_schema_errors_for_the_new_tools`; registry parity via `tests/test_http_service.py` and `tests/test_http_cli.py` against `tests/tool_contract.py` |
| A18-15 log privacy | `tests/test_preset_writes.py::test_logs_carry_no_preset_names_or_objects` |
| Registry and coverage | `tests/tool_contract.py`, `tests/test_tool_contract.py`, `tests/test_coverage.py`, `tests/test_readme.py` |

Firmware facts (pinned source review, not observed on hardware): a playlist save runs after
`loadPlaylist` but before the playlist advances, so finite `repeat` and shuffle are stored and
accepted; a running playlist could be stored instead, so the playlist route is refused while one
runs; a nameless state write is stored as `Preset <id>`.

Correction round 1 (review of `01d0c81`): source `backup_id` protected from retention pruning
during restore (M-1); finite `repeat` and shuffle accepted with semantic readback (S1); playlist
route refused with `PRESET_CONFLICT` while `state.pl` > 0, at planning and after the snapshot;
`transition` bounded to 0-655 tenths, `bs` to 0-31; member recheck after the snapshot is a
conflict; interference and referencing-playlist warnings tested. Evidence: `tests/test_restore.py`
and `tests/test_preset_writes.py` tests of the same names.

Hardware: not run. A check of both routes needs its own human authorization naming the controller
and a captured restorable baseline (DEC-021 "Hardware"); the hardware outcome is pending.

Commands (Windows, 2026-11-07, after correction round 1; CI in the PR): `pytest` 1286 passed, 18
skipped, 6 failed and 5 errors in `tests/test_inventory_client.py` / `tests/test_hw_http_probe.py`
(Windows-only, same as `main`); the two new files 104 passed; ruff, strict mypy (28 files),
traceability, coverage (43 % planned / 34 % overall), agent sync, agent setup, lock, private
identifiers pass; `check_distribution.py` fails locally only at the uvx stdio handshake (path with
a space), Linux CI is the reference.

### Second pull request: playlist authoring, bundle export and import

The retained bundle fixture `examples/contracts/preset-bundle.json` is actual export output of the
synthetic fixture device.

| Scenario | Evidence |
| --- | --- |
| A18-07 playlist authoring: invalid or non-state member, more than 100 members, `end=255`, wrapping `repeat`, out-of-range durations/transitions rejected before any write; valid playlist stored and verified semantically; running playlist and member interference named | `tests/test_playlists.py` (valid save with one POST, dry run hazards, running-playlist refusal, overwrite snapshot, conflicts, schema bounds, member checks, timeout unknown, semantic mismatch, repeat wrap on restore) |
| A18-08 export of a mixed store: no device, address or credential data, verbatim objects, correct types, excluded entries named | `tests/test_bundles.py::test_export_*`, `::test_include_unwritable_exports_every_type_for_inspection` |
| A18-09 parser rejects unknown `format`, `format_version` 2 (named), unknown/duplicate keys, NaN, oversize, bad IDs with zero device I/O; retained v1 fixture parses | `tests/test_bundles.py::test_parser_rejects_*`, `::test_rejected_bundles_cause_zero_device_io`, `::test_retained_fixture_is_actual_export_output_and_parses` |
| A18-10 dry run onto fewer LEDs/segments, other catalog, matrix, occupied destinations: each mismatch, overwrite and mapping named; zero POSTs; no file | `tests/test_bundles.py::test_dry_run_*`, `::test_valid_dry_run_*`, explicit effect/catalog map, allocation, self-reference, malformed target store, segment stop boundary |
| A18-11 snapshots before the first POST, backup failure sends nothing, members before playlists, per-entry verification | `tests/test_bundles.py::test_snapshots_precede_the_first_post_and_members_precede_playlists`, backup failure, taken destination, retention-pruning protection, write-time playlist conflicts |
| A18-12 partial import: k-th write unreadable, entry k `unknown`, later `not_attempted`, no resend, earlier `backup_id`s returned | `tests/test_bundles.py::test_unreadable_kth_write_stops_the_import_without_any_resend`, `::test_first_entry_mismatch_and_later_conflict_outcomes` |
| A18-13 roundtrip into identical capabilities (state exact, playlist semantic) | `tests/test_bundles.py::test_roundtrip_export_import_reproduces_the_objects` |
| A18-14 transport parity | `tests/test_bundles.py::test_protocol_envelope_and_schema_errors_for_the_new_tools`; `tests/test_http_service.py`, `tests/test_http_cli.py` |
| A18-15 log privacy | `tests/test_bundles.py::test_logs_carry_no_bundle_content_names_or_addresses` |
| Registry and coverage | as in the first pull request |

Source facts for the bounds (pinned v16.0.1): `repeat` plus one pass is kept in a byte (0-254), a
transition is `tr x 100` in 16 bits (at most 655 tenths), `dur` is 0-42949670 tenths. Since saving
a playlist starts it and the route is refused while one runs (ISSUE-18-DEC-003), an import carries
at most one playlist.

Correction round 1 (review of `8f78ef7`, tests only): duplicate-key test on an otherwise valid
bundle, retention-pruning protection (`retain_per_device=1`, three overwrites), write-time playlist
checks, and planning branches (`id_map` allocation, self-reference, malformed store, catalog-map
bound, `stop` boundary) covered, each mutation-checked; docs updated (imported transition range,
custom palettes, scope of the address scan).

Hardware: not run. A check of playlist authoring and import needs its own human authorization
naming the controller and a captured baseline (DEC-021 "Hardware"); the outcome is pending.

Commands (Windows, 2026-11-08; CI in the PR): `pytest` 1420 passed, 20 skipped, same Windows-only 6
failures and 5 errors as `main`; the four preset test files 199 passed; ruff, strict mypy (32
files), traceability, coverage (44 % / 35 %), agent sync, agent setup, lock, private identifiers
pass; `check_distribution.py` as above.

## Issue #19 validation evidence

Evidence for [issue #19](https://github.com/descipar/wled-mcp/issues/19). Contract:
[contract/segments.md](../contract/segments.md). Requirements: S2-SEG-01, S2-SEG-02 and
S2-T05 of [STAGE-2.md](../STAGE-2.md); scenarios AC-19-01 to AC-19-18 of
[ISSUE-19-DEC-003](../decisions/stage-2.md#issue-19-dec-003--technical-defaults-for-the-capability-model-and-segment-fields).

Hardware honesty (AC-19-18): the only hardware evidence in this project is one RGB-only 1D
controller on WLED 16.0.1. Nothing below is a CCT, RGBW-new-range, 2D or overlap hardware claim;
those capabilities stay at the expected tier of DEC-020 (source-reviewed and mock-tested).

### First pull request: capability model and read side

Mock transport and pure functions only. The stateful fake `tests/layout_support.py` gained opt-in
WLED 16 shapes (`v16`, `matrix`, `buses`) from the v16.0.1 source pin; its default stays the stage-1
shape. All tests are in `tests/test_segment_capabilities.py` unless named otherwise.

| Scenario | Evidence |
| --- | --- |
| AC-19-01 per-segment evidence chain `state_lc` -> `info_seglc` -> `null`; RGB-only, RGBW, white-only, CCT bits; 0.15.1 info without `seg[].lc`; malformed `lc`; unknown never false; uniform bits | `test_state_lc_is_the_first_evidence_source`, `test_0_15_shape_without_seg_lc_falls_back_to_aligned_seglc`, `test_no_per_segment_evidence_is_unknown_not_false` and four more |
| AC-19-01 `capabilities.matrix` from `info.leds.matrix`, malformed `null` with a warning, 1D without a warning | `test_matrix_is_parsed_strictly`, `test_get_state_reports_v16_matrix_fields` and two more |
| AC-19-02 new segment fields from their wire keys, `null` when absent or malformed (with a warning), additive; state example equals the read model | `test_new_segment_fields_come_from_their_wire_keys`, `test_state_example_matches_the_read_model` (examples/contracts/state.json) and three more |
| AC-19-03 refactor parity: existing patch, layout, store, import and export suites pass unchanged; write side still uses `info.leds.seglc` only; `CAP_*` importable from readmodels | full `pytest` run; `test_bundle_module_uses_the_moved_parse_matrix`, `test_cap_constants_stay_importable_from_readmodels`; `tests/test_bundles.py` unchanged |
| WLED 16 fake: omitted Y kept, X/Y clamped, trailing strip bounds, capability recomputed after a move, option keys with firmware clamps | four `test_fake_*` tests |
| Coverage rows W-SEG-14 to W-SEG-22 partial (read only), W-INFO-02 | `tests/test_coverage.py`, `scripts/check_coverage.py` |

Not covered by the first pull request: every write-side scenario (AC-19-04 to AC-19-16) and
transport parity of new input fields (AC-19-15); they belong to the second pull request.

### Second pull request: segment writes

Mock transport and pure functions only. The fake now follows the v16.0.1 source more closely (name
cleared on the requested X bounds before clamping, `si`/`set` constrained to 0-3, `cct` applied by
every build, trailing-strip rows from `startY`/`stopY`); its own tests pin that. Carried review items
of PR #108 were done first: the write-side CCT lookup moved from `info.leds.seglc` to the
`seg[].lc` chain (pin flipped in `test_write_side_uses_the_seg_lc_chain_without_seglc`), surviving
mutants were killed by new tests, and examples/contracts/state.json is v16-shaped.

| Scenario | Evidence |
| --- | --- |
| AC-19-04 `cct` on a CCT segment: payload `{"id": N, "cct": X}`, readback equal, `applied/verified`; dry run identical with zero POSTs | `test_cct_patch_on_a_cct_segment_is_verified_and_the_dry_run_is_identical` |
| AC-19-05 `cct` on an RGB-only segment, aggregate-only, missing or misaligned evidence, or a moved range without uniform evidence: `UNSUPPORTED_CAPABILITY`, zero POSTs, whole request refused | `test_cct_without_evidence_is_unsupported_before_any_post` (5 cases x dry/live) |
| AC-19-06 white handling: existing RGBW unchanged, white-only takes `[0, 0, 0, W]`, RGB+CCT takes 3 channels, moved or new range takes 4 only under the uniform rule | `test_white_only_range_takes_four_channels_with_rgb_zero`, `test_moved_range_takes_four_channels_only_under_the_uniform_rule`; `tests/test_layouts.py::test_T06_rgbw_rules` (deliberately updated) and two more |
| AC-19-07 2D bounds on a matrix, omitted rows preserved, rows-only change keeps the name, any 2D field on a 1D device is `UNSUPPORTED_CAPABILITY` | `test_matrix_x_patch_keeps_rows_and_resends_the_name`, `test_2d_fields_on_a_1d_device_are_unsupported` and two more |
| AC-19-08 matrix gap closed (`stop` > width is `VALIDATION_ERROR` before any POST), rectangle overlap, explicit rows for a new replace segment, trailing strip preserved but never created or moved | `test_matrix_patch_bounds_are_refused_before_any_post`, `test_matrix_replace_uses_rectangles_and_preserves_the_trailing_strip` and two more |
| AC-19-09 orientation only on a matrix, verified | `test_matrix_orientation_patch_is_verified` |
| AC-19-10 option bounds before any write, field presence per segment and for a new ID on every active segment, readback verified | `test_option_bounds_are_schema_errors`, `test_option_without_its_wire_key_is_unsupported` (10 options x both tools) and three more |
| AC-19-11 overlap rejected by default in both tools, `allow_overlap` permits it, plan lists pairs and render order, dry run identical; `blend_mode` where reported | `test_patch_overlap_needs_allow_overlap_and_the_plan_lists_pairs`, `test_replace_overlap_with_blend_mode_and_render_order`; stage-1 rejection tests unchanged |
| AC-19-12 replace create defaults where the readback proves the field; `inherited_unexposed_state` lists only unreset keys | `test_replace_create_sends_the_wled_16_defaults`, `test_reused_slot_on_a_stage_1_device_lists_only_unreported_keys`; `tests/test_layouts.py::test_T05_fixture_case_exact_post_sequence_and_final_layout` (updated: `cct` 127 on create), regenerated examples |
| AC-19-13 a patch omitting new fields sends none; a geometry change resends the name, rows and orientation untouched | `test_omitted_new_fields_are_never_sent` |
| AC-19-14 uncertain and partial writes keep the stage-1 mappings without replay | `test_uncertain_cct_write_is_unknown_and_not_replayed`, `test_uncertain_matrix_replace_step_stops_the_sequence` and one more |
| AC-19-15 transport parity: identical additive schemas, T06 parity for every new field, tool list unchanged, retained 0.1.0 contract compatible without a migration note | `tests/test_layouts.py::test_new_input_fields_are_additive_and_identical_in_both_tools`, `tests/test_http_service.py::test_http_results_match_in_process_server`, `tests/test_upgrade_compat.py` |
| AC-19-16 `wled_store_preset` takes the wire keys with the same bounds and rules; overlap stays rejected | `test_store_accepts_wled_16_keys_with_evidence_and_stores_them_verbatim`, `test_store_refuses_wled_16_keys_without_evidence` (8 cases x dry/live), `test_store_has_no_allow_overlap` |
| AC-19-17 no version-based refusal below 16.0.0; no #19 rule reads the tier | `test_no_issue_19_rule_reads_the_firmware_tier` |
| AC-19-18 hardware honesty | This file: no CCT, RGBW-new-range, 2D or overlap hardware claim |
| Coverage W-SEG-13 to W-SEG-22 supported | docs/WLED-COVERAGE.md, `scripts/check_coverage.py --update` (57 % of the planned scope, 46 % overall) |

Stage-1 hardware evidence: the replace runs on the RGB-only test controller predate the extended
create payload. The 11 keys a create step may now add (`cct`, `c1`-`c3`, `o1`-`o3`, `si`, `set`,
`m12`, `bm`) rest on mock and source evidence only.

Review round 1 (b219017): the store no longer moves an existing trailing strip, the patch tool
accepts unchanged bounds on a trailing strip, and eight tests were added for surviving mutants
(overlap swap, rows-change counts as moved for CCT, unknown rows block a geometry change, all
overlapping pairs listed, store option on a new ID, and others).

Not covered: any hardware run. A read-only probe of the RGB-only test controller could confirm the
WLED 16 option keys and `seg[].lc` on real firmware; it needs separate authorization and is not
required by the issue.

## Issue #20 validation evidence

Evidence for [issue #20](https://github.com/descipar/wled-mcp/issues/20). Contracts:
[contract/profiles.md](../contract/profiles.md) and
[contract/diagnostics.md](../contract/diagnostics.md). Requirements: S2-ACCESS-01 to S2-ACCESS-03
and scenario S2-T02 of [STAGE-2.md](../STAGE-2.md); decisions
[ISSUE-20-DEC-001](../decisions/stage-2.md#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes)
(human) and
[ISSUE-20-DEC-002](../decisions/stage-2.md#issue-20-dec-002--technical-defaults-td-20-1-to-td-20-15)
(coordinator).

Hardware honesty: none claimed. Every test uses a mock transport or a synthetic loopback device on
`127.0.0.1`; no LAN device, physical lighting or deployed service was contacted.

### First pull request: profiles, device ceilings and guard layers

Scenario IDs T20-01 to T20-13. Tests are in `tests/test_access_profiles.py` unless named otherwise.

| Scenario | Evidence |
| --- | --- |
| T20-01 per profile, stdio and HTTP: `tools/list` equals `expected_names(profile)`, each tool byte-identical to the full list's | `test_tools_list_equals_the_profile_expectation_and_each_tool_is_unchanged`, installed-console tests for stdio and HTTP (three profiles each), `test_the_file_profile_applies_and_the_option_overrides_it` |
| T20-02 a direct `tools/call` of an excluded tool is the same `-32602` "Unknown tool" as a made-up name; zero device requests, both transports | `test_excluded_tool_is_an_unknown_tool_before_any_io` and the console tests |
| T20-03 SDK `get_tool_input_schema` is `None` for excluded tools | `test_sdk_schema_lookup_is_none_for_excluded_tools` |
| T20-04 G3 with test doubles: a `control` composite on a `read`-capped device through each engine and the import entry, a `read` operation attempting a write, a `manage` write on a `control`-capped device are `ACCESS_DENIED`, `not_attempted`, zero requests, guard before the device lock; ambient class visible in children and threads | `test_every_engine_refuses_before_the_lock_and_any_io`, `test_the_import_entry_refuses_before_parsing_or_any_io`, `test_the_ambient_class_is_set_per_call_visible_in_children_and_reset`, `test_every_engine_checks_access_as_its_first_statement` and five more |
| T20-05 class parity: production `Operation.tool_class` equals the contract class for all tools, both directions; a missing class fails at construction; a non-`ToolClass` value is refused by `create_server` | `test_production_classes_equal_the_contract_classes_in_both_directions`, `test_an_operation_without_a_class_cannot_be_constructed`, `test_create_server_refuses_a_class_that_is_not_a_tool_class` |
| T20-06 control/manage split pinned: literal name sets, `control` tools never send `psave`/`pdel` or write a file, `read` tools send no POST | `test_control_and_manage_name_sets_are_pinned`, `test_read_tools_send_no_post_and_write_nothing`, `test_control_tools_never_send_storage_commands_or_write_files` |
| T20-07 invalid `--profile`, `[access] profile` or `max_class`: exit 2 or `ConfigurationError`, fixed positional message, no value echo; precedence option, file, default; `--profile` with a subcommand is a usage error | `test_invalid_access_settings_are_positional_and_value_free`, `test_profile_precedence_is_option_then_file_then_full`, `test_no_environment_variable_selects_a_profile` and six more |
| T20-08 caps: G2 refuses every device-taking write tool above the cap before I/O including `dry_run`; reads stay allowed; effective class is the lower of profile and cap; unknown device keeps `UNKNOWN_DEVICE`; validation precedes G2 | `test_a_device_cap_refuses_every_higher_class_before_any_io_including_dry_run`, `test_the_effective_class_is_the_lower_of_profile_and_cap`, `test_the_cap_cases_cover_every_write_tool` and three more |
| T20-09 concurrent HTTP clients plus a parallel stdio process see the same list and refusals; the capped device receives no write | `test_concurrent_http_clients_and_a_stdio_process_see_the_same_list_and_refusals` (installed console, two loopback devices) |
| T20-10 configuration: retained 0.1.0 and shipped configurations validate unchanged; new keys accepted; unknown `[access]` key rejected value-free; `config validate`/`doctor` text unchanged without access settings; `add-device` keeps bytes; export carries only profile and class names | `test_access_settings_are_additive_and_optional`, `test_retained_and_shipped_configurations_are_unchanged_by_the_new_keys`, `tests/test_setup_cli.py`, `tests/test_doctor.py` (access cases) |
| T20-11 `tests/test_upgrade_compat.py` and migration-note parsing pass without edits | `tests/test_upgrade_compat.py` (unedited) |
| T20-12 structural: `post_state` referenced only from the client, `resources.py` and `bundle_tools.py` | `test_post_state_is_referenced_only_by_the_engines_and_the_import_path` |
| T20-13 restricted-profile smoke against the installed wheel | `scripts/check_distribution.py` (`restricted_handshake`) |
| Startup event: one INFO line with transport, profile and number of capped devices | `test_serve_passes_the_policy_to_create_server_and_logs_one_startup_event`, `test_serve_http_passes_the_policy_to_create_server_and_logs_the_event` |

Implementer mutation spot checks (not a substitute for review): G2 disabled, registry filter
inverted, ambient default lowered, `read` ambient refusal removed, import-entry guard removed,
`lower` returning the higher class and the guard removed from `write_sequence_verified` each fail at
least one test.

### Second pull request: correlation ID, bounded logs and the status tool

Contract: [contract/diagnostics.md](../contract/diagnostics.md). Requirement S2-ACCESS-03 (with
OPS-03 and OPS-05). Scenario IDs T20-14 to T20-17. Tests are in `tests/test_diagnostics.py` unless
named otherwise.

| Scenario | Evidence |
| --- | --- |
| T20-14 a correlation ID on every served envelope (ok, domain error, validation error, `ACCESS_DENIED`, refused `dry_run`), unique per call, never client-chosen, appended to the `-32603` message, absent from direct `execute` dumps, not in the output schema's `required` list; parity tests strip it through one helper | `test_every_served_envelope_carries_a_unique_server_generated_id`, `test_a_client_cannot_choose_the_id`, `test_the_id_is_optional_in_the_schema_and_absent_from_unserved_dumps`, `test_an_internal_failure_names_the_id_and_nothing_else` and three more; helper `tests/envelopes.py`; `tests/test_upgrade_compat.py` unedited |
| T20-15 logs: only allowlisted fields; planted argument values, URLs, header and credential strings absent; line bound; unknown tool name not logged; level and JSON format; stdout untouched on stdio; default level silent on success | `test_a_call_line_has_only_allowlisted_fields_and_no_planted_value`, `test_lines_stay_within_the_bound_in_both_formats`, `test_the_default_level_is_silent_on_success_and_reports_failures`, `test_the_stdio_console_keeps_stdout_clean_at_info_level`, `test_the_http_console_logs_one_bounded_json_line_per_call` and eight more |
| Startup event visible with `WLED_MCP_LOG_LEVEL=info`, silent at the default | `test_the_startup_event_is_visible_only_when_the_level_allows_it` |
| T20-16 status tool: zero requests and file writes; unobserved device `unknown`; failed read shows code and age; good read `reachable`; polling never changes an age; present in all three profiles; no URL, host, path or credential in `data`; read class; counters bounded | `test_the_status_tool_is_listed_in_every_profile_and_sends_nothing`, `test_an_unobserved_device_is_unknown_never_healthy`, `test_polling_the_status_never_refreshes_an_observation_or_sends_a_request`, `test_the_status_data_names_no_url_host_path_or_credential` and eight more; `tests/test_tool_contract.py`, `tests/test_readme.py`, `scripts/check_coverage.py` |
| T20-17 no outbound connection besides configured device requests during a full tool pass; liveness unchanged and device-free | `test_a_full_tool_pass_opens_no_connection_besides_the_configured_devices`, `test_nothing_runs_in_the_background_between_calls`; existing `tests/test_http_service.py` and `tests/test_http_cli.py` |
| TD-20-12 rotation and tenancy statements | `test_the_contract_states_restart_based_rotation_and_no_tenancy` |

Mutation spot checks (implementer): 12 mutations (serializer, ID source, level filter, monitor
observing a rejected address, unobserved reported reachable, status tool sending a request, log
handler on stdout, and others) all killed; six more after correction round 1, all killed.

Boundaries: the status tool and observer are proven against a mock transport and synthetic loopback
devices only. What a real controller returns after a power loss, Wi-Fi roam or captive portal is not
exercised; readiness states describe only what this process observed. No hardware evidence is
claimed for #20.

### Commands and not covered

Commands and results are in the pull request description. `scripts/check_distribution.py` fails
locally at its uvx handshake when the working directory path contains a space; the restricted-profile
handshake before it and the setup and HTTP smoke steps ran. `wled_apply_scene` of #17 is not part of
this work: the guard layers are tested with test-double composites using the same engines and
`Resources.require_access`.
