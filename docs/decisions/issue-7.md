# Issue #7 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

## ISSUE-7-DEC-001 — Requirements first, implementation after prerequisites

- Status: active for issue #7 only.
- Authority/source: actual human answer in the current issue-7 workflow session,
  2026-11-04, to the question how to handle the unmet prerequisites #5 and #6;
  no chat permalink exists.
- Scope/decision: prepare only the requirements packet for #7. Implementation
  starts after #5 and #6 are merged; the packet is then refreshed against the new
  main. No code, device access, merge or issue write is authorized by this entry.
- Conditions: this is not a general policy for unmet prerequisites; that question
  remains unresolved in [DECISIONS.md](../DECISIONS.md). Other issues do not reuse it.
- Rationale supplied: none beyond the choice itself.
- Affected: issue-7 requirements packet and the start condition of its
  implementation. Supersession: none.
- Propagation: coordinator passes this ID with the packet to later roles.

## ISSUE-7-DEC-002 — Layout replacement exposes the additional Should options

- Status: active for issue #7 delivery (SEG-05); the human merge decision
  remains separate.
- Authority/source: actual human answer in the same session, 2026-11-04, to the
  packet question D1 (core fields only versus additional Should segment options).
  The answer was the single word "zusätzlich", read as selecting the alternative;
  no chat permalink exists.
- Scope/decision: `wled_replace_layout` also exposes the Should segment options
  `grouping`, `spacing`, `offset`, `reverse`, `mirror`, `selected` and `name`
  beyond the core fields (`id`, `start`, `stop`, `on`, `brightness`, `colors`,
  effect/palette, `speed`, `intensity`).
- Conditions: if #6 already defines handling for any of these fields, #7 follows
  #6 rather than diverging. CCT, 2D and pixel streaming stay out of scope unless
  separately decided. Omitted fields on existing IDs are preserved; new IDs get
  the contract defaults. Requires refreshing the packet's tests and contract text.
- Rationale supplied: none beyond the choice itself.
- Affected: SEG-05, T05–T08 field coverage, TOOL-CONTRACT.md. Supersession: none.
- Propagation: coordinator passes this ID with the packet to later roles.
