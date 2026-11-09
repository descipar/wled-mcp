# Effect search (`wled_search_effects`, #31)

Requirements S3-EFFECT-01 and S3-EFFECT-02 ([STAGE-3.md](../STAGE-3.md)). One read-only
tool searches the effects of **one configured device** by curated properties and returns the
device's own IDs and names with an explanation per result. It never writes: applying a result
is an explicit call of an existing control tool (for example `wled_patch_segments`) with the
returned ID. The class is `read` (every profile), identical on stdio and HTTP.

Delivery follows DEC-028: a small catalog that is right beats a wide one that might be wrong.
The catalog covers a handful of built-in effects; effects it does not list are simply not
searchable. This is not a claim to classify every effect.

## Request

All filters are optional and combined with AND. Extra fields are rejected.

| Field | Values | Meaning |
| --- | --- | --- |
| `device_id` | string, required | Configured device |
| `refresh` | bool, default false | Bypass the effect-list cache (as `wled_get_effects`) |
| `motion` | list of `static`, `calm`, `moderate`, `lively` | Effect motion is one of these |
| `flashing` | list of `none`, `occasional`, `frequent` | Worst-case flashing across the speed range |
| `colors_min`, `colors_max` | 0 to 3 | Colour slots the effect offers (0 = palette-driven) |
| `uses_palette` | bool | The effect offers a palette |
| `strip_length` | `short`, `medium`, `long` | Effect is recommended for that length |
| `min_visibility` | `low`, `medium`, `high` | Visibility at least this (ordinal) |
| `max_palette_saturation_need` | `low`, `medium`, `high` | Needs at most this saturated a palette (ordinal) |
| `strict` | bool, default true | Unknown properties exclude (true) or yield partial matches (false) |
| `min_confidence` | `recommended` (default) or `verified` | Lowest confidence that counts as known |
| `limit` | 1 to 50, default 20 | Maximum results |

There is no free-text or name query; look names up with `wled_get_effects`. Without filters
the covered effects of the device are listed. `strip_length` is a recommendation for rough
classes ("short" up to a few dozen LEDs, "long" several hundred); it is not measured.

## Properties, confidence and provenance

Every catalog property is `{value, confidence, basis, evidence}`. A property that is absent
is **unknown**; it is never guessed from the name.

| Property | Values | Highest confidence | Definition |
| --- | --- | --- | --- |
| `flashing` | `none`, `occasional`, `frequent` | verified | Worst case over speed/intensity: `frequent` for on/off alternation (strobe, blink), `none` when the effect function has no abrupt full-strip alternation at any setting. A comfort property, **not** a medical photosensitivity guarantee |
| `colors` | integer 0 to 3 | verified | Colour slots in the colour field of the effect's metadata string (`_data_FX_MODE_*` in FX.cpp); for effects without one, the colours the effect function reads |
| `uses_palette` | bool | verified | The metadata string offers a palette selection |
| `motion` | `static`, `calm`, `moderate`, `lively` | recommended | Subjective |
| `strip_length` | non-empty subset of `short`, `medium`, `long` | recommended | Subjective |
| `visibility` | `low`, `medium`, `high` | recommended | How well the effect reads at modest brightness; soft effects tend low. Curated judgement, not measured |
| `palette_saturation_need` | `low`, `medium`, `high` | recommended | How saturated a palette must be for the effect to be visible; pale palettes at low brightness hide effects that need `high` |

`confidence` is `verified` (checked against the pinned effect source or a recorded run) or
`recommended` (curated judgement). Subjective properties can **never** be `verified`; the
loader rejects such an entry. `basis` is `source_review`, `observed_run` or
`author_judgement`; a `verified` property needs `source_review` or `observed_run`. `evidence`
is required text naming the source or record. Visibility and palette saturation need
come from an owner remark in a recorded live check
([live-check-2026-11-08](../validation/live-check-2026-11-08.md)) and stay `recommended`.

## Matching and explanation

A property is **known** when it has a value with confidence at or above `min_confidence`.

- A known value that fails a filter excludes the effect in both modes.
- An unknown (or below-`min_confidence`) requested property excludes the effect when
  `strict=true`; with `strict=false` the effect is returned as `match: "partial"` and the
  property is listed under `unverified`. A subjective filter with `min_confidence=verified`
  therefore matches nothing and says why; it is not an error.
