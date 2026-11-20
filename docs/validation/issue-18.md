# Issue #18 validation evidence

Evidence for [issue #18](https://github.com/descipar/wled-mcp/issues/18). Contract:
[contract/presets.md](../contract/presets.md). Requirements: PRE-03, PRE-04 (restore execution),
PLAY-01 and S2-PRESET-01 to -03 of [STAGE-2.md](../STAGE-2.md).

Mock transport and `tmp_path` only; no LAN, device or hardware access. The stateful fakes
(`tests/preset_support.py`, `tests/bundle_support.py`) model the WLED v16.0.1 write routes recorded
in [SOURCES.md](../SOURCES.md#issue-18-wled-16-preset-write-evidence) (firmware set explicitly).
Nothing here is hardware acceptance.

## First pull request: restore, supplied-state save, snapshot listing

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

## Second pull request: playlist authoring, bundle export and import

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
