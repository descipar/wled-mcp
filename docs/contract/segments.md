# Capability-aware segments, CCT and 2D layouts (issue #19)

Contract for [issue #19](https://github.com/descipar/wled-mcp/issues/19). It extends
[`wled_get_state`](../TOOL-CONTRACT.md#read-tools-state-and-catalogs-implemented-in-5) and the
[segment tools](../TOOL-CONTRACT.md#segments-schema-and-omissions)
`wled_patch_segments` and `wled_replace_layout`; everything stated there applies unless
this file says otherwise.
Decisions: [ISSUE-19-DEC-001](../decisions/issue-19.md#issue-19-dec-001--overlapping-segments)
(human: overlap only with `allow_overlap`),
[ISSUE-19-DEC-002](../decisions/issue-19.md#issue-19-dec-002--segment-features-not-exposed)
(human: `rpt`, `fxdef`, matrix/panel configuration and `i` not exposed) and
[ISSUE-19-DEC-003](../decisions/issue-19.md#issue-19-dec-003--technical-defaults-for-the-capability-model-and-segment-fields)
(coordinator, technical defaults). Evidence: [validation/issue-19.md](../validation/issue-19.md)
(mock and source only).

Status: the first pull request delivers the capability model and the read side below.
No write payload, validation outcome or bundle behavior changes with it; the setters,
the matrix write rules and the overlap opt-in follow in the second pull request and
will be added to this file then.

## Capability model

`src/wled_mcp/capabilities.py` derives every capability fact from the same fresh
`/json/state` and `/json/info` reads a tool already makes. It is pure (no extra HTTP,
no cache) and never decides by product name or firmware version (DEC-020, TD-21-6); the
firmware tier of #21 is not an input.

| Fact | Evidence | Unknown |
| --- | --- | --- |
| Per-segment color capability | `state.seg[].lc` (source `state_lc`); else the position-aligned `info.leds.seglc` entry when that list has one integer per state segment (source `info_seglc`) | `null`, never `false` |
| Device aggregate | `info.leds.lc` (integer) | `null` |
| Matrix size | `info.leds.matrix` with exactly the keys `w` and `h`, both positive integers | `null` (a 1D build, a build without 2D support, or a malformed value) |
| Uniform capability | `info.leds.lc` when every active segment reports exactly that value (used by the second pull request for new or moved ranges) | `null` |

Capability bits (FX.h `SEG_CAPABILITY_*`): RGB `0x01`, white `0x02`, CCT `0x04`. A
`seg[].lc` value counts only when it is an integer 0-255 (booleans rejected); otherwise
it is ignored with a warning and the next source applies. `parse_matrix` moved here from
the bundle code unchanged, so the bundle 2D rule of
[ISSUE-18-DEC-003](../decisions/issue-18.md#issue-18-dec-003--technical-defaults-for-restore-supplied-state-save-and-bundles)
(startY/stopY entries blocked unless source and target matrix are both reported and
equal) and the `cct` warning behave exactly as before; the bundle format is unchanged.

The write planners still use the stage-1 lookup (`info.leds.seglc` only, with the
`info.leds.lc` fallback for an unchanged range, ISSUE-6-DEC-003) until the second pull
request switches them to the evidence chain above.

## `wled_get_state` additions

All additions are optional output fields; nothing is removed or renamed.

`data.capabilities.matrix`: `{"width": w, "height": h}` from `info.leds.matrix`, else
`null`. A present but malformed value adds a warning. Absence is not listed in
`diagnostics.unknown_capabilities`, because the firmware omits the key on every 1D
device.

`data.capabilities.segment_color_capability_reported` is `true` when every segment has
per-segment evidence from either source (before: only from `info.leds.seglc`).

Each entry of `data.state.segments[]` keeps its stage-1 fields and adds, after `name`:

| Field | Wire key | Read bound | Notes |
| --- | --- | --- | --- |
| `color_capability_source` | - | `state_lc`, `info_seglc` or `null` | Which evidence produced `reported_color_capability` |
| `cct` | `cct` | 0-255 | White balance / color temperature value |
| `custom1`, `custom2` | `c1`, `c2` | 0-255 | Effect-specific sliders; meaning per effect metadata |
| `custom3` | `c3` | 0-31 | 5-bit slider in the firmware |
| `check1`-`check3` | `o1`-`o3` | boolean | Effect-specific options |
| `sound_simulation` | `si` | 0-255 | |
| `segment_set` | `set` | 0-255 | |
| `map_1d_2d` | `m12` | 0-255 | |
| `freeze` | `frz` | boolean | |
| `blend_mode` | `bm` | 0-255 | |
| `start_y`, `stop_y` | `startY`, `stopY` | 0-65535 | Present only on a matrix |
| `reverse_y`, `mirror_y`, `transpose` | `rY`, `mY`, `tp` | boolean | Present only on a matrix |

A field is the wire value when the key is present and well-typed within the read bound,
else `null`; a present value of the wrong type or outside the bound adds a warning
(the stage-1 pattern). Read bounds are the firmware storage types; the stricter write
bounds of ISSUE-19-DEC-003 TD-19-2 belong to the setters.

`reported_color_capability` keeps its `{rgb, white, cct}` shape and now follows the
evidence chain. The trimming of a zero fourth color channel still uses only
`info.leds.seglc` evidence, so `colors` and `color_channels` are unchanged for every
device; the two can differ only when `seg[].lc` exists and `info.leds.seglc` does not
line up.

## Source evidence (WLED v16.0.1)

Pinned WLED source tag `v16.0.1`, commit `29b389df1c1aaec6ff53aea742d17063b985906c`
(the WLED 16 pin recorded in [SOURCES.md](../SOURCES.md#issue-66-wled-16-preset-evidence)). Source review only;
no hardware observation.

| Fact | Source |
| --- | --- |
| `serializeSegment` emits `lc`, `cct`, `set`, `frz`, `c1`-`c3`, `o1`-`o3`, `si`, `m12`, `bm` for every segment, and `startY`/`stopY`/`rY`/`mY`/`tp` only when `strip.isMatrix` | `wled00/json.cpp` L574-643 |
| `serializeInfo` emits `leds.matrix {w, h}` only when `strip.isMatrix`; `leds.seglc` (marked deprecated in favor of `state.seg[].lc`) per active segment in order; `leds.lc` as the bitwise OR | `wled00/json.cpp` L723-745 |
| `deserializeSegment` reads omitted keys from the current segment (`elem[key] \| seg.key`), so an omitted Y bound or option is kept | `wled00/json.cpp` L116-123, L156-165, L201-203, L302-312 |
| `c3` is constrained to 0-31; `m12` to 0-7 in `setGeometry` | `wled00/json.cpp` L303-305; `wled00/FX_fcn.cpp` L477 |
| `setGeometry` clamps X to the matrix width and Y to the height; a range starting at or after `width * height` is a trailing 1D strip bounded by the total LED count | `wled00/FX_fcn.cpp` L460-538 |
| A segment's capability is recomputed from the bus pixels it covers after a geometry change | `wled00/FX_fcn.cpp` `refreshLightCapabilities` L1027ff |
| Segment defaults: `cct` 127, `c1`/`c2` 128, `c3` 16, checks false, `bm` 0 | `wled00/FX.h` L42-48, L564-586 |
