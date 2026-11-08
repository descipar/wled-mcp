# Issue #17 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-08.

## ISSUE-17-DEC-001 — Storage of groups and scenes, default failure policy

- ID: ISSUE-17-DEC-001
- Recorded date: 2026-11-08
- Status: active for issue #17.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-08 to the two Phase-0
  questions of the requirements packet `.agent-runs/stage2/issue-17/packet.md`
  (OD-17-1 and OD-17-2): "A und A" (English: "A and A"); no permalink.
- Scope: issue #17 (named device groups and reusable multi-device scenes), both pull
  requests.
- Decision:
  - OD-17-1, option A: groups and scenes are local JSON documents under
    `<data-dir>/groups/` and `<data-dir>/scenes/`. They are written by `manage`-class
    tools and read by `read` tools. The inventory file is untouched.
  - OD-17-2, option A: the default failure policy is `strict` (nothing is written if
    any target fails preflight); `best_effort` is an explicit opt-in.
- Applicability / conditions / expiry: issue #17 until a later owner decision. The
  scene apply tool of the second pull request applies the policy default; the first
  pull request only plans.
- Rationale supplied: none beyond choosing the recommended options; the packet
  rationale (no file edit or restart for agent-authored groups, no configuration
  schema change, no half-applied scene by default) is agent analysis.
- Affected requirement IDs, files, issues and tests: S2-GROUP-01, S2-GROUP-02;
  `src/wled_mcp/scene_store.py`, `scene_tools.py`; docs/contract/groups-scenes.md;
  tests/test_scene_store.py, tests/test_scene_tools.py.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-17 packet (OD-17-1, OD-17-2).
- Revalidation needed / next action: none.

## ISSUE-17-DEC-002 — Technical defaults TD-17-1 to TD-17-18 and coordinator choice C-17-1

- ID: ISSUE-17-DEC-002
- Recorded date: 2026-11-08
- Status: active for issue #17 (both pull requests).
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: requirements packet `.agent-runs/stage2/issue-17/packet.md` (items TD-17-1 to
  TD-17-18 and acceptance scenarios AC-17-01 to AC-17-14), accepted in the coordinator
  session on 2026-11-08 together with C-17-1 below; recorded with the first #17 pull
  request.
- Scope: issue #17 only; not a project-wide rule. It applies ISSUE-17-DEC-001,
  ISSUE-20-DEC-001 (tool classes), ISSUE-98-DEC-001 (expected tool contract) and
  ISSUE-21-DEC-002 TD-21-5 (integer schema versions).
