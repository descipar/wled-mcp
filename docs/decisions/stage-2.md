# Decisions: stage 2 (issues #16 to #25)

## Issue #16 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

### ISSUE-16-DEC-001 — Inventory reload and discovery surface

- ID: ISSUE-16-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #16; superseded in part by DEC-035 (2026-11-12): the "restart
  instead of reload" half of Q1 and the "CLI only, not an MCP tool, never writes the
  inventory" half of Q2 no longer hold from M8. The validate-then-restart procedure for hand
  edits and the `wled-mcp discover` command stay valid.
- Authority: human decision (repository owner), coordinator session, 2026-11-07, answering
  Q1, Q2 of DEC-021: "alles nach empfehlung" (English: "everything as recommended").
- Scope: issue #16 (S2-SETUP-02, DEV-03 remainder of ISSUE-13-DEC-001).
- Decision:
  - Q1 A: inventory changes use `wled-mcp config validate` followed by the documented
    restart; in-process reload is not part of stage 2 (the ISSUE-13-DEC-001 deferral is
    closed as "not needed").
  - Q2 A: discovery is a CLI-only `wled-mcp discover` using the standard library (one-shot
    mDNS query, no new dependency); it reports candidates and prints the enrollment command,
    is not an MCP tool and never writes the inventory.
- Conditions: discovery runs only on explicit CLI invocation; WLED mDNS service type and TXT
  fields are verified against the pinned source in docs/SOURCES.md.
- Supersedes / superseded by: closes the reload deferral of ISSUE-13-DEC-001; superseded in
  part by DEC-035.

### ISSUE-16-DEC-002 — Technical defaults TD-16-1 to TD-16-10

- ID: ISSUE-16-DEC-002
- Recorded date: 2026-11-08
- Status: active for issue #16; TD-16-8 superseded in part by DEC-035 (2026-11-12): "no
  unicast probes" and the CLI-only engine no longer hold from M8 (the engine becomes the
  shared one of #199).
- Authority: technical proposal accepted by the coordinator (not a human decision; the owner
  can override any part).
- Source: TD-16-1 to TD-16-10 and two coordinator choices of the issue-16 packet, accepted
  2026-11-08.
- Scope: issue #16 (S2-SETUP-01 to -03, DEV-03, OPS-04 remainders). Contract text:
  docs/contract/cli.md.
- Decision:
  - TD-16-1 CLI shape: `cli.build_parser()`; no subcommand = serve; subcommands
    `config init|add-device|validate`, `doctor`, `discover` (second PR); `--format
    text|json`; exit codes 0 ok, 1 problem, 2 usage, 3 internal; JSON has `schema_version` 1
    and `command`.
  - TD-16-2 Absolute `--config`/`--data-dir` (or environment) only; no default lookup.
  - TD-16-3 `config init` writes only the selected file; `config add-device` appends one
    `[[devices]]` block textually, validates the result with the startup validator, rejects
    an equal normalized `base_url` and writes atomically, aborting if the file changed;
    0600 on POSIX; no token generation, no device contact.
  - TD-16-4 `config validate` shares `validate_document` with startup; never contacts devices.
  - TD-16-5 Read-only `doctor` (runtime, configuration, storage, device, optional endpoint
    checks); device checks via the in-process `wled_get_state` envelope and
    `compat.support_warning`.
  - TD-16-6 Sanitized `doctor --export` from an allowlist.
  - TD-16-7 OPS-04 remainder: doctor covers every listed condition; serve prints one advisory
    stderr line when the backups location is not writable and still starts.
  - TD-16-8 Discovery (second PR): standard-library one-shot IPv4 mDNS query, bounded
    window and candidate cap, never automatic.
  - TD-16-9 Docs in `docs/contract/cli.md` and `docs/validation/stage-2-core.md`.
  - TD-16-10 Two PRs; no new dependency.
  - Coordinator choices: no no-op `config migrate`; no `--create-data-dir`; #20 starts after
    the second #16 PR.
- Conditions: while #16 is open; deviations go back to the coordinator.
- Supersedes / superseded by: none (TD-16-8 in part by DEC-035, see Status).

## Issue #17 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-08.

### ISSUE-17-DEC-001 — Storage of groups and scenes, default failure policy

- ID: ISSUE-17-DEC-001
- Recorded date: 2026-11-08
- Status: active for issue #17.
- Authority: human decision (repository owner), coordinator session, 2026-11-08, answering
  OD-17-1 and OD-17-2: "A und A" (English: "A and A").
- Scope: issue #17 (named device groups and reusable multi-device scenes), both PRs.
- Decision:
  - OD-17-1, option A: groups and scenes are local JSON documents under
    `<data-dir>/groups/` and `<data-dir>/scenes/`, written by `manage`-class tools and
    read by `read` tools; the inventory file is untouched.
  - OD-17-2, option A: the default failure policy is `strict` (nothing is written if any
    target fails preflight); `best_effort` is an explicit opt-in.
- Conditions: until a later owner decision; PR A only plans, PR B's apply tool applies the
  policy default.
- Supersedes / superseded by: none.

### ISSUE-17-DEC-002 — Technical defaults TD-17-1 to TD-17-18 and coordinator choice C-17-1

- ID: ISSUE-17-DEC-002
- Recorded date: 2026-11-08
- Status: active for issue #17 (both pull requests).
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: requirements packet (TD-17-1 to TD-17-18, AC-17-01 to AC-17-14), coordinator
  session, 2026-11-08.
- Scope: issue #17 only; applies ISSUE-17-DEC-001, ISSUE-20-DEC-001 (tool classes),
  ISSUE-98-DEC-001 and ISSUE-21-DEC-002 TD-21-5. Contract text: docs/contract/groups-scenes.md.
