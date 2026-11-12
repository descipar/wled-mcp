# Issue #128 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

## ISSUE-128-DEC-001 — Read-only probes on one secured controller, three lock states

- ID: ISSUE-128-DEC-001
- Recorded date: 2026-11-12
- Status: active for issue #128 only. Executed on 2026-11-12 for the states "both", "PIN only" and
  "OTA lock only" (see docs/validation/issue-128.md); it authorizes nothing further.
- Authority: human decision (owner instruction in the main coordinator session; chat is the
  normal channel for owner authority).
- Source: owner messages in the main session on 2026-11-12 (no permalink). The owner designated
  one controller (address given in chat, deliberately not recorded here), stated that the
  settings PIN and the OTA lock are both enabled on it (values given in chat, deliberately not
  recorded here), and then answered "ja, Read-only-Probes mit beiden Sperren freigegeben" to the
  coordinator's proposal.
- Scope: issue #128, acceptance item 2, the one designated controller only; first the state
  "settings PIN and OTA lock both active", later "PIN only" and "OTA lock only" once the owner
  confirmed each (see owner intent below).
- Decision: the following is authorized.
  1. Read-only probes against that controller: reachability probe, state, effects, palettes,
     preset list and one preset read, recording status codes and resulting error envelopes.
  2. The probes use the server's normal read paths. No PIN or passphrase is sent, stored or
     committed; the server does not try to bypass a lock.
- Not authorized: any write to the controller (master state, segment patch, preset save or
  delete, restore), any change of the PIN, passphrase or other security setting, any scan or
  discovery, contact with any other device. The write set (acceptance item 3) needs its own
  explicit owner authorization (given later, see ISSUE-128-DEC-002).
- Applicability / conditions / expiry: bounded to this state and this controller. The owner
  will later switch to "PIN only" and "OTA lock only" for the separate states required by
  acceptance item 1; probes in those states need the owner's confirmation that the state is set.
  If that does not happen, the result states "unknown" for the individual locks.
- Owner intent, same day (chat, "wir testen auch getrennt gesperrt", English: "we will also test
  with the locks separate"): the states "PIN only" and "OTA lock only" are in scope for this
  issue. This states the plan; it does not by itself authorize probes in those states. The owner
  confirms each state once it is set, and the read-only probes then follow under this decision's
  conditions (same probe set, same controller) unless the owner narrows them.
- Rationale supplied: acceptance item 1 asks for separate states; the owner enabled both at once
  first. No further rationale supplied.
- Affected requirement IDs, files, issues and tests: issue #128, docs/validation/issue-128.md
  (written), README limitations, docs/contract/compatibility.md.
- Supersedes / superseded by: none (extended, not replaced, by ISSUE-128-DEC-002).
- Propagated to roles / packet references: passed to the requirements role (packet
  .agent-runs/issue-128/packet.md) and the reviewer.
- Revalidation needed / next action: none for the read-only states (all run).

## ISSUE-128-DEC-002 — Minimal write set on the secured controller, in each of three lock states

- ID: ISSUE-128-DEC-002
- Recorded date: 2026-11-12
- Status: active for issue #128 only; executed on 2026-11-12, once per state (both, PIN only, OTA
  lock only; see docs/validation/issue-128.md); it authorizes nothing further.
- Authority: human decision (owner instruction in the main coordinator session).
- Source: owner message in the main session on 2026-11-12 (no permalink): "freigabe zum write",
  followed by the owner's answers to two clarifying questions: it means the hardware write set
  (acceptance item 3), not the merge of the pull request, and it runs in all three states one after
  another (both locks, PIN only, OTA lock only). Controller address and lock values stay in chat.
- Scope: issue #128, acceptance item 3, the one designated controller only, one run per state. The
  owner sets each state and confirms it in chat before that state's run.
- Decision: the following is authorized per state, in this order, stopping at the first failed or
  uncertain step and never retrying a write blindly.
  1. A master-state write (brightness change, then restored) with the device off.
  2. One segment patch (segment 0 speed, then restored).
  3. A preset store and a preset delete on one unused slot (state equal to the baseline, power
     off), each with the server's snapshot behavior, then a comparison with the baseline.
- Not authorized: any other write, a firmware update, any change of the PIN, passphrase or other
  security setting, any write while the device is on, overwriting or deleting an existing preset,
  discovery, contact with any other device.
- Applicability / conditions / expiry: bounded to this controller and these three runs; it is not
  standing permission for later hardware writes.
- Rationale supplied: none beyond the scope choice (all three states, so each lock can be judged
  alone).
- Affected requirement IDs, files, issues and tests: issue #128, docs/validation/issue-128.md.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: coordinator only so far; the run is executed by the
  coordinator session.
- Revalidation needed / next action: none; all three runs are done.
