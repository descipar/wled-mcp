# Issue #28 decisions

## ISSUE-28-DEC-001 — Selected-controller live-output writes for the #28 evidence

- Recorded date: 2026-11-12.
- Status: active for the bounded issue #28 evidence only.
- Authority/source: actual owner message in the coordinator session on 2026-11-12 (no
  permalink): "Freigabe auf den üblichen wled skadis zu schreiben" (English: "approval to write
  to the usual WLED skadis"). "The usual" refers to the test controller used by the earlier
  validation runs (hub device id `skadis`); its address and inventory are kept only in ignored
  local runtime configuration and in the maintainer's local notes, never in a committed file.
- Scope: S3-SIGNAL-01/-02 and S3-T02, the M4 exit evidence; that one selected test controller
  only.
- Decision: the live-output writes and bounded temporary-signal runs that the #28 acceptance
  evidence needs are authorized: one or two evidence runs, not a matrix. Reuse the established
  run pattern: read-only probes first; capture the full state and the preset list beforehand;
  restore and verify afterwards (as in [issue-134](../validation/issue-134.md) and the issue-150
  and issue-30 records). Access is from a local build of the candidate (stdio or loopback HTTP)
  with its own data directory, which is removed afterwards and leaves no snapshot on the hub.
- Baseline to restore: power off, brightness 47, one segment, preset list exactly one entry
  (slot 1, a state preset), no other presets or playlists; WLED 16.0.1, ESP32-C3, 133 LEDs,
  one RGB segment.
- Not authorized: reboot or OTA, firmware or settings/configuration changes, WiFi or security
  settings, overwriting or deleting presets other than ones the run itself created on unused
  slots (and then removed or restored), any other controller, hub deployment (the hub service
  keeps its released version), anything beyond the restoration criteria. Stop and ask the owner
  on any unexpected state, failed restoration or uncertain write; an uncertain write is never
  retried blindly. If the controller is unreachable, record that as a limit and ask instead of
  waiting.
- Conditions/expiry: issue #28 evidence only; expires with the issue. Not a general write
  approval and not valid for follow-up issues, other milestones or other controllers. Merge
  approval stays with the owner (DEC-029 item 4 covers M1 and M2 only).
- Rationale supplied: not supplied beyond the statement.
- Affected: S3-SIGNAL-01/-02, S3-T02, the M4 exit evidence, `docs/validation/issue-28.md`.
- Supersedes: no earlier decision; ISSUE-134, ISSUE-150 and ISSUE-30 approvals are not reused.
- Propagation: requirements, implementation and reviewer roles receive this decision ID and its
  scope in their handoffs; the live run itself is carried out by the coordinator session.

## ISSUE-28-DEC-002 — Temporary signal design defaults

- Recorded date: 2026-11-12.
- Status: active technical proposal accepted by the coordinator for issue #28 only; not a
  human decision. The owner can change any item at the merge decision.
- Authority/source: requirements packet for issue #28 (items TD-28-1 to TD-28-20), accepted by
  the coordinator within the owner constraints of the issue and AR-01.
- Scope: issue #28 / S3-SIGNAL-01/-02 only.
- Decision: three tools (`wled_start_signal`, `wled_get_signal_status`, `wled_cancel_signal`)
  with classes control / read / control; one signal per device, overlap rejected, at most eight
  per process; the signal writes only slot-0 colour, the Solid effect and, when needed, segment
  and master power, and restores exactly those fields only when they still hold what the signal
  set (otherwise `skipped_conflict`); unsupported device states (playlist, realtime, nightlight,
  frozen segments, invisible target) are rejected at start; delayed work runs with an explicit
  `control` access class; locks are held during capture/apply and compare/restore, not while
  waiting; one bounded retry only after a failure that happened before any POST left, never a
  replay; a signal manager owned by `Resources` is shared by stdio and HTTP; orderly shutdown
  makes one bounded (5 s) conditional restore attempt per active signal; nothing is persisted
  and nothing is recovered after a crash or restart (the signal may stay applied, the
  documentation says so and gives the manual recovery); timing is best effort.
- Applicability / conditions / expiry: issue #28 implementation; persistence with an
  `interrupted` status on next start is a possible later follow-up, not part of this scope.
- Rationale supplied: smallest design that meets the acceptance criteria (DEC-028).
- Affected: `docs/contract/signals.md`, signal modules and tests, `docs/validation/issue-28.md`.
- Supersedes: none.
- Propagation: implementer and reviewer receive this ID and the packet.