- Decision:
  - C-17-1 Issue #17 starts now. The class classification of ISSUE-20-DEC-001 (#98)
    satisfies the DEC-021 dependency "profile classes"; the enforcement of #20 is not
    a prerequisite.
  - TD-17-1 Two pull requests. A: groups, scene format and store, sharing and
    `wled_plan_scene` (reads only, never sends a device write). B: `wled_apply_scene`
    (the only device-write path), executor, policy and aggregate outcome.
  - TD-17-2 Tools after `wled_import_presets`, in registry order, with class and
    destructive flag: `wled_list_groups` (read, no), `wled_save_group` (manage, yes),
    `wled_delete_group` (manage, yes), `wled_list_scenes` (read, no),
    `wled_save_scene` (manage, yes), `wled_delete_scene` (manage, yes),
    `wled_plan_scene` (read, no); pull request B adds `wled_apply_scene` (control, no).
    The list tools return the full document through an optional ID instead of separate
    get tools. `wled_plan_scene` is a separate read-class tool so that a read-only
    profile can preview.
  - TD-17-3 One strict JSON document per item, `groups/<id>.json` and
    `scenes/<id>.json`, IDs matching the device ID pattern, lazily created 0700
    directories and 0600 files, at most 64 KiB per document, 100 groups and 500 scenes,
    atomic replace, symlinks and non-regular files refused, unreadable, invalid or
    newer-version files counted and never rewritten, migrated or pruned. Replacing
    needs `overwrite=true` and returns the previous document instead of a snapshot.
    A per-process lock serializes store writes; save and delete take `dry_run`.
  - TD-17-4 Group document: `format` `wled-mcp.group`, integer `format_version` 1, `id`,
    `name`, 1-16 members `{device, segments?}` with explicit unique segment IDs 0-254;
    a duplicate device in one group is rejected. Members are rechecked against the
    inventory at every expansion.
  - TD-17-5 Scene document: `format` `wled-mcp.scene`, integer `format_version` 1, `id`,
    `name`, optional `description`, 1-16 targets of exactly one `device` or `group`
    with `master` and/or `segments`, using the allowlisted fields of the existing
    planners; geometry, names, `selected`, `freeze`, `blend_mode` and raw state are not
    scene fields. Strict JSON, no duplicate keys, 64 KiB bound.
  - TD-17-6 `effect_name` and `palette_name` resolve per device inside the device
    operation (exact, then unique case-folded); ambiguity is `AMBIGUOUS_NAME` with
    bounded candidates; a numeric ID is used as given and the plan warns that it is
    device and firmware specific.
  - TD-17-7 Expansion in document order, a group in member order; each device at most
    once after expansion, otherwise the whole request is refused before any device I/O
    naming the device and both origins.
  - TD-17-8 The plan reads fresh state under the per-device lock, with at most 4
    devices in flight, builds master and segment plans with the real planners and is
    not a reservation.
  - TD-17-9 Policy: `strict` (default) or `best_effort`; fixed limits of 4 devices in
    flight and 16 expanded devices per request; master step before segment step.
  - TD-17-10 Aggregate envelope without new application or verification values; one
    additive error code `STORAGE_FAILED`.
  - TD-17-11 No new write engine and no scene-level lock (pull request B).
  - TD-17-12 Sharing: shareable export through `wled_list_scenes` replaces device and
    group references by positional placeholders, `include_targets=true` keeps them;
    free text containing an inventory host token blocks the export; `wled_save_scene`
    maps placeholders through `target_map`, all or nothing.
  - TD-17-13 Versioning follows TD-21-5 with one shared helper for groups and scenes.
  - TD-17-14 Coverage: the new tools are listed under "Tools without a WLED feature
    row"; no row changes status; the notes of W-SEG-05 and W-SEG-07 are corrected
    because only numeric IDs are accepted by the segment tools.
  - TD-17-15 Documentation in `docs/contract/groups-scenes.md` and
    `docs/validation/issue-17.md`, retained example `examples/contracts/scene.json`.
  - TD-17-16 Tool classes are declared in `tests/tool_contract.py` and on the `Operation`
    (`tool_class`). The access guard lives in the write engines of `Resources` (G3), not in
    `Resources.operation`. `wled_apply_scene` has no `device_id`, so it reaches every device
    through `Resources.write_verified` (the ambient class and each device's ceiling are
    checked at every write) and its preflight calls the public `Resources.require_access`
    once per expanded device; the operation has `tool_class=ToolClass.CONTROL`. (Amended by
    amendment 1; the earlier wording named `Resources.operation` and a per-device entry
    function.)
  - TD-17-17 No firmware gating; capability evidence comes from fresh readbacks through
    the planners.
  - TD-17-18 Review depth is full (DEC-022 item 3).
- Applicability / conditions / expiry: issue #17 until a later decision. Reading choices
  made while implementing pull request A are listed in
  [validation/issue-17.md](../validation/issue-17.md#reading-choices).
- Rationale supplied: packet analysis (agent).
- Affected requirement IDs, files, issues and tests: S2-GROUP-01, S2-GROUP-02, S2-T02,
  S2-T03, S2-T06, S2-COMPAT-01; tests/tool_contract.py; docs/TOOL-CONTRACT.md;
  docs/WLED-COVERAGE.md; the new #17 tests.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-17 packet; implementer and reviewer
  handoffs.
- Amendments:
  - Amendment 1, recorded with pull request B. Authority: technical proposal accepted by
    the coordinator (not a human decision). Source: the independent review of pull request A
    at candidate `9b48a09`, whose findings the coordinator accepted for pull request B.
    It changes only the points below and nothing else in this decision.
    1. Reading choice 2: a device that is not configured, named directly by a target or as a
       group member, is a per-device `UNKNOWN_DEVICE` preflight failure at plan and at apply
       time, with no I/O for that device. `strict` blocks every device; `best_effort` skips
       that device. An unknown group, a duplicate device, the device and patch limits and an
       entry without `ids` on a member that designates none refuse the whole request. Saving
       a scene refuses an unconfigured directly named device.
    2. TD-17-16 as amended above (the guard is in the write engines; the preflight calls
       `Resources.require_access` once per expanded device; `tool_class=CONTROL`).
    3. The leak check of a shareable export (TD-17-12) scans every exported string value
       (scene `id`, `name`, `description`, every `effect_name` and `palette_name` and, only
       when `include_targets` keeps them, the target references), not only `name` and
       `description`. This is a contract-text change
       ([groups-scenes.md](../contract/groups-scenes.md#sharing)).
    4. Group and scene IDs may not be Windows device names; the definition store lock is per
       directory.
  - Reading choices made while implementing pull request B are listed in
    [validation/issue-17.md](../validation/issue-17.md#reading-choices-pull-request-b).
- Revalidation needed / next action: none.
