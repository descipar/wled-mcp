# Issue #17 validation: device groups, scenes, plan, apply and sharing

Evidence for [#17](https://github.com/descipar/wled-mcp/issues/17); contract in
[contract/groups-scenes.md](../contract/groups-scenes.md), decisions in
[ISSUE-17-DEC-001 and -002](../decisions/issue-17.md). Pull request A (definitions, store,
sharing, `wled_plan_scene`) and pull request B (`wled_apply_scene`, executor, policy, aggregate
outcome) are covered.

**All evidence is mock evidence.** The fleet is `tests/scene_support.py` (several stateful
`FakeWLED` devices behind one router with failure injections, request log and in-flight gauges);
console tests use the loopback fake of `tests/acceptance_support.py`. Stores use `tmp_path`. No
LAN device or hardware was used; no multi-device or synchronization behavior of real controllers
is claimed.

## Scenario to test map

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

## Carried items of the pull request A review

| Item | Evidence |
| --- | --- |
| Store-level ID check is the refusal (mutant M16) | `tests/test_scene_store.py` `test_the_store_id_check_is_the_refusal_not_a_missing_file` |
| Windows device names are not group or scene IDs | `test_windows_device_names_are_not_usable_ids`, `test_names_that_only_resemble_a_device_name_stay_valid` |
| One store lock per directory | `test_two_store_instances_over_one_directory_cannot_create_the_same_id` |
| Leak check scans every exported string | `tests/test_scenes.py` and `tests/test_scene_tools.py` export-scan tests |
| `bundles.py` uses the shared `format_version` helper | `tests/test_bundles.py` unchanged and passing |
| Doc corrections (`DESTRUCTIVE` comment, segment `effect_name`/`palette_name` wording) | `docs/TOOL-CONTRACT.md` |

## Reading choices

Choices where the packet or the technical defaults leave room.

### Reading choices (pull request B)

1. A device that is "unknown" aggregates as `application=unknown` (`unknown/unknown` +
   `WRITE_OUTCOME_UNKNOWN`, TD-17-10); device entries keep the exact verification.
2. `wled_apply_scene dry_run=true` includes the per-device `control` ceiling check; the read-class
   `wled_plan_scene` does not. Otherwise identical.
3. A proven master step followed by a segment step refused before sending is `applied/mismatch`.
4. Master and segments are two `write_verified` calls; another writer can interleave between them.
5. An aggregate that wrote nothing returns the first refusal in expansion order, device named.
6. A stopped call returns no result; the contract states untouched versus uncertain devices.
7. The apply annotations are a local constant in `scene_tools.py` (`operations.py` imports it).

### Reading choices (pull request A)

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

## Commands run

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

## Known limits

- Mock evidence only; no multi-device or synchronization behavior of real controllers is claimed
  and hardware acceptance of #17 is not part of this evidence. A single-controller scene smoke
  needs its own authorization.
- Several server processes on one data directory are not coordinated.
- Plan results are a snapshot; the apply plans again under each device lock.
- A stopped call leaves unstarted devices untouched and in-flight writes uncertain; the HTTP drain
  (operation timeout plus two seconds) is shorter than a 16-device scene can take.
- Master and segments of one device are two write operations.
- Directory-symlink and POSIX permission tests run only on POSIX hosts (CI).
