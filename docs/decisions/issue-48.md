# Issue #48 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-48-DEC-001 — Shared #6/#7 handling of firmware segment limits

- ID: ISSUE-48-DEC-001
- Recorded date: 2026-11-05
- Status: active for issue #48 delivery; the human merge decision remains separate.
- Authority: human decision.
- Source: human answers in the issue-48 workflow session, 2026-11-05, to the
  coordinator's questions D-48-1, D-48-1a and D-48-1b (each answered with the option
  marked as recommended); no permalink.
- Scope: issue #48, i.e. the two segment tools `wled_patch_segments` (#6) and
  `wled_replace_layout` (#7). Not a project default; master `wled_set_state` behavior
  is not changed by this entry.
- Decision (option B, 1a: 32 UTF-8 bytes, 1b: reject), identical for both tools:
  - Before any write (and identically in dry run), reject with `VALIDATION_ERROR`:
    segment names over 32 UTF-8 bytes or containing U+0000; `grouping` outside 1-255
    and `spacing` outside 0-255; `on=true` with `brightness=0`; `brightness=0` with
    omitted `on` on a segment that is currently on.
  - A positive `brightness` with omitted `on` on a segment that is currently off is
    compensated: the resolved `on=false` is sent with `bri`, shown in the plan as
    targeted compensation, and the resolved `on` is verified whenever `bri` is sent.
  - The 32-byte name limit applies to every device; it is not derived from the chip
    type because the firmware buffer is a build option.
- Applicability / conditions: pinned v0.15.1 source evidence (profile 0,
  ISSUE-6-DEC-002); hardware confirmation of buffer size, overflow behavior and a
  possible visible transition stays with #12.
- Rationale supplied: none beyond choosing the recommended options.
- Affected: SEG-01, SEG-03, SEG-04, SEG-05, CTRL-01 (segment part), T04-T08,
  docs/TOOL-CONTRACT.md, docs/VALIDATION.md, docs/SOURCES.md, `patches.py`,
  `layouts.py` and their tests.
- Supersedes: for #7, the name limit, the absent 255 bounds and the `bri` sending rule
  of [ISSUE-7-DEC-006](issue-7.md#issue-7-dec-006--align-7-with-6-limits-and-bri-handling).
  ISSUE-7-DEC-007 (#7 brightness=0 rejections) stays in force and now also applies to
  #6 through this entry. For #6, it tightens the previous character-based name limit and
  unbounded grouping/spacing.
- Propagated to: requirements packet `.agent-runs/issue-48/packet.md`, implementer and
  reviewer handoffs.
- Revalidation: hardware evidence (#12) or another firmware profile may require
  revisiting the limits.
