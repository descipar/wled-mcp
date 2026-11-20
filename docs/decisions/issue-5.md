# Issue #5 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

## ISSUE-5-DEC-001 — Scoped implementation authority

- Status: active for issue #5 delivery; human merge decision remains separate.
- Authority/source: human request to implement issue #5 using the defined workflow, current
  session, 2026-11-04.
- Scope: read-only state/info/catalog tools, tests, documentation, independent review and PR.
  No deployment, physical device calls, merge, license or publication; does not authorize
  #6–#14.

## ISSUE-5-DEC-002 — Read surface, freshness and error mapping

- Status/authority: active agent technical baseline pending review/human merge.
- Decision: three read tools (`wled_get_state`, `wled_get_effects`, `wled_get_palettes`).
  State and info are never cached; each call reads fresh under one deadline (not an atomic
  snapshot). Unreported capabilities are `null`, not `false`. Problems are envelope errors
  with existing codes. A 4th color channel is trimmed only for a proven RGB-only segment.
  Diagnostics cover server version and unknown capabilities (partial OPS-04).

## ISSUE-5-DEC-003 — Catalog identity, placeholders and optional fxdata

- Status/authority: active agent technical baseline; not human-confirmed.
- Decision: catalog ID is the array index of the device list, preserved without reindexing.
  Count mismatch warns. Placeholder slots are flagged and not name-matched. `/json/fxdata`
  is optional, never a name source; failure yields `ok=true` with metadata unavailable.

## ISSUE-5-DEC-004 — Catalog cache and firmware-aware invalidation

- Status/authority: active agent technical baseline; not human-confirmed.
- Decision: per-device/per-kind cache with TTL (`catalog_cache_seconds`, 0 disables) and
  `refresh`. A non-refresh hit performs one fresh info read; changed `ver`/`vid`
  invalidates; an info failure returns an error. Expired entries are never served; a failed
  refresh keeps the old entry.

## ISSUE-5-DEC-005 — Name resolution as internal shared helper

- Status/authority: active agent technical baseline; not human-confirmed.
- Decision: unique exact, then unique case-folded match; otherwise `AMBIGUOUS_NAME` with
  bounded candidates; no fuzzy auto-resolve. No new public parameter; end-to-end use is #6.
- Closed out by #149: `wled_patch_segments` and `wled_replace_layout` accept names through
  this resolver; see [segment names](../contract/segment-names.md).

## ISSUE-5-DEC-006 — Raw info redaction

- Status/authority: active agent default, open to human change.
- Decision: remove `mac`, `ip` and `wifi.bssid` from `raw.info`, listing removed keys
  (runtime output, separate from commit privacy, DEC-005).

## ISSUE-5-DEC-007 — Reads use the per-device lock

- Status/authority: active agent technical baseline; not human-confirmed.
- Decision: read tools run through the per-device operation (lock plus one deadline); reads
  on one device serialize, different devices stay independent, concurrent catalog misses are
  single-flight. `refreshed` means a cache bypass was requested; `source` states provenance.

## ISSUE-5-DEC-008 — Capability source in firmware output

- Status/authority: active agent observation from the pinned v0.15.1 source
  ([SOURCES.md](../SOURCES.md)); not verified on hardware.
- Decision: aggregate capability from `info.leds.lc`, per-segment from `info.leds.seglc`
  aligned by position only when its length equals the segment list. Bits RGB=1, W=2, CCT=4;
  RGB-only is `(lc & 7) == 1`. Unavailable effect slots are the literal `RSVD`.

## ISSUE-5-DEC-009 — Helper-level evidence accepted for ambiguous-name criterion

- Status: active for issue #5 acceptance only.
- Authority/source: human answer, current session, 2026-11-04.
- Scope: the single acceptance item "Noncontiguous effect/palette IDs remain unchanged;
  ambiguous names return candidate matches". Not a general rule.
- Decision: the tested internal resolver (`AMBIGUOUS_NAME`, ISSUE-5-DEC-005) is accepted as
  sufficient evidence for that item; public resolution through setters is #6. Does not waive
  H01/H02 or other items. Refines DEC-005's deferral for acceptance purposes only.
