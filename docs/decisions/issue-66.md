# Issue #66 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-66-DEC-001 — WLED 16 `bs` key in state presets

- ID: ISSUE-66-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #66 only.
- Authority/source: technical determination by the requirements agent (TD-66-1 to TD-66-5),
  accepted by the coordinator; not a human decision, the owner may veto at review. Implementation
  authority: owner instruction "#66 nach workflow umsetzen" (English: "implement #66 per
  workflow"), 2026-11-06 (DEC-001). Evidence: read-only review of WLED source tag `v16.0.1`
  ([SOURCES.md](../SOURCES.md#issue-66-wled-16-preset-evidence)).
- Scope: preset classification, save verification and save-result warning of the preset tools.
- Decision:
  - Determination: top-level `bs` is the global blending (transition) style, read by
    `deserializeState`, masked to 5 bits, only consumed by rendering, not persisted to
    configuration, not synced, not a preset, playlist or control action; light state like
    `transition`, safe in a `state` preset.
  - TD-66-1 `bs` joins the `state` allowlist; the observable-field rule (one of `on`, `bri`,
    `seg`) is unchanged, so `bs` alone is not a state preset; no value or type check.
  - TD-66-2 `bs` is a compared master field on save, only when present in the live state read
    before the save.
  - TD-66-3 A save whose stored entry does not classify as `state` adds one warning naming only
    the unexpected top-level key names; outcome unchanged, no corrective write or retry.
  - TD-66-4 Activation (`{"ps": id}`, control keys, playlist rules, verification) is unchanged;
    `bs` is not verified on activation.
  - TD-66-5 The stateful test fake stores `bs` only when its live state has it; the default fake
    stays 0.15-shaped.
- Conditions: evidenced for the v16.0.1 source only (not hardware); 0.15.x unaffected; other 16.x
  revisions and forks not reviewed; other new top-level keys stay `unknown`. Amends the `state`
  allowlist of SOURCES.md "Issue-9 preset evidence"; does not supersede ISSUE-9-DEC-001. A
  hardware re-check of save then activate on a WLED 16 controller is pending (#12 follow-up) and
  needs its own authorization.
