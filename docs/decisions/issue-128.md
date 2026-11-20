# Issue #128 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

## ISSUE-128-DEC-001 — Read-only probes on one secured controller, three lock states

- ID: ISSUE-128-DEC-001
- Recorded date: 2026-11-12
- Status: active for issue #128 only. Executed on 2026-11-12 for "both", "PIN only" and "OTA lock
  only" (docs/validation/issue-128.md); it authorizes nothing further.
- Authority/source: human decision, owner messages in the main session, 2026-11-12 (no
  permalink). The owner designated one controller (address and lock values stay in chat) and
  answered "ja, Read-only-Probes mit beiden Sperren freigegeben". Same day: "wir testen auch
  getrennt gesperrt" (English: "we will also test with the locks separate").
- Scope: #128 acceptance item 2, the one designated controller; states "settings PIN and OTA lock
  both active", later "PIN only" and "OTA lock only" once the owner confirms each is set.
- Decision: authorized are read-only probes (reachability, state, effects, palettes, preset list,
  one preset read) recording status codes and error envelopes, via the server's normal read
  paths; no PIN or passphrase is sent, stored or committed and no lock is bypassed.
- Not authorized: any write, any change of PIN, passphrase or security setting, scan or
  discovery, contact with other devices. The write set (item 3) is ISSUE-128-DEC-002.
- Conditions: bounded to this controller; without owner confirmation of a state the result states
  "unknown" for the individual locks.

## ISSUE-128-DEC-002 — Minimal write set on the secured controller, in each of three lock states

- ID: ISSUE-128-DEC-002
- Recorded date: 2026-11-12
- Status: active for issue #128 only; executed on 2026-11-12, once per state (both, PIN only, OTA
  lock only; docs/validation/issue-128.md); it authorizes nothing further.
- Authority/source: human decision, owner message in the main session, 2026-11-12 (no
  permalink): "freigabe zum write"; clarified: it means the hardware write set (item 3), not the
  PR merge, and runs in all three states one after another.
- Scope: #128 acceptance item 3, the one designated controller, one run per state; the owner sets
  and confirms each state first.
- Decision: per state, in order, stopping at the first failed or uncertain step and never
  retrying a write blindly: (1) master-state brightness change then restore, device off;
  (2) one segment patch (segment 0 speed) then restore; (3) preset store and delete on one unused
  slot (state equal to baseline, power off) with the server's snapshot behavior, then comparison
  with the baseline.
- Not authorized: any other write, firmware update, security setting change, writes while the
  device is on, overwriting or deleting an existing preset, discovery, other devices.
- Conditions: bounded to this controller and these three runs; not standing permission.