- Results are ordered `full` before `partial`, then by device ID. There is no relevance score.
  `total_matches` and `truncated` report the effect of `limit`.

Each result has the device's exact `id` and `name`, `match` (`full`/`partial`), `mapping`,
`matched[]` (property, requested value, effect value, confidence, basis), `unverified[]`,
and all known `properties`. `no_match` appears when `results` is empty, with a `reason`:
`no_curated_overlap`, `catalog_not_applicable`, `excluded_by_known_properties`,
`only_unverified_candidates`, `only_stale_candidates`, plus `detail` and counts.
The envelope is a success (`ok=true`) even without results; errors are device or transport
failures as in `wled_get_effects`. `note` repeats that subjective values are recommendations
and that `flashing` is no safety guarantee.

### Intersection with the device (IDs are not universal)

Catalog entries are matched against the device's effect list by exact name (no fuzzy
matching; `RSVD` placeholder slots never match):

- `exact`: the device lists the name at the catalog ID. Returned with the device ID.
- `id_changed`: the name occurs exactly once at another ID. Returned only with
  `strict=false`, as `partial`, with the device's ID and a `stale_reason`.
- Name conflict (the catalog ID holds a different name and the name occurs nowhere), duplicate
  names on the device, and effects absent from the device are never returned. The first two
  are listed (bounded to 10) under `diagnostics.stale_mappings` and `diagnostics.ambiguous`;
  absent effects are counted.

`diagnostics` also reports `covered_in_catalog`, `present_on_device` and
`device_effects_without_curation`. `/json/fxdata` is not used; a failure there does not affect
the search.

### Firmware

`catalog.firmware_match` is `reviewed` when `info.ver` equals a reviewed version exactly,
otherwise `unreviewed` (for example another 16.x or `16.0.1-custom`); exact name and ID
matches are still returned, with a warning. When the firmware is below the supported floor or
not recognizable (`compat.classify` returns `unsupported` or `unrecognized`,
[compatibility.md](compatibility.md)) the catalog is not applied: no results,
`no_match.reason=catalog_not_applicable`, `firmware_match=not_applicable` and a warning.
This is a search-result decision, not a request refusal.

## Catalog file

`src/wled_mcp/catalog_data/effect_properties.json`, shipped in the wheel and sdist
(`scripts/check_distribution.py` checks both). Top level: `schema_version` (integer; a
different value is rejected with a message naming both versions; the file is never
rewritten), `data_version` (date, bumped on every change), `property_notes`, `firmware`
(`reviewed` versions and `source` pin) and `effects` (`id`, exact `name`, `properties`).
Unknown properties, values, extra keys, duplicate IDs or names and the placeholder name are
rejected by the loader (pydantic, `extra=forbid`). An invalid file is a packaging error,
covered by a test, and the tool then fails with `INTERNAL_FAILURE`; it never skips silently.
Reviewed firmware: WLED 16.0.1, tag `v16.0.1` (see [SOURCES.md](../SOURCES.md)).

## Updating and contributing

The catalog is reviewed project data; there is no cloud fetch, account, telemetry or
runtime-editable override file (a later issue may add an override). To add or change an effect
open a pull request that:

1. takes the ID and exact name from the firmware source at a stated tag (`FX.h` `FX_MODE_*`
   and the `_data_FX_MODE_*` string of `FX.cpp`), one effect per entry, no bulk import from names;
2. sets a property only when it is defensible; otherwise omits it (unknown);
3. uses `verified` only with `source_review` or `observed_run` and an `evidence` that names the
   source (file, symbol, commit) or the record; subjective properties stay `recommended`;
4. bumps `data_version`, adds the effect to the test record of names and IDs in
   `tests/test_effect_search.py`, and adds one line to the change list below.

Review checks the ID/name pair against the pinned source, the evidence text per property and
that nothing subjective claims more than `recommended`. To add a firmware version to
`firmware.reviewed`, re-check every entry against that firmware's source first; a support-tier
promotion in `compat.py` and [compatibility.md](compatibility.md) is a separate change.

Change list:

- `2026-11-09`: initial catalog of 12 effects for WLED 16.0.1.

## Limits

Curated and small; subjective labels are not measured; `flashing` is not a safety guarantee;
no 2D properties; palettes are not searched (only a per-effect hint); no ranking. Mock and
loopback evidence only; no live device was used for this feature.
