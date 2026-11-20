# Issue #17 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-08.

## ISSUE-17-DEC-001 — Storage of groups and scenes, default failure policy

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

## ISSUE-17-DEC-002 — Technical defaults TD-17-1 to TD-17-18 and coordinator choice C-17-1

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
  - TD-17-15 Docs in docs/contract/groups-scenes.md and docs/validation/issue-17.md;
    example `examples/contracts/scene.json`.
  - TD-17-16 (as amended) Tool classes are declared in `tests/tool_contract.py` and on the
    `Operation` (`tool_class`). The access guard lives in the write engines of `Resources`,
    not in `Resources.operation`; `wled_apply_scene` reaches every device through
    `Resources.write_verified` and its preflight calls `Resources.require_access` once per
    expanded device; `tool_class=ToolClass.CONTROL`.
  - TD-17-17 No firmware gating; capability evidence from fresh readbacks.
  - TD-17-18 Review depth is full (DEC-022 item 3).
- Conditions: until a later decision. Reading choices:
  [PR A](../validation/issue-17.md#reading-choices),
  [PR B](../validation/issue-17.md#reading-choices-pull-request-b).
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
