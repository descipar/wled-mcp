# Issue #5 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

## ISSUE-5-DEC-001 — Scoped implementation authority

- Status: active for issue #5 delivery; human merge decision remains separate.
- Authority/source: actual human request to implement issue #5 using the defined
  workflow, current session, 2026-11-04; no chat permalink exists.
- Scope: read-only state/info/catalog tools, tests, documentation, independent
  review and PR. No deployment, physical device calls, merge, license or
  publication permission. Does not authorize #6–#14.
- Rationale supplied: follow defined workflow; no additional rationale supplied.
- Affected: C5-01–10. Supersession: none; other issue approvals are not reused.
- Propagation: coordinator passes this and DEC-001–007, ISSUE-2/3/4 references to
  implementer and reviewer.

## ISSUE-5-DEC-002 — Read surface, freshness and error mapping

- Status/authority: active agent technical baseline pending review/human merge.
- Source: requirements packet for #5 (P1, P6, P7, P9); not human-confirmed.
- Decision: three read tools (`wled_get_state`, `wled_get_effects`,
  `wled_get_palettes`). State and info are never cached; each call reads fresh
  under one deadline, not an atomic snapshot. Unreported capabilities are `null`,
  not `false`. Device/response problems are envelope errors using existing codes.
  A 4th color channel is trimmed only for a proven RGB-only segment.
  Diagnostics cover server version and unknown capabilities (partial OPS-04).
- Conditions: no setters, no hardware claim. Revalidate on firmware observations.
- Affected: C5-01/02/07–10, T02/T15.

## ISSUE-5-DEC-003 — Catalog identity, placeholders and optional fxdata

- Status/authority: active agent technical baseline; not human-confirmed.
- Source: packet P2, P4; pinned firmware source to be checked by the implementer.
- Decision: catalog ID is the array index of the device list, preserved without
  reindexing or hardcoded counts. Count mismatch warns. Placeholder slots are
  flagged and not name-matched. `/json/fxdata` is optional, never a name source;
  its failure or length mismatch yields `ok=true` with metadata unavailable.
- Affected: C5-03/05, T03.

## ISSUE-5-DEC-004 — Catalog cache and firmware-aware invalidation

- Status/authority: active agent technical baseline; not human-confirmed.
- Source: packet P3; uses the existing `catalog_cache_seconds` setting.
- Decision: per-device/per-kind cache with TTL (0 disables) and `refresh`. A
  non-refresh hit performs one fresh info read; a changed `ver`/`vid` invalidates;
  an info failure returns an error. Expired entries are never served. A failed
  refresh keeps the old entry. Alternative recorded: zero-HTTP hits.
- Affected: C5-06, T03.

## ISSUE-5-DEC-005 — Name resolution as internal shared helper

- Status/authority: active agent technical baseline; not human-confirmed.
- Source: packet P5.
- Decision: unique exact, then unique case-folded match; otherwise
  `AMBIGUOUS_NAME` with bounded candidates; no fuzzy auto-resolve. No new public
  parameter; end-to-end use belongs to #6.
- Affected: C5-04.

## ISSUE-5-DEC-006 — Raw info redaction

- Status/authority: active agent default, open to human change.
- Source: packet P8.
- Decision: remove `mac`, `ip` and `wifi.bssid` from `raw.info`, listing removed
  keys. Applies to runtime output, separate from commit privacy (DEC-005).
- Affected: C5-01.

## ISSUE-5-DEC-007 — Reads use the per-device lock

- Status/authority: active agent technical baseline; not human-confirmed.
- Source: implementer handoff for #5 (refines packet P1).
- Decision: read tools run through the per-device operation (lock plus one
  deadline). Reads on one device serialize and cannot interleave with a future
  write workflow; different devices stay independent; concurrent catalog misses
  are single-flight. `refreshed` means the caller requested a cache bypass;
  `source` states where the data came from.
- Affected: C5-06/09, T02.

## ISSUE-5-DEC-008 — Capability source in firmware output

- Status/authority: active agent observation from the pinned v0.15.1 source
  ([SOURCES.md](../SOURCES.md)); not verified on hardware.
- Decision: aggregate capability comes from `info.leds.lc`, per-segment
  capability from `info.leds.seglc` aligned by position only when its length
  equals the segment list. Bits RGB=1, W=2, CCT=4; RGB-only is `(lc & 7) == 1`.
  Unavailable effect slots are the literal `RSVD`.
- Conditions: revalidate on other firmware versions or real device output.
- Affected: C5-01/02/03.

## ISSUE-5-DEC-009 — Helper-level evidence accepted for ambiguous-name criterion

- Status: active for issue #5 acceptance only.
- Authority/source: actual human answer in the current session, 2026-11-04, to
  the question how the unmet criterion "ambiguous names return candidate matches"
  should be treated; no chat permalink exists.
- Scope: issue #5, the single acceptance item "Noncontiguous effect/palette IDs
  remain unchanged; ambiguous names return candidate matches". Not a general rule.
- Decision: the tested internal resolver (`AMBIGUOUS_NAME` with bounded
  candidates, ISSUE-5-DEC-005) is accepted as sufficient evidence for that item.
  Public name resolution through setters remains work for #6.
- Rationale supplied: none beyond the choice itself.
- Affected: C5-03/04, completion of #5. Supersedes: none; refines DEC-005's
  deferral for acceptance purposes only. Does not waive H01/H02 or other items.
- Propagation: coordinator passes this ID to the completion role.
