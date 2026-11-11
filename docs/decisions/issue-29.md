# Issue #29 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-11.

## ISSUE-29-DEC-001 — Technical defaults TD-29-1 to TD-29-14

- ID: ISSUE-29-DEC-001
- Recorded date: 2026-11-11
- Status: active for issue #29.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: coordinator acceptance on 2026-11-11 of the technical defaults TD-29-1 to TD-29-14 in
  the issue-29 requirements packet (`.agent-runs/issue-29/packet.md`, pinned to main
  `97b4e7a8540af48f3152a8a471893ebfb08a1324`); no permalink.
- Scope: issue #29 only (static SVG layout preview, S3-PREVIEW-01 and S3-PREVIEW-02).
- Decision: in summary, one read-class tool `wled_preview_layout` returns the SVG as a string in
  the standard tool result (`data.svg`, `data.media_type` `image/svg+xml`), not as an MCP
  resource or image content, so both transports deliver it identically. It renders the observed
  1D segment layout of one configured device or a proposed layout validated by the existing
  layout planner without any write, with optional zone bands (#27) and optional live colour
  samples (#150). The renderer is a pure, deterministic, bounded function with an element and
  attribute allowlist and one sanitiser for all text. Matrix devices are refused with
  `UNSUPPORTED_CAPABILITY`; no 2D geometry is inferred. Colours are approximations; effects are
  not simulated. No hardware access is needed or authorized.
- Applicability / conditions / expiry: agent proposals, reversible by the owner. ISSUE-150-DEC-001
  and ISSUE-30-DEC-001 (bounded read-only runs) are not reused. Merge needs the owner's decision
  (the standing approval of DEC-029 item 4 covers M1 and M2 only).
- Rationale supplied: DEC-028 pragmatic delivery; smallest design with identical delivery on
  both transports (AR-02, AR-05); no human rationale supplied.
- Affected requirement IDs, files, issues and tests: S3-PREVIEW-01, S3-PREVIEW-02, S3-T03; #29;
  `docs/contract/layout-preview.md`, `tests/test_layout_preview.py`, `tests/test_preview_tools.py`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-29 packet, implementer, reviewer.
- Revalidation needed / next action: none. Carried (not created): an optional 2D preview over
  declared matrix geometry (candidate milestone Backlog).
