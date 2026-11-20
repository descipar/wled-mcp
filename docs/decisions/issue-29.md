# Issue #29 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-11.

## ISSUE-29-DEC-001 — Technical defaults TD-29-1 to TD-29-14

- ID: ISSUE-29-DEC-001
- Status: active for issue #29.
- Authority: technical proposal accepted by the coordinator, 2026-11-11 (TD-29-1 to TD-29-14 of the
  #29 packet); not a human decision. Reversible by the owner.
- Scope: #29 only (static SVG layout preview, S3-PREVIEW-01/02).
- Decision: one read-class tool `wled_preview_layout` returns the SVG as a string in the standard tool
  result (`data.svg`, `data.media_type` `image/svg+xml`), not as an MCP resource or image content, so
  both transports deliver it identically. It renders the observed 1D segment layout of one configured
  device or a proposed layout validated by the existing planner without any write, with optional zone
  bands (#27) and live colour samples (#150). The renderer is pure, deterministic and bounded with an
  element/attribute allowlist and one text sanitiser. Matrix devices are refused with
  `UNSUPPORTED_CAPABILITY`; no 2D geometry is inferred; colours are approximations, effects are not
  simulated. No hardware access.
- Conditions: ISSUE-150-DEC-001 and ISSUE-30-DEC-001 are not reused. Merge needs the owner's decision
  (DEC-029 item 4 covers M1 and M2 only).
- Affected: S3-PREVIEW-01/02, S3-T03; `docs/contract/layout-preview.md`. Supersedes: none. Carried
  (not created): optional 2D preview over declared matrix geometry.