- Decision:
  - C-17-1 Issue #17 starts now; the class classification of ISSUE-20-DEC-001 satisfies the
    DEC-021 dependency "profile classes", #20 enforcement is not a prerequisite.
  - TD-17-1 Two PRs: A (groups, scene format and store, sharing, `wled_plan_scene`; reads
    only) and B (`wled_apply_scene`, the only device-write path).
  - TD-17-2 Tools: `wled_list_groups` (read), `wled_save_group`/`wled_delete_group`
    (manage, destructive), `wled_list_scenes` (read), `wled_save_scene`/`wled_delete_scene`
    (manage, destructive), `wled_plan_scene` (read, so a read-only profile can preview); PR
    B adds `wled_apply_scene` (control). List tools return the full document by optional ID.
  - TD-17-3 One strict JSON document per item (`groups/<id>.json`, `scenes/<id>.json`),
    0700 directories and 0600 files, at most 64 KiB per document, 100 groups, 500 scenes,
    atomic replace, symlinks refused, bad or newer-version files counted and never
    rewritten. Replacing needs `overwrite=true`; save and delete take `dry_run`.
  - TD-17-4 Group: `format` `wled-mcp.group`, integer `format_version` 1, 1-16 members
    `{device, segments?}` with unique explicit segment IDs 0-254; members are rechecked
    against the inventory at every expansion.
  - TD-17-5 Scene: `format` `wled-mcp.scene`, integer `format_version` 1, 1-16 targets of
    exactly one `device` or `group` with `master` and/or `segments` (allowlisted fields of
    the existing planners; no geometry, names, `selected`, `freeze`, `blend_mode`, raw state).
  - TD-17-6 `effect_name`/`palette_name` resolve per device (exact, then unique
    case-folded); ambiguity is `AMBIGUOUS_NAME`; numeric IDs are used as given with a warning.
  - TD-17-7 Expansion in document order; a device appearing twice after expansion refuses
    the request before any I/O.
  - TD-17-8 The plan reads fresh state under the per-device lock, at most 4 devices in
    flight, with the real planners; not a reservation.
  - TD-17-9 Policy `strict` (default) or `best_effort`; 4 devices in flight, 16 per request;
    master step before segment step.
  - TD-17-10 Aggregate envelope without new application or verification values; one
    additive error code `STORAGE_FAILED`.
  - TD-17-11 No new write engine and no scene-level lock (PR B).
  - TD-17-12 Sharing: export through `wled_list_scenes` replaces device and group
    references by positional placeholders (`include_targets=true` keeps them); free text with
    an inventory host token blocks the export; `wled_save_scene` maps placeholders through
    `target_map`, all or nothing.
  - TD-17-13 Versioning follows TD-21-5 with one shared helper.
  - TD-17-14 Coverage: new tools listed under "Tools without a WLED feature row"; notes of
    W-SEG-05 and W-SEG-07 corrected (only numeric IDs accepted by segment tools).
  - TD-17-15 Docs in docs/contract/groups-scenes.md and docs/validation/stage-2-core.md;
    example `examples/contracts/scene.json`.
  - TD-17-16 (as amended) Tool classes are declared in `tests/tool_contract.py` and on the
    `Operation` (`tool_class`). The access guard lives in the write engines of `Resources`,
    not in `Resources.operation`; `wled_apply_scene` reaches every device through
    `Resources.write_verified` and its preflight calls `Resources.require_access` once per
    expanded device; `tool_class=ToolClass.CONTROL`.
  - TD-17-17 No firmware gating; capability evidence from fresh readbacks.
  - TD-17-18 Review depth is full (DEC-022 item 3).
