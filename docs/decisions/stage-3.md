# Decisions: stage 3 features (issues #27 to #31)

## Issue #27 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

### ISSUE-27-DEC-001 — Technical defaults TD-27-1 to TD-27-16 and the three scope defaults

- ID: ISSUE-27-DEC-001
- Status: active for issue #27.
- Authority: technical proposal accepted by the coordinator, 2026-11-09 (TD-27-1 to TD-27-16 and
  OC-27-1 to OC-27-3 of the issue-27 packet); not a human decision. Reversible by the owner.
- Scope: issue #27 only (S3-ZONE-01, S3-ZONE-02).
- Decision: zones are reviewed local files `<data-dir>/zones/<id>.json` (`format` `wled-mcp.zone`,
  `format_version` 1) mapping a name to configured device IDs and `[start, stop)` LED ranges, with a
  required per-device `led_count` as stale-topology anchor, optional `segment` cross-check and a
  `reversed` flag (reporting only). Tools: `wled_list_zones`, `wled_plan_zone` (`read`),
  `wled_apply_zone` (`control`), after `wled_apply_scene`. Lookup by exact ID, then unique
  case-folded name (`AMBIGUOUS_NAME`). Existing active segments only: a zone resolves only when live
  segments tile it exactly, otherwise refused before any write with a stable `reason` and
  `layout_change_required`; geometry is never changed. No new error code. Apply reuses the scene
  machinery (strict default, four in flight) with one hook that resolves segment IDs from the fresh
  read and re-checks at write time. OC-27-1 (zone targets in groups/scenes) and OC-27-2 (zone
  save/delete tool) deferred; OC-27-3 accepted.
- Conditions: ISSUE-17-DEC-001 (agent-authored groups/scenes) is not generalized to zones.
  Refinements live in [contract/zones.md](../contract/zones.md).
- Supersedes / superseded by: none. Follow-ups (zones in scenes/groups, zone save/delete) not created.

## Issue #28 decisions

### ISSUE-28-DEC-001 — Selected-controller live-output writes for the #28 evidence

- Recorded date: 2026-11-12.
- Status: active for the bounded issue #28 evidence only.
- Authority/source: owner message in the coordinator session, 2026-11-12 (no permalink):
  "Freigabe auf den üblichen wled skadis zu schreiben" (English: "approval to write to the usual
  WLED skadis"). "The usual" is the test controller of the earlier validation runs; its address
  and inventory stay in ignored local configuration, never in a committed file.
- Scope: S3-SIGNAL-01/-02 and S3-T02, the M4 exit evidence; that one controller only.
- Decision: the live-output writes and bounded temporary-signal runs that the #28 evidence needs
  are authorized: one or two evidence runs, not a matrix. Pattern as in
  [issue-134](../validation/hardware-checks.md): read-only probes first; capture full state and preset
  list; restore and verify afterwards; local build of the candidate (stdio or loopback HTTP) with
  its own data directory, removed afterwards.
- Baseline to restore: power off, brightness 47, one segment, preset list exactly one entry
  (slot 1, a state preset), no other presets or playlists; WLED 16.0.1, ESP32-C3, 133 LEDs, one
  RGB segment.
- Not authorized: reboot or OTA, firmware/settings/WiFi/security changes, overwriting or deleting
  presets other than ones the run created on unused slots, any other controller, hub deployment.
  Stop and ask on any unexpected state, failed restoration or uncertain write (never retried
  blindly); an unreachable controller is recorded as a limit.
- Conditions: expires with issue #28; not a general write approval. ISSUE-134, -150 and -30
  approvals are not reused. Merge approval stays with the owner (DEC-029 item 4: M1 and M2 only).

### ISSUE-28-DEC-002 — Temporary signal design defaults

- Recorded date: 2026-11-12.
- Status: active technical proposal accepted by the coordinator for issue #28 only (items
  TD-28-1 to TD-28-20 of the packet); not a human decision; the owner can change any item at the
  merge decision.
- Decision: three tools (`wled_start_signal`, `wled_get_signal_status`, `wled_cancel_signal`;
  classes control / read / control); one signal per device, overlap rejected, at most eight per
  process; a signal writes only slot-0 colour, the Solid effect and, when needed, segment and
  master power, and restores exactly those fields only if they still hold what the signal set
  (else `skipped_conflict`); unsupported states (playlist, realtime, nightlight, frozen segments,
  invisible target) are rejected at start; delayed work runs with an explicit `control` access
  class; locks are held during capture/apply and compare/restore, not while waiting; one bounded
  retry only after a failure before any POST left, never a replay; a signal manager owned by
  `Resources` is shared by stdio and HTTP; orderly shutdown makes one bounded (5 s) conditional
  restore per active signal; nothing is persisted or recovered after a crash (documented with
  manual recovery); timing is best effort.
