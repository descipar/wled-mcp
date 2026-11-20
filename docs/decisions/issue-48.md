# Issue #48 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-48-DEC-001 — Shared #6/#7 handling of firmware segment limits

- ID: ISSUE-48-DEC-001
- Status: active for issue #48 delivery; the human merge decision remains separate.
- Authority: human decision. Source: answers in the issue-48 workflow session, 2026-11-05, to
  questions D-48-1, D-48-1a, D-48-1b (each the recommended option); no permalink.
- Scope: `wled_patch_segments` (#6) and `wled_replace_layout` (#7). Not a project default; master
  `wled_set_state` is not changed by this entry.
- Decision (option B, 1a: 32 UTF-8 bytes, 1b: reject), identical for both tools:
  - Before any write (and in dry run) reject with `VALIDATION_ERROR`: segment names over 32 UTF-8
    bytes or containing U+0000; `grouping` outside 1-255 and `spacing` outside 0-255; `on=true` with
    `brightness=0`; `brightness=0` with omitted `on` on a segment that is currently on.
  - A positive `brightness` with omitted `on` on a segment that is currently off is compensated: the
    resolved `on=false` is sent with `bri`, shown as targeted compensation, and the resolved `on` is
    verified whenever `bri` is sent.
  - The 32-byte name limit applies to every device (the firmware buffer is a build option).
- Conditions: pinned v0.15.1 source (profile 0, ISSUE-6-DEC-002); hardware confirmation stays with #12.
- Supersedes: for #7, the name limit, absent 255 bounds and `bri` sending rule of
  [ISSUE-7-DEC-006](issue-7.md#issue-7-dec-006--align-7-with-6-limits-and-bri-handling).
  ISSUE-7-DEC-007 stays in force and now also applies to #6. For #6 it tightens the character-based
  name limit and unbounded grouping/spacing.
- Affected: SEG-01, SEG-03 to SEG-05, CTRL-01 (segment part), T04-T08.
