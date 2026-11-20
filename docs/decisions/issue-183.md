# Issue #183 decisions

## ISSUE-183-DEC-001 — Selected-controller live writes for the #183 evidence

- Recorded date: 2026-11-16.
- Status: active for the bounded issue #183 evidence only.
- Authority/source: owner message relayed by the main session, 2026-11-16 (no permalink):
  "freigabe für hware auf dem üblichen gerät" (English: "approval for hardware on the usual
  device"). "The usual" is the test controller of the earlier validation runs; its address and
  inventory stay in ignored local configuration.
- Scope: R-183 live evidence (single-controller room path) for the M7 exit; that one controller.
- Decision: authorized on that controller: room/group listing (read), a dry run, and live state
  changes through the new room action (power, brightness, colour or effect on the existing
  segment) followed by a restore. Budget: one or two evidence runs (DEC-028), each preceded by a
  dry run and a read-only probe, against the exact PASS-ready candidate commit.
- Baseline to capture and restore (verified by read-back): power off, brightness 47, preset list
  exactly one entry (slot 1, "Solid").
- Not authorized: preset store/overwrite/delete, playlists, configuration, network or firmware
  settings, OTA, reboot, other controllers, hub deployment. Stop and ask on any unexpected state,
  failed restoration or uncertain write (never retried blindly).
- Conditions: ends when #183 closes; not valid for other issues, milestones or controllers; earlier
  hardware approvals are not reused. Merge approval stays with the owner.

## ISSUE-183-DEC-002 — Room design defaults

- Recorded date: 2026-11-16.
- Status: active technical proposal accepted by the coordinator for issue #183 only; not a human
  decision; the owner can change any item at the merge decision (DEC-028).
- Decision:
  1. A room is a stored group with optional `kind` (`group` default, or `room`); format stays
     `wled-mcp.group` version 1, plain groups are written without `kind`, existing files are never
     rewritten; belonging derives from room-kind groups.
  2. One room per controller; a second assignment is a conflict before any save or write; plain
     groups may overlap.
  3. One new control tool `wled_apply_room(room, state | scene_id, mode, dry_run)` reusing the
     scene planners and `Resources.write_verified`; no new write primitive, application or
     verification value or error code. A state patch is refused for a room whose members designate
     segments; a scene applies only if everything it touches lies inside the room and its
     designated segments, else the whole request is refused before any write.
  4. Optional `room` on `wled_plan_zone` and `wled_apply_zone`; a segment outside is refused
     (`outside_room`).
  5. Partial failure never reports overall success; unknown outcomes are `WRITE_OUTCOME_UNKNOWN`.
  6. The served schema budget is raised as measured (docs/validation/issue-235.md).
- Contracts: docs/contract/rooms.md, groups-scenes.md, zones.md.
