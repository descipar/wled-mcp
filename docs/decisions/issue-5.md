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
