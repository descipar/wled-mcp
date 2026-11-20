# Issue #28 decisions

## ISSUE-28-DEC-001 — Selected-controller live-output writes for the #28 evidence

- Recorded date: 2026-11-12.
- Status: active for the bounded issue #28 evidence only.
- Authority/source: owner message in the coordinator session, 2026-11-12 (no permalink):
  "Freigabe auf den üblichen wled skadis zu schreiben" (English: "approval to write to the usual
  WLED skadis"). "The usual" is the test controller of the earlier validation runs; its address
  and inventory stay in ignored local configuration, never in a committed file.
- Scope: S3-SIGNAL-01/-02 and S3-T02, the M4 exit evidence; that one controller only.
- Decision: the live-output writes and bounded temporary-signal runs that the #28 evidence needs
  are authorized: one or two evidence runs, not a matrix. Pattern as in
  [issue-134](../validation/issue-134.md): read-only probes first; capture full state and preset
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

## ISSUE-28-DEC-002 — Temporary signal design defaults

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
