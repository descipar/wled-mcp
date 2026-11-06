# Issue #66 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-66-DEC-001 — WLED 16 `bs` key in state presets

- ID: ISSUE-66-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #66 only.
- Authority: technical determination and proposal by the requirements agent (TD-66-1
  to TD-66-5), accepted by the coordinator. This is not a human decision; the owner
  did not choose these defaults and may veto them at review. Human authority for the
  implementation itself: owner instruction "#66 nach workflow umsetzen" on 2026-11-06,
  relayed by the coordinator (DEC-001); no permalink.
- Source: requirements packet `.agent-runs/issue-66/packet.md` (2026-11-06) and a
  read-only review of the WLED source at tag `v16.0.1`, commit
  `29b389df1c1aaec6ff53aea742d17063b985906c`, recorded in
  [SOURCES.md](../SOURCES.md#issue-66-wled-16-preset-evidence).
- Scope: issue #66; preset classification, save verification and the save-result
  warning of the preset tools.
- Decision:
  - Determination: top-level `bs` is the global blending (transition) style. It is
    read by `deserializeState`, masked to 5 bits, only consumed by rendering, not
    persisted to configuration, not synced and not a preset, playlist or control
    action. It is light state of the same kind as `transition` and safe in a `state`
    preset.
  - TD-66-1 `bs` is added to the `state` allowlist. The observable-field rule (at
    least one of `on`, `bri`, `seg`) is unchanged, so `bs` alone is not a state
    preset. No value or type check on `bs`.
  - TD-66-2 `bs` is a compared master field on save, compared only when present in
    the live state read before the save; a stored `bs` without a live `bs` is not
    compared.
  - TD-66-3 A save whose stored entry does not classify as `state` adds one warning
    naming only the unexpected top-level key names (no values, no preset name). The
    outcome is unchanged; no corrective write and no retry.
  - TD-66-4 Activation (payload `{"ps": id}`, control keys, playlist rules and
    activation verification) is unchanged; `bs` is not verified on activation.
  - TD-66-5 The stateful test fake stores `bs` only when its live state has `bs`; the
    default fake state stays 0.15-shaped as the control.
- Applicability / conditions / expiry: evidenced for the v16.0.1 source; 0.15.x is
  unaffected (no `bs` there). Other 16.x revisions and forks are not reviewed. Any
  other new top-level key stays `unknown`. Source evidence only, not hardware evidence.
- Rationale supplied: the source facts in SOURCES.md; the #12 hardware run observed a
  WLED 16 saved entry classified `unknown` because of `bs`.
- Affected requirement IDs, files, issues and tests: PRE-01, PRE-02, PRE-05, PLAY-01
  (member check), T11, T13; `src/wled_mcp/presets.py`, `src/wled_mcp/operations.py`,
  [TOOL-CONTRACT.md](../TOOL-CONTRACT.md), [SOURCES.md](../SOURCES.md),
  `tests/test_presets.py`, `tests/preset_support.py`.
- Supersedes / superseded by: amends the `state` allowlist recorded in SOURCES.md
  "Issue-9 preset evidence" and in the ISSUE-9-DEC-001 clarification; does not
  supersede ISSUE-9-DEC-001 (positive-evidence types remain).
- Propagated to roles / packet references: packet `.agent-runs/issue-66/packet.md`;
  implementer and reviewer through the coordinator.
- Revalidation needed / next action: hardware re-check of save then activate on a
  WLED 16 controller is pending as a #12 follow-up and needs its own human
  authorization naming the controller and a captured/restored baseline.
