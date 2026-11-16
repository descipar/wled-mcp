# Issue #183 decisions

## ISSUE-183-DEC-001 — Selected-controller live writes for the #183 evidence

- Recorded date: 2026-11-16.
- Status: active for the bounded issue #183 evidence only.
- Authority/source: actual owner message relayed by the main session on 2026-11-16 (no
  permalink): "freigabe für hware auf dem üblichen gerät" (English: "approval for hardware on
  the usual device"). "The usual" is the test controller of the earlier validation runs (hub
  device id `skadis`); its address and inventory stay in ignored local runtime configuration
  and the maintainer's local notes, never in a committed file.
- Scope: R-183 live evidence (the single-controller room path) for the M7 exit; that one
  selected test controller only.
- Decision: the live writes that the #183 acceptance evidence needs are authorized on that one
  controller: room/group listing (read), a dry run, and live state changes through the new room
  action (power, brightness, colour or effect on the existing segment), followed by a restore.
  Budget: one or two evidence runs (DEC-028), each preceded by a dry run and a read-only probe.
  The live step runs only against a PASS-ready candidate commit, using that exact commit.
- Baseline to capture first and to restore and verify by read-back afterwards: power off,
  brightness 47, preset list exactly one entry (slot 1, "Solid").
- Not authorized: preset store, overwrite or delete, playlists, configuration, network or
  firmware settings, OTA, reboot, any other controller, hub deployment. Stop and ask the owner
  on any unexpected state, failed restoration or uncertain write; an uncertain write is never
  retried blindly.
- Conditions/expiry: ends when issue #183 closes. Not a general write approval; not valid for
  other issues, milestones or controllers. Merge approval stays with the owner (DEC-029 item 4
  covers M1 and M2 only).
- Rationale supplied: not supplied beyond the statement.
- Affected: `docs/validation/issue-183.md`, the M7 exit evidence.
- Supersedes: no earlier decision; earlier per-issue hardware approvals are not reused.
- Propagation: requirements and implementation roles receive this ID and scope in their
  handoffs; the live run itself is carried out by the coordinator session.

## ISSUE-183-DEC-002 — Room design defaults

- Recorded date: 2026-11-16.
- Status: active technical proposal accepted by the coordinator for issue #183 only; not a human
  decision. The owner can change any item at the merge decision (DEC-028).
- Authority/source: requirements packet for issue #183 (`.agent-runs/m7/issue-183/packet.md`),
  accepted by the coordinator within the constraints of the issue.
- Scope: issue #183 only.
- Decision:
  1. A room is a stored group with an optional `kind` (`group` by default, or `room`); the group
     format stays `wled-mcp.group` version 1, plain groups are written without `kind`, existing
     files are never rewritten. Belonging is derived from room-kind groups (no inventory field).
  2. One room per controller; a second assignment is reported as a conflict before any save or
     write; plain groups may overlap.
  3. One new control tool `wled_apply_room(room, state | scene_id, mode, dry_run)` reusing the
     scene planners and `Resources.write_verified`; no new write primitive, application or
     verification value or error code. A state patch is refused for a room whose members designate
     segments; a scene is applied only if everything it touches lies inside the room and the
     designated segments, otherwise the whole request is refused before any write.
  4. Optional `room` on `wled_plan_zone` and `wled_apply_zone`; a segment outside the room is
     refused (`outside_room`).
  5. Partial failure never reports overall success; unknown outcomes are `WRITE_OUTCOME_UNKNOWN`.
  6. The served schema budget is raised as measured and recorded in docs/validation/issue-235.md.
- Applicability / conditions / expiry: issue #183 until a later decision.
- Rationale supplied: packet analysis (agent).
- Affected: docs/contract/rooms.md, groups-scenes.md, zones.md, agent-guidance.md, versioning.md,
  TOOL-CONTRACT.md, tests.
- Supersedes: none.
- Propagation: implementation and review handoffs.