- Conditions: persistence with an `interrupted` status is a possible later follow-up. Contract:
  `docs/contract/signals.md`.

## Issue #29 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-11.

### ISSUE-29-DEC-001 — Technical defaults TD-29-1 to TD-29-14

- ID: ISSUE-29-DEC-001
- Status: active for issue #29.
- Authority: technical proposal accepted by the coordinator, 2026-11-11 (TD-29-1 to TD-29-14 of the
  #29 packet); not a human decision. Reversible by the owner.
- Scope: #29 only (static SVG layout preview, S3-PREVIEW-01/02).
- Decision: one read-class tool `wled_preview_layout` returns the SVG as a string in the standard tool
  result (`data.svg`, `data.media_type` `image/svg+xml`), not as an MCP resource or image content, so
  both transports deliver it identically. It renders the observed 1D segment layout of one configured
  device or a proposed layout validated by the existing planner without any write, with optional zone
  bands (#27) and live colour samples (#150). The renderer is pure, deterministic and bounded with an
  element/attribute allowlist and one text sanitiser. Matrix devices are refused with
  `UNSUPPORTED_CAPABILITY`; no 2D geometry is inferred; colours are approximations, effects are not
  simulated. No hardware access.
- Conditions: ISSUE-150-DEC-001 and ISSUE-30-DEC-001 are not reused. Merge needs the owner's decision
  (DEC-029 item 4 covers M1 and M2 only).
- Affected: S3-PREVIEW-01/02, S3-T03; `docs/contract/layout-preview.md`. Supersedes: none. Carried
  (not created): optional 2D preview over declared matrix geometry.

## Issue #30 decisions

### ISSUE-30-DEC-001 — Selected-controller read-only live run

- Status: active for the bounded issue #30 / milestone M2 live run only.
- Authority/source: owner message in the coordinator session, 2026-11-11 (no permalink), authorizing
  the read-only live run and naming one controller (name and address only in ignored local files).
- Scope: S3-EXPLAIN-01/-02, the M2 exit criterion; one selected test controller, `read-only` profile
  over stdio, tool `wled_explain_lighting`.
- Decision: a bounded read-only run: at most two tool calls, each reading `/json/state` and
  `/json/info` once. No writes, discovery, configuration or firmware changes, deployment, publication
  or other controllers.
- Conditions/expiry: issue #30 only; consumed by the run in
  [validation/stage-3.md](../validation/stage-3.md); not standing permission. Captures stay in the
  ignored runtime directory; only neutral evidence is published.
- Supersedes: none; ISSUE-150-DEC-001 is not reused.

## Issue #31 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

### ISSUE-31-DEC-001 — Technical defaults TD-31-1 to TD-31-12

- ID: ISSUE-31-DEC-001
- Status: active for issue #31.
- Authority: technical proposal accepted by the coordinator, 2026-11-09 (TD-31-1 to TD-31-12 and two
  optional confirmations of the #31 packet); not a human decision. Reversible by the owner.
- Scope: #31 only (`wled_search_effects`, S3-EFFECT-01/02).
- Decision: one read-only tool `wled_search_effects` (class `read`); optional AND-combined property
  filters with `strict` and `min_confidence` (unknown properties never satisfy a strict filter); each
  catalog property is `{value, confidence, basis, evidence}`, subjective ones never `verified`; a
  shipped versioned JSON catalog with integer `schema_version` rejection; device intersection by exact
  name with `exact`, `id_changed`, name-conflict, ambiguous and absent handling; fixed `no_match`
  reasons; small initial catalog from firmware source at tag `v16.0.1` only; updates by pull request,
  no runtime override or remote fetch; mock tests only. Accepted as proposed: separate properties
  `visibility` and `palette_saturation_need`; firmware below the floor or unrecognizable gets
  `catalog_not_applicable`.
- Conditions: implementation refinements (colour slot count 0 to 3; basis/evidence on each property
  instead of a `provenance` object; firmware floor from `compat.py`) are recorded in
  `docs/contract/effect-search.md`.
- Supersedes / superseded by: none.