- Conditions: until a later decision. Reading choices:
  [PR A](../validation/stage-2-core.md#reading-choices),
  [PR B](../validation/stage-2-core.md#reading-choices-pull-request-b).
- Supersedes / superseded by: none.
- Amendment 1 (with PR B; technical proposal accepted by the coordinator after the review of
  PR A; changes only these points):
  1. A not-configured device (direct target or group member) is a per-device
     `UNKNOWN_DEVICE` preflight failure at plan and apply, with no I/O: `strict` blocks all,
     `best_effort` skips it. Unknown group, duplicate device, device/patch limits and an
     entry without `ids` refuse the whole request. Saving a scene refuses an unconfigured
     directly named device.
  2. TD-17-16 as amended above.
  3. The leak check of a shareable export scans every exported string value, not only
     `name` and `description` ([groups-scenes.md](../contract/groups-scenes.md#sharing)).
  4. Group and scene IDs may not be Windows device names; the store lock is per directory.

## Issue #18 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

### ISSUE-18-DEC-001 — Write route for supplied preset and playlist objects

- ID: ISSUE-18-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #18.
- Authority: human decision (repository owner), coordinator session, 2026-11-07, answering
  OD-18-1 of DEC-021: "alles nach empfehlung" (English: "everything as recommended").
- Scope: issue #18 restore, supplied-state save, import and playlist authoring on WLED 16.
- Decision: option A. Supplied objects are written through the JSON API one entry at a
  time with an explicit, documented live effect: state objects use the firmware's
  immediate verbatim write path (applied to the lights, then stored exactly); playlists use
  the native playlist save (the playlist starts playing and is stored firmware-normalized).
  Tool descriptions and the dry run state this effect; there is no automatic return to the
  previous lighting. The storage-only PRE-03 variant is declared unsupported on WLED 16.
- Conditions: supported firmware (DEC-020); each write takes a snapshot first and verifies
  by readback; whole-file `/presets.json` upload stays excluded (PRE-04).
- Supersedes / superseded by: none.

### ISSUE-18-DEC-002 — Capability-model owner

- ID: ISSUE-18-DEC-002
- Recorded date: 2026-11-07
- Status: active for issues #18 and #19.
- Authority: coordinator decision (integration owner under DEC-021); the owner did not
  object when it was announced.
- Scope: shared capability model between #18 and #19 (OD-18-2, D-19-1).
- Decision: #19 owns `src/wled_mcp/capabilities.py`. #18 does not depend on it; it uses
  the fields of the existing read models and an interim rule for raw matrix data.
- Conditions: Track B order (#18 before #19); if #18 needs the module, the coordinator
  revisits this entry instead of duplicating logic.
- Supersedes / superseded by: none.

### ISSUE-18-DEC-003 — Technical defaults for restore, supplied-state save and bundles

- ID: ISSUE-18-DEC-003
- Recorded date: 2026-11-07
- Status: active for issue #18.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: refreshed requirements packet, coordinator session, 2026-11-07; playlist-restore
  item amended the same day after the independent review (correction round 1).
- Scope: issue #18 only (both PRs). Contract text: docs/contract/presets.md.
- Decision:
  - No firmware-version gate (DEC-020, "warns, does not refuse"); below 16.0.0 tools run and
    rely on readback verification (the warning is #21's mechanism).
  - Restore needs the exact `device_id` and firmware `version` of the snapshot
    (ISSUE-8-DEC-003). Default target is the snapshot's preset ID; an occupied destination
    needs `overwrite=true` and the restore takes its own snapshot first.
  - Tools after `wled_delete_preset`, with ISSUE-20-DEC-001 classes: `wled_list_snapshots`
    (read), `wled_restore_preset` (manage, destructive), `wled_store_preset` (manage,
    destructive; `wled_save_preset` keeps no `state` input); PR B: `wled_save_playlist`
    (manage, destructive), `wled_export_presets` (read), `wled_import_presets` (manage,
    destructive).
  - Coverage: PR A W-PRESET-08 supported, W-PRESET-09 partial; PR B W-PRESET-09 supported,
    export/import added to W-PRESET-01, -07, -08.
  - Playlist restore (amended): a finite `repeat` and shuffle `r` are accepted and checked
    by semantic readback; `end = 255` and negative `repeat` stay refused. While `state.pl`
    > 0 (planning and recheck after the snapshot) the playlist route is refused with
    `PRESET_CONFLICT` without a POST; the source snapshot is protected from pruning.
  - PR B: playlist authoring refuses `end = 255` and negative `repeat`, `shuffle` is
    explicit; export selects `state` and `playlist` entries by default (others only with
    `include_unwritable=true`, never importable); bundles are inline, rejected above 192 KiB
    before any device I/O; at most 50 entries per import; lowest free ID 1-250 in bundle
    order without `id_map`; no LED-range or matrix conversion; snapshots before the first
    write; stop at the first failed, mismatched or unknown entry.
- Conditions: the bundle `format_version` follows TD-21-5 (ISSUE-21-DEC-002); #19 takes over
  the interim matrix rule with the capability module.
- Supersedes / superseded by: none.

## Issue #19 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07. The capability-model
owner is recorded as [ISSUE-18-DEC-002](#issue-18-dec-002--capability-model-owner).

### ISSUE-19-DEC-001 — Overlapping segments

- ID: ISSUE-19-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #19.
- Authority: human decision (repository owner), coordinator session, 2026-11-07, answering
  the Phase-0 questions of DEC-021 (D-19-2): "alles nach empfehlung" (English: "everything
  as recommended").
- Scope: `wled_patch_segments` and `wled_replace_layout` overlap handling.
- Decision: option B. Overlap stays rejected by default. An explicit request flag
  `allow_overlap=true` in both tools permits it; the plan lists every overlapping pair and
  the render order (higher slot on top), and `blend_mode` (0-16) becomes settable.
- Conditions: supported firmware (DEC-020); `blend_mode` settable only where the device
  reports the field.
- Supersedes / superseded by: extends the stage-1 overlap rejection with an opt-in.

### ISSUE-19-DEC-002 — Segment features not exposed

- ID: ISSUE-19-DEC-002
- Recorded date: 2026-11-07
- Status: active for issue #19 and the coverage list (#94).
- Authority: human decision (repository owner), coordinator session, 2026-11-07, on the
  exclusions proposed in TD-19-8: "ja, merge #96 und alles nach empfehlung" (English: "yes,
  merge #96 and everything as recommended").
- Scope: segment features of the WLED JSON API that the segment tools do not expose.
- Decision: not exposed are segment repetition `rpt`, the effect-defaults flag `fxdef` and
  matrix/panel configuration through `/json/cfg`. Individual LED control `i` stays excluded
  by ISSUE-13-DEC-001 (SEG-06). Alias and alternative encodings (`len`, the Loxone
  `lx`/`ly` build option, non-array color forms) are not separate features.
- Conditions: issue #19 and later stages until a new decision.
- Supersedes / superseded by: none.

### ISSUE-19-DEC-003 — Technical defaults for the capability model and segment fields

- ID: ISSUE-19-DEC-003
- Recorded date: 2026-11-08
- Status: active for issue #19 (both pull requests).
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: refreshed requirements packet (TD-19-1 to TD-19-14, AC-19-01 to AC-19-18),
  coordinator session, 2026-11-08.
- Scope: issue #19 only; applies ISSUE-19-DEC-001/-002 and ISSUE-18-DEC-002.
- Decision (contract text in docs/contract/segments.md):
  - TD-19-1 No new tool; additive input fields on `SegmentPatch`, `LayoutSegment`,
    `SuppliedSegment`, output fields on the `wled_get_state` segment view and `capabilities`.
  - TD-19-2 Public names and wire keys: `cct`, `start_y`/`stop_y` (`startY`/`stopY`),
    `reverse_y` (`rY`), `mirror_y` (`mY`), `transpose` (`tp`), `map_1d_2d` (`m12`, 0-4),
    `custom1`-`custom3` (`c1`-`c3`; 0-255, 0-255, 0-31), `check1`-`check3` (`o1`-`o3`),
    `sound_simulation` (`si`, 0-3), `segment_set` (`set`, 0-3), `freeze` (`frz`),
    `blend_mode` (`bm`, 0-16), request-level `allow_overlap` (default false).
  - TD-19-3 Per-segment capability evidence: `state.seg[].lc`, else the position-aligned
    `info.leds.seglc` entry, else none; CCT is bit 0x04; never by product name or firmware.
  - TD-19-4 New or moved ranges: `info.leds.lc` is an integer, every active segment's
    capability equals it and has the required bits; otherwise `UNSUPPORTED_CAPABILITY`.
  - TD-19-5 An option field is settable only when the target segment's fresh readback
    carries its wire key; 2D fields need `info.leds.matrix` with integer `w`, `h` >= 1.
  - TD-19-6 Replace create defaults where evidence exists (`cct` 127, `custom1`/`custom2`
    128, `custom3` 16, others 0/false); on a matrix a new segment needs explicit
    `start_y`/`stop_y`.
  - TD-19-7 Matrix geometry: X against width, Y against height; a trailing strip range is
    read and preserved, creating or moving one is `UNSUPPORTED_CAPABILITY`.
  - TD-19-8 Plan and dry run carry `capability_evidence` per field and, with
    `allow_overlap`, `overlaps` and `render_order`; `freeze=true` warns that master power-on
    unfreezes all segments.
  - TD-19-9 `src/wled_mcp/capabilities.py` is pure and network-free (`parse_matrix`,
    `SegmentCapability`, `DeviceCapabilities`, `derive_capabilities`, color helpers); no
    firmware tiering.
  - TD-19-10 Bundles: no behavior change beyond sourcing matrix and CCT bit from
    capabilities.py; `format_version` unchanged.
  - TD-19-11 Coverage: W-SEG-14..22 planned to partial (PR A), W-SEG-13..22 to supported
    (PR B); W-INFO-02 lists `leds.matrix` and `seg[].lc`.
  - TD-19-12 `wled_store_preset` gains the new wire keys in PR B under the same rules;
    overlap stays rejected there.
  - TD-19-13 Contract text in docs/contract/segments.md, evidence in
    docs/validation/stage-2-core.md.
  - TD-19-14 Two pull requests: A (capability model and read side, no write change) and B
    (all write-side changes).
  - Coordinator choices: C-19-1 extend `wled_store_preset` in PR B; C-19-2 two PRs; C-19-3
    start on `main` and merge `main` after #105.
- Conditions: supported firmware (DEC-020); the firmware tier of #21 is not read by any #19
  rule (TD-21-6).
- Supersedes / superseded by: extends ISSUE-6-DEC-003 (see S-2); ISSUE-18-DEC-003's
  interim raw-matrix rule is now served by capabilities.py.
- Amendment (2026-11-08, full review of PR B; coordinator, not a human decision):
  - S-1 `blend_mode` is settable without `allow_overlap`, with field presence only (a
    coordinator reading of ISSUE-19-DEC-001, to be confirmed with the owner at the next
    DEC-022 revalidation).
  - S-2 TD-19-3 extends the ISSUE-6-DEC-003 evidence source from `/json/info` `leds.seglc`
    to `/json/state` `seg[].lc` (read-only); the aggregate fallback for an existing
    unchanged range is kept.
  - (a) A new range keeps the stage-1 RGB-only rule of ISSUE-7-DEC-004 beside TD-19-4.
  - (b) `capability_evidence` appears only when a #19 field is supplied; no colors.
  - (d) In `wled_store_preset` an existing ID with unchanged X and rows uses its own
    evidence, other entries the uniform rule; an existing trailing strip is never moved.
  - N-3 The store's color width keeps the stage-1 aggregate `info.leds.lc` rule.
  - (f) Unapplied or uncertain writes keep the stage-1 outcome mappings (`unknown/mismatch`,
    `applied/mismatch`, `unknown/unknown` with `WRITE_OUTCOME_UNKNOWN`).
  - N-4 A carried nit edit of tests/test_upgrade_compat.py outside the path list was
    coordinator-assigned.

## Issue #20 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

### ISSUE-20-DEC-001 — Default profile, device restrictions, status surface, classes

- ID: ISSUE-20-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #20.
- Authority: human decision (repository owner), coordinator session, 2026-11-07, answering
  Q1-Q3 of DEC-021: "alles nach empfehlung" (English: "everything as recommended").
- Scope: issue #20 (S2-ACCESS) and the tool classification used by every tool-adding issue.
- Decision:
  - Q1 (a): with no profile configured the profile is `full`; restriction is opt-in, and
    README/quickstart show how to choose `read-only` or `control`.
  - Q2 (a): device restrictions are a per-device maximum class in the inventory; the
    effective class is the lower of the process profile and the device cap; a call above it
    is refused before any device I/O.
  - Q3 (a): no unauthenticated health route (ISSUE-14-DEC-004 stays); liveness is a TCP
    connect or authenticated `ping`; status is a read-class tool (`wled_get_service_status`)
    in both transports.
  - Confirmations: class vocabulary `read`, `control`, `manage`, with `wled_replace_layout`
    as `control` (D1); no per-credential scopes in #20 (D3); correlation ID as an envelope
    field (D8).
- Conditions: issues #17-#19 classify each new tool with this vocabulary.
- Supersedes / superseded by: none.

### ISSUE-20-DEC-002 — Technical defaults TD-20-1 to TD-20-15

- ID: ISSUE-20-DEC-002
- Recorded date: 2026-11-08
- Status: active for issue #20.
- Authority: technical proposal accepted by the coordinator (not a human decision; the owner
  can override any part).
- Source: TD-20-1 to TD-20-15 and C-20-1 of the issue-20 packet, accepted 2026-11-08; cites
  [ISSUE-20-DEC-001](#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes),
  which it does not change.
- Scope: issue #20. Contract text: docs/contract/profiles.md.
- Decision:
  - TD-20-1 Vocabulary and cumulative profiles: `read` (no live, storage or local file
    mutation), `control` (live output only), `manage` (device storage or local persistent
    artifacts); `read-only` = {read}, `control` = {read, control}, `full` = all. Production
    table `src/wled_mcp/access.py`; a test compares it with the test helper's copy.
  - TD-20-2 (D2) A tool's class is the maximum over all argument combinations; `dry_run`
    does not lower it.
  - TD-20-3 (D7) `Operation.tool_class` is a required keyword.
  - TD-20-4 `create_server(operations, access=None)`; `None` means `full`; a disabled tool is
    indistinguishable from an unknown one.
  - TD-20-5 (D4) Three guard layers: G1 registration filter; G2 dispatch-time device ceiling
    after schema validation; G3 entry guard of the write engines and preset-import path via
    an ambient `ContextVar`, before the device lock and any I/O. `Resources.require_access`
    is public for composite preflights.
  - TD-20-6 Additive error code `ACCESS_DENIED`, fixed message naming only device ID and
    class names, `not_attempted`/`not_requested`.
  - TD-20-7 Config (additive, `schema_version` 1): `[access] profile`, per-device
    `max_class`; `--profile` overrides the file; no environment variable.
  - TD-20-8 `config validate` and `doctor` unchanged without access settings; with them one
    extra line and additive JSON fields.
  - TD-20-9 to TD-20-12 (PR B) correlation ID, bounded structured stderr logging, read-class
    `wled_get_service_status` without device I/O, unchanged liveness/rotation with a "not
    tenancy" statement.
  - TD-20-13 Two PRs: A enforcement, B diagnostics and status. TD-20-14 Full review depth.
  - TD-20-15 #67 stays out; the filter is applied once in `create_server`.
  - C-20-1 The migration-note table of `docs/contract/versioning.md` gets two rows
    (`/access`, `/devices/max_class`) with provisional release `0.2.0`; #25 corrects the
    number if the release differs.
- Conditions: while #20 is open; deviations go back to the coordinator.
- Supersedes / superseded by: none. ISSUE-14-DEC-004 stays.

## Issue #21 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

### ISSUE-21-DEC-001 — Update and rollback evidence

- ID: ISSUE-21-DEC-001
- Recorded date: 2026-11-07
- Status: active for issues #21 and #25.
- Authority/source: human decision, owner answer in the coordinator session, 2026-11-07, to the
  Phase-0 questions of the stage-2 plan (DEC-021): "alles nach empfehlung" (English: "everything
  as recommended"); no permalink.
- Scope: closure evidence for S2-COMPAT-03 (version-to-version update and rollback, HTTP and
  uvx/stdio).
- Decision: #21 closes on automated upgrade/rollback tests plus the documented procedure. The
  live update/rollback run on the deployed target is evidence for #25 (S2-LAUNCH-01), performed
  once with the published artifacts.
- Conditions: the live run needs its own operation authorization when #25 reaches it.

### ISSUE-21-DEC-002 — Technical defaults TD-21-1 to TD-21-10

- ID: ISSUE-21-DEC-002
- Recorded date: 2026-11-07
- Status: active for issue #21 (with #70, absorbed per DEC-021); technical proposal accepted by
  the coordinator (refresh 2 of the packet, main `96c1842`), not a human decision; the owner can
  override any part.
- Scope: #21 and #70. TD-21-5 is design input for #16, #17 and #18, not a global rule.
- Decision:
  - TD-21-1 one version source, static `project.version`; runtime via `importlib.metadata`;
    scripts, image files, examples and tests derive it.
  - TD-21-2 release versions `MAJOR.MINOR.PATCH` (optional `rcN`); PEP 440 string, OCI tag,
    registry version and git tag `v<version>` identical apart from the `v`.
  - TD-21-3 non-release builds `<base>+g<12hex>[.dirty]`, image tag `+` mapped to `-`, staged
    by `stage_release.py --non-release` from `git archive`; no tracked-file edit.
  - TD-21-4 contract evolution rules within `0.x`; retained 0.1.0 `tools/list` snapshot test
    reusing `tests/tool_contract.py`, with a migration-note allowlist.
  - TD-21-5 integer schema versions; readers reject higher/unknown versions naming them;
    migrations in memory; config and snapshot files never rewritten by the server.
  - TD-21-6 firmware classifier `src/wled_mcp/compat.py` (floor 16.0.0; tested {16.0.1};
    expected empty) in `wled_get_state.data.diagnostics.firmware_support`; warning only.
  - TD-21-7 keep the 0.15.x baseline handling; reword "pinned v0.15.1"; default fixtures 16.x.
  - TD-21-8 native arm64 CI (`ubuntu-24.04-arm`) for checks and a container job per
    architecture, no QEMU as native evidence; fallback only if the runner is unavailable.
  - TD-21-9 retained 0.1.0 fixtures from `0da1249` with automated upgrade/rollback tests; no
    live run (ISSUE-21-DEC-001).
  - TD-21-10 documentation in `docs/contract/versioning.md`, `docs/contract/compatibility.md`,
    `docs/validation/stage-2-release.md`; README support table keeps the DEC-013 phrases; no version
    bump. R21-COVERAGE: no WLED-COVERAGE row changes.
- Conditions: applies while #21 is open; deviations go back to the coordinator.

## Issue #22 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09. Human sources are owner chat messages in the main coordinator session, no permalinks.

### ISSUE-22-DEC-001 — Build the PyPI publish workflow

- ID: ISSUE-22-DEC-001
- Status: active for issue #22 only.
- Authority: human decision ("ja, bau den workflow mit publish.yml und pypi aber lass das von opus machen" (English: "yes, build the workflow with publish.yml and pypi, but have Opus do it")), answering whether to build the wheel, smoke-test and publish workflow behind the `pypi` environment.
- Scope: the PyPI part of #22 (S2-DIST-01 and the PyPI side of S2-DIST-03): workflow file, tests, owner-side setup and release documentation.
- Decision: build `.github/workflows/publish.yml` with a build and smoke-test job and a separate publish job in the GitHub environment `pypi`, using PyPI Trusted Publishing (OIDC), no API tokens. Implementation and review run on Opus. The owner registers the pending Trusted Publisher at PyPI (project `wled-mcp`, owner `descipar`, repository `wled-mcp`, workflow `publish.yml`, environment `pypi`) and creates the GitHub environment with required reviewers.
- Conditions: merging the workflow publishes nothing. No upload, name reservation, PyPI/TestPyPI registration, environment, setting or ruleset change, tag, release or workflow run is authorized; each needs an explicit instruction (DEC-023). Merge needs the owner's approval; the DEC-022 standing approval is not used (DEC-027 item 7). Answers, for #22, the workflow part of DEC-023 item 2 and DEC-027 item 4.
- Update 2026-11-09: PR #141 merged as `bf2359e` at the owner's instruction ("141 mergen, keine testpypi probe, trigger design wie vorgchlagen" (English: "merge 141, no TestPyPI rehearsal, trigger design as proposed"); typing error kept), with `--admin` (DEC-024).

### ISSUE-22-DEC-002 — Technical defaults for the PyPI workflow packet

- ID: ISSUE-22-DEC-002
- Status: active for issue #22 only; technical proposal by the coordinator under ISSUE-22-DEC-001, not an owner decision (items 2 and 4 later owner-confirmed, see Update).
- Authority: technical proposal (coordinator).
- Scope: the PyPI publish workflow packet of #22.
- Decision:
  1. Bounded packet: only the PyPI workflow; OCI image pipeline, SBOM, attestation and vulnerability review stay open.
  2. Triggers: a published GitHub release and manual `workflow_dispatch` on a tag; no `push` or `pull_request` trigger publishes. The publish job runs in environment `pypi`, whose required reviewers are the barrier.
  3. Version guard: the build job refuses unless the ref is tag `v<version>` matching `project.version` of `pyproject.toml` and the built artifacts.
  4. Actions in `publish.yml` pinned by full commit SHA (it holds `id-token: write`); `ci.yml` keeps its style.
  5. Documentation in new `docs/PUBLISHING.md` (DEC-021 placement); evidence in `docs/validation/stage-2-release.md`.
  6. The build job also refuses a tag whose commit is not reachable from `main` (DEC-023 item 1).
  7. Package metadata may be completed (classifiers without `License ::`, `Changelog` URL, sdist exclusion of a worktree `.git` file); exact runtime pins and README wording are reported to the owner.
- Observation (read-only, 2026-11-09, not a decision): PyPI and TestPyPI returned 404 for `wled-mcp`; a GitHub environment `pypi` existed with one required-reviewer rule; no tag for the current version existed.
- Update 2026-11-09: items 2 and 4 are owner-confirmed by the message quoted in ISSUE-22-DEC-001's update; items 1, 3 and 5 to 7 remain coordinator defaults. The owner declined a TestPyPI rehearsal. Item 7's report is answered by ISSUE-22-DEC-003 and ISSUE-22-DEC-005.

### ISSUE-22-DEC-003 — Loosen the exact runtime pins

- ID: ISSUE-22-DEC-003
- Status: active for issue #22 only.
- Authority: human decision ("laufzeit pins lockern" (English: "loosen the runtime pins")), answering whether to keep or loosen the exact pins `mcp==2.3.0`, `starlette==1.10.0`, `uvicorn==0.54.0`.
- Scope: #22 acceptance item 4 (S2-DIST-03).
- Decision: published metadata declares ranges instead of exact pins. The staged release, container image and stdio hub example keep installing the exact tested set through `requirements-runtime.txt`.
- Conditions: the ranges are technical defaults (ISSUE-22-DEC-004); no release or upload is authorized.

### ISSUE-22-DEC-004 — Technical defaults for the dependency ranges

- ID: ISSUE-22-DEC-004
- Status: active for issue #22 only; technical proposal accepted by the coordinator under ISSUE-22-DEC-003, not an owner decision.
- Authority: technical proposal (requirements role, accepted by the coordinator).
- Scope: #22 acceptance item 4.
- Decision:
  1. Ranges: `mcp>=2.3.0,<3`, `pydantic>=2.12.0,<3`, `httpx2>=2.16,<3`, `starlette>=1.0.0,<2`, `uvicorn>=0.31.1,<0.55` (capped at the next minor: `0.x`, internals subclassed), `anyio>=4.10,<5` (newly declared, imported directly).
  2. Floors confirmed by a lowest-direct install and test run; a failing floor is raised and recorded. The run confirmed all floors.
  3. Placement: `docs/contract/dependencies.md`; evidence `docs/validation/stage-2-release.md`; CHANGELOG entry in the 0.1.2 section.
- Conditions: widening an upper bound later needs a highest-resolution test run.
- Owner update 2026-11-09: "mach es doch sinnvoller und gehe nicht alle versionen so tief runter, da kann man doch mal abwägen" (English: "do it more sensibly and do not go down so deep for all versions, one can weigh things up"). The ranges rest on one lower-bound run and one newest/locked run; the review is light.

### ISSUE-22-DEC-005 — README fit for the PyPI project page

- ID: ISSUE-22-DEC-005
- Status: active for issue #22 only.
- Authority: human decision (paraphrased by the main session, no verbatim quote): fewer separate PRs on the release path, so the PR of ISSUE-22-DEC-003 also makes README.md correct for the PyPI page.
- Scope: README.md for the PyPI page of 0.1.2 (S2-DIST-01), same PR as ISSUE-22-DEC-003.
- Decision: no false "not published to PyPI" statement and no dated "published" claim; PyPI route first once published, Git route kept; every relative link made absolute (`https://github.com/descipar/wled-mcp/blob/main/...`); a test fails on a relative link. No other README edits.
- Conditions: no tag, release, upload, registration or setting change authorized; tagging afterwards is the main session's action under its own owner authorization.

### ISSUE-22-DEC-006 — Narrow #22 to the PyPI path

- ID: ISSUE-22-DEC-006
- Status: active for issue #22 only.
- Authority: human decision (instructions paraphrased, no verbatim quote): narrow #22 to the PyPI path and move container work to a new backlog issue.
- Scope: acceptance checklist and title of #22; new issue #156 (S2-DIST-01 to 03).
- Decision: #22 covers the PyPI wheel/sdist release path only (S2-DIST-01 and the PyPI parts of S2-DIST-03). Container selection and smoke tests, multi-architecture images, image SBOM/provenance, image name checks and OCI pin/rollback documentation (S2-DIST-02 and the OCI parts of S2-DIST-03) move to [#156](https://github.com/descipar/wled-mcp/issues/156) in the Backlog. DEC-023 still applies.
- Conditions: no build, upload, registration or setting change authorized. Next: close #22 once the inventory and vulnerability note exists.

## Issue #23 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

### ISSUE-23-DEC-001 — Bring the M6 issues to current requirements

- ID: ISSUE-23-DEC-001
- Status: active for the open M6 issues (#23, #25, #151, #181) only; coordinator-proposal items are
  not owner decisions.
- Authority: human decision (owner chat, main coordinator session, 2026-11-12, no permalink) for the
  issue-body rewrite and workflow start; coordinator proposal (DEC-028) for deferrals. Owner
  statements: "Issue-Body anpassen" (English: "adapt the issue body"); "das issue soll einfach auf die
  aktuellen anforderungen angepasst werden. da interessiert mich der originaltext nicht" (English:
  "the issue should simply be adapted to the current requirements; I am not interested in the
  original text"); "Ja, Workflow für #23 starten" (English: "yes, start the workflow for #23"); the
  same treatment for all M6 issues, removing stage markers, and adding the stale H07 statement to #23.
- Decision: bodies of #23, #25, #181 rewritten against `main` (GitHub keeps history); #151 needed no
  change then (later rewritten under [ISSUE-151-DEC-001](m3-m6.md)); `stage:5` removed from #23,
  #25. Acceptance of #23: troubleshooting page, replacement architecture guide, corrected stale
  statements (SOURCES.md, DEVELOPMENT.md, README, VALIDATION.md H07), ROADMAP Backlog row, existing
  doc checks. Runs as a docs-only change.
- Conditions: deferral of a release policy, support issue template, third-party license overview and
  metadata cross-check is a coordinator proposal; the owner may schedule or drop each. No
  publication, license change, repository setting or hardware contact; merge approval stays per PR.
- Affected: S2-PUBLIC-02/03, S2-LAUNCH-01/02; DEC-029. Supersedes: obsolete #23 body sections only.

## Issue #24 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09. Human sources are owner chat messages in the main coordinator session, no permalinks.

### ISSUE-24-DEC-001 — Prepare registry metadata, drafts and the next patch release

- ID: ISSUE-24-DEC-001
- Status: active for issue #24 only.
- Authority: human decision ("Ja, mach so" (English: "Yes, do it that way")), answering the coordinator's proposed packet (items 1 to 4 and ISSUE-24-DEC-002).
- Scope: #24 (S2-MARKET-01 to 03), one PR with "Refs" (not "Closes"); the issue stays open because the fresh-MCPHub install test needs the published package.
- Decision: authorized: (1) a registry namespace marker in the README for `io.github.descipar/wled-mcp`; (2) a locally validated root `server.json` (PyPI package, stdio through uvx, no `remotes`); (3) drafts only of the MCPM / local-catalog entry and the hosted mcphub.app submission copy; (4) preparing the next patch release in the same PR (version bump, `uv.lock`, changelog).
- Not authorized: Git tag, GitHub release, PyPI upload, installing, logging in to, validating with or publishing with `mcp-publisher` (`validate` sends the file to an external service), any external issue, PR or form submission, hardware or LAN contact.
- Conditions: not standing permission for publication; each step needs an instruction at that time (DEC-023). Merge follows DEC-022 and DEC-029 item 4 (M1, #24 per DEC-030) and authorizes no publication step.
- Update 2026-11-09: the PR was merged. Item 4 is superseded in part by DEC-030 item 4 (the milestone release needs a minor version); the prepared patch version was never tagged or published. Items 1 to 3 stand; item 3 is narrowed by ISSUE-24-DEC-003.

### ISSUE-24-DEC-002 — Technical defaults for the registry packet

- ID: ISSUE-24-DEC-002
- Status: active for issue #24 only; technical proposal by the coordinator under ISSUE-24-DEC-001, not an owner decision.
- Authority: technical proposal (coordinator).
- Scope: the issue-24 packet (S2-MARKET-01 to 03).
- Decision:
  1. Root `server.json`, `$schema` the 2025-12-11 server schema.
  2. Name `io.github.descipar/wled-mcp` (DEC-012); title "WLED MCP (unofficial)"; description at most 100 characters, unofficial and not affiliated; repository and website URLs to the repository.
  3. Marker `<!-- mcp-name: io.github.descipar/wled-mcp -->` after the README intro paragraph, no link.
  4. One package entry, no `remotes`: `pypi`, `wled-mcp`, version of `project.version`, runtime hint `uvx`, stdio; runtime arguments mirror README step 3; package arguments `--transport stdio`, `--config {config_path}`, `--data-dir {data_dir}` (required, `filepath`, not secret); no environment variables. `--isolated` is a positional argument with the fixed value (deviation from "named flag", reported).
  5. MCPM draft `docs/listings/mcpm-wled-mcp.json`: unpinned uvx, paths as `${...}` references, synthetic paths, no `is_official`, no tools array.
  6. Hosted-directory copy `docs/listings/mcphub-app-submission.md`: English, impersonal, fields unverified, draft status, no WLED logo.
  7. Published schemas are not vendored; `tests/test_registry_metadata.py` holds offline invariants with negative controls; `docs/validation/stage-2-release.md` records one live schema validation and that the publisher's checks were not run.
  8. `scripts/check_distribution.py` requires `mcp-name: <name of server.json>` in the wheel `METADATA`.
  9. Release preparation: patch bump, `uv.lock`, changelog from `git log v0.1.2..HEAD` (additive, [versioning](../contract/versioning.md)); bump in this PR.
  10. `docs/PUBLISHING.md` documents registry steps after the PyPI release; no automation; `mcp-publisher validate` not used.
  11. Currently true wording (README "no registry entry", Status paragraph) stays.
- Conditions: until the owner changes it or the work is merged.

### ISSUE-24-DEC-003 — Official MCP Registry only; no MCPM or hosted-directory submission for now

- ID: ISSUE-24-DEC-003
- Status: active for issue #24 only.
- Authority: human decision (paraphrased: once M1 closes the server shall be findable in the MCPHub registry, i.e. the official MCP Registry; MCPM contribution and hosted mcphub.app form not wanted for now).
- Scope: #24 listing routes only (S2-MARKET-01 to 03).
- Decision: the goal is findability through the official MCP Registry after M1 closes. The MCPM / local-catalog contribution and the hosted mcphub.app submission are dropped for now; their drafts stay in `docs/listings/` unsubmitted and unmaintained. Tag, GitHub release, PyPI upload, `mcp-publisher login` and `mcp-publisher publish` each need an explicit instruction at that time.
- Conditions: bounded to #24 and "for now"; the owner may reinstate a route; not standing permission (DEC-023, DEC-030). Narrows ISSUE-24-DEC-001 item 3. Next: the 0.2.0 release chain in [PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release).

### ISSUE-24-DEC-004 — Per-step publication instructions for the M1 release

- ID: ISSUE-24-DEC-004
- Status: executed (each instruction was used once; nothing remains authorized).
- Authority: human decision (separate owner chat instructions).
- Scope: #24 and the M1 minor release only, under ISSUE-24-DEC-003 and DEC-030 (S2-MARKET-01).
- Decision: authorized once each: tag and GitHub release of the M1 release, approval of the `pypi` environment for that publish run, the publisher login (run by the owner), and the registry publish of `server.json`.
- Conditions: consumed by execution; a later release, tag, upload or registry publish needs its own instruction (DEC-023, DEC-030). The fresh-install test (S2-MARKET-03) is separate. Completes the DEC-030 open question for M1 with ISSUE-24-DEC-003.

### ISSUE-24-DEC-005 — Waive the hub-side start of an adapted registry entry

- ID: ISSUE-24-DEC-005
- Status: active for issue #24 only.
- Authority: human decision (2026-11-10: "nein, es reicht so als installiert" (English: "no, it is enough as installed as it is")), answering whether the corrected entry should be started once in the owner's hub.
- Scope: item 6 of #24 (fresh install from generated configuration, S2-MARKET-03) only.
- Decision: the hub-side start of the manually adapted registry entry is waived. The registry listing, the observed install dialog with the documented manual adaptation ([validation/stage-2-release.md](../validation/stage-2-release.md#mcphub-registry-tab-observed-install-dialog-2026-11-10)) and the local launch check of the composed command are sufficient for item 6.
- Conditions: closed by waiver, not observation: the install-test row stays "not run" and says "waived by the owner". Claims nothing about other hosts; no publication permission. A later hub-side observation can be recorded without changing this. Closes the follow-up of ISSUE-24-DEC-004.

## Issue #25 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

### ISSUE-25-DEC-001 — Drop the opt-in simulator

- ID: ISSUE-25-DEC-001
- Recorded date: 2026-11-12
- Status: active for issue #25 only.
- Authority: human decision (owner chat answer, main coordinator session, 2026-11-12):
  "Simulator streichen" (English: "drop the simulator").
- Scope: the opt-in synthetic demo/simulator part of S2-LAUNCH-01 and of #25 only.
- Decision: the simulator is dropped, not deferred; it is not built and no Backlog issue is
  opened. No-hardware evidence stays with the existing test doubles in `tests/`.
- Conditions: the rest of S2-LAUNCH-01/-02 is unchanged; the owner may reinstate a simulator
  later as a new issue.
- Supersedes / superseded by: supersedes, for the simulator only, the deferral in
  [DEC-023](../DECISIONS.md#dec-023--staged-first-public-release) item 3.

### ISSUE-25-DEC-002 — Hardware use and scope of the launch-report PR

- ID: ISSUE-25-DEC-002
- Recorded date: 2026-11-13
- Status: active for issue #25 only; the hardware part is spent once the run is recorded.
- Authority: human decision (owner instruction, coordinator session, 2026-11-13).
- Scope: the launch report and prepared rollback checklist of #25. The selected test
  controller (named only in the local reference) may be used for read and write checks with a
  restorable state kept first, a small call count and the scope recorded.
- Decision: the report and checklist may be prepared, and one bounded hardware run of the
  published release 0.3.0 on that controller is authorized
  ([validation/releases.md](../validation/releases.md)).
- Not authorized: restart or rollback of the deployed service (checkbox 2 needs its own
  authorization), publication, release, tag, registry submission, MCPHub deployment,
  visibility or license change.
- Conditions: that controller and that run only; merge approval stays with the owner.
- Supersedes / superseded by: none.

### ISSUE-25-DEC-003 — Restart, rollback and hub-entry changes for the live rollback

- ID: ISSUE-25-DEC-003
- Recorded date: 2026-11-13
- Status: active for issue #25 only; exercised once on 2026-11-13 (rollback 0.3.0 to 0.2.0
  and restore; the hub entry was not changed).
- Authority: owner authorization relayed to the packet session by the coordinator in three
  messages on 2026-11-13 (recorded as relayed, not verified by this session).
- Scope: item 1 of #25 (S2-COMPAT-03, live part): back up inventory, data directory and the
  wled-mcp hub entry, roll the deployed HTTP service back to the previous release following
  DEPLOYMENT.md, check with read-only calls only, restore the release it ran before and the
  hub entry; change only the wled-mcp entry; no hostnames, addresses or credentials in files.
- Decision: the run is authorized in that scope; it stops and reports if a true rollback
  needs an artifact or choice that is not available. Rollback target: release 0.2.0, staged
  on the target first. The hub entry may be changed for this rollback (this issue only, not
  standing), only if the verification needs it, backed up first and restored afterwards; no
  other hub entry, no hub reinstall ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)),
  no publish, release, tag or registry step.
- Not authorized: other hub entries; ISSUE-24-DEC-005 waiver unchanged, no fresh-install test.
- Superseded part: "restart and rollback are not authorized" of ISSUE-25-DEC-002 no longer
  holds for this scope; its hardware part is unchanged.
- Executed 2026-11-13 after the owner's "go": record in
  [validation/releases.md](../validation/releases.md#3-upgrade-and-rollback-evidence);
  the hub entry was not changed. The later update to 0.4.0
  ([validation/releases.md](../validation/releases.md)) ran on a separate owner
  instruction, outside this decision.
