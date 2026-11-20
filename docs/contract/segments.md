# Capability-aware segments, CCT and 2D layouts (issue #19)

Contract for [issue #19](https://github.com/descipar/wled-mcp/issues/19). It extends
[`wled_get_state`](../TOOL-CONTRACT.md#read-tools-state-and-catalogs-implemented-in-5) and the [segment
tools](../TOOL-CONTRACT.md#segments-schema-and-omissions) `wled_patch_segments` and `wled_replace_layout`; everything
stated there applies unless this file says otherwise. Decisions:
[ISSUE-19-DEC-001](../decisions/stage-2.md#issue-19-dec-001--overlapping-segments) (human: overlap only with
`allow_overlap`), [ISSUE-19-DEC-002](../decisions/stage-2.md#issue-19-dec-002--segment-features-not-exposed) (human:
`rpt`, `fxdef`, matrix/panel configuration and `i` not exposed) and
[ISSUE-19-DEC-003](../decisions/stage-2.md#issue-19-dec-003--technical-defaults-for-the-capability-model-and-segment-fields)
(coordinator, technical defaults). Evidence: [validation/stage-2-core.md](../validation/stage-2-core.md) (mock and source only).
`wled_store_preset` takes the same fields under their wire keys
([presets.md](presets.md#supplied-state-wled_store_preset)); bundle import and export are unchanged (TD-19-10).

## Capability model

`src/wled_mcp/capabilities.py` derives every capability fact from the same fresh `/json/state` and `/json/info` reads a
tool already makes. It is pure (no extra HTTP, no cache) and never decides by product name or firmware version (DEC-020,
TD-21-6); the firmware tier of #21 is not an input.

| Fact | Evidence | Unknown |
| --- | --- | --- |
| Per-segment color capability | `state.seg[].lc` (source `state_lc`); else the position-aligned `info.leds.seglc` entry when that list has one integer per state segment (source `info_seglc`) | `null`, never `false` |
| Device aggregate | `info.leds.lc` (integer) | `null` |
| Matrix size | `info.leds.matrix` with exactly the keys `w` and `h`, both positive integers | `null` (a 1D build, a build without 2D support, or a malformed value) |
| Uniform capability | `info.leds.lc` when every active segment reports exactly that value (for new or moved ranges) | `null`, also for an empty segment list |

Capability bits (FX.h `SEG_CAPABILITY_*`): RGB `0x01`, white `0x02`, CCT `0x04`. A `seg[].lc` value counts only when it
is an integer 0-255 (booleans rejected); otherwise it is ignored with a warning and the next source applies. An
`info.leds.seglc` list counts only when every entry is in the same range. The bundle 2D rule of
[ISSUE-18-DEC-003](../decisions/stage-2.md#issue-18-dec-003--technical-defaults-for-restore-supplied-state-save-and-bundles)
(startY/stopY entries blocked unless source and target matrix are both reported and equal) and the `cct` warning use
`parse_matrix` from this module; the bundle format is unchanged.

Write-side switch: `wled_patch_segments`, `wled_replace_layout` and `wled_store_preset` use the evidence chain above, so
`seg[].lc` alone is per-segment evidence (pinned by `test_write_side_uses_the_seg_lc_chain_without_seglc`). The
`info.leds.lc` fallback for an existing unchanged range is kept (ISSUE-6-DEC-003).

## `wled_get_state` additions

All additions are optional output fields; nothing is removed or renamed.

`data.capabilities.matrix`: `{"width": w, "height": h}` from `info.leds.matrix`, else `null`. A present but malformed
value adds a warning. Absence is not listed in `diagnostics.unknown_capabilities`, because the firmware omits the key on
every 1D device.

`data.capabilities.segment_color_capability_reported` is `true` when every segment has per-segment evidence from either
source.

Each entry of `data.state.segments[]` keeps its stage-1 fields and adds, after `name`, `color_capability_source`
(`state_lc`, `info_seglc` or `null`: which evidence produced `reported_color_capability`) and the fields of the
[request table](#request-fields) under their read names (`cct`, `custom1`-`custom3`, `check1`-`check3`,
`sound_simulation`, `segment_set`, `map_1d_2d`, `freeze`, `blend_mode`; `start_y`, `stop_y`, `reverse_y`, `mirror_y`,
`transpose` only on a matrix). A field is the wire value when the key is present and well-typed within the firmware
storage type (0-255; `custom3` 0-31; `start_y`/`stop_y` 0-65535; booleans), else `null`, and a present value of the
wrong type or outside the bound adds a warning. The stricter write bounds belong to the setters (ISSUE-19-DEC-003
TD-19-2).

`reported_color_capability` keeps its `{rgb, white, cct}` shape and follows the evidence chain. The trimming of a zero
fourth color channel uses only `info.leds.seglc` evidence, so `colors` and `color_channels` are unchanged for every
device.

## Write rules (second pull request)

Every rule below is checked for the complete request before the first POST and identically in a dry run
(`VALIDATION_ERROR` or `UNSUPPORTED_CAPABILITY`, zero POSTs). The rules of
[TOOL-CONTRACT.md](../TOOL-CONTRACT.md#segments-schema-and-omissions) (patch versus replace, omitted fields are not
resets, plan and dry run, verification, uncertain writes without replay) are unchanged. No rule reads the firmware
version or the tier of #21 (DEC-020, TD-21-6).

### Request fields

`wled_patch_segments` (`SegmentPatch`) and `wled_replace_layout` (`LayoutSegment`) take the same optional fields;
`wled_store_preset` (`SuppliedSegment`) takes them under the wire key. No field is required by the schema (TD-19-1).

| Field | Wire key | Bounds | Evidence needed |
| --- | --- | --- | --- |
| `cct` | `cct` | 0-255 (no Kelvin input) | CCT bit 0x04 (below) |
| `custom1`, `custom2` | `c1`, `c2` | 0-255 | field presence |
| `custom3` | `c3` | 0-31 | field presence |
| `check1`-`check3` | `o1`-`o3` | boolean | field presence |
| `sound_simulation` | `si` | 0-3 | field presence |
| `segment_set` | `set` | 0-3 | field presence |
| `map_1d_2d` | `m12` | 0-4 | field presence |
| `freeze` | `frz` | boolean | field presence |
| `blend_mode` | `bm` | 0-16 | field presence |
| `start_y`, `stop_y` | `startY`, `stopY` | integers, supplied together | matrix |
| `reverse_y`, `mirror_y`, `transpose` | `rY`, `mY`, `tp` | boolean | matrix |

Request level, both segment tools only: `allow_overlap` (boolean, default `false`). Custom sliders and checks have
effect-specific meanings; only the ranges are checked.

### Evidence

- **Field presence (TD-19-5).** An option is settable only when the fresh readback of the target segment carries its
  wire key; for a new ID every active segment must carry it (an empty segment list proves nothing). This covers older
  firmware and builds without a feature without a version gate. Otherwise `UNSUPPORTED_CAPABILITY` naming the key.
- **Matrix.** `start_y`, `stop_y` and the orientation fields need `info.leds.matrix`; on a 1D device they are
  `UNSUPPORTED_CAPABILITY`.
- **CCT (TD-19-3, TD-19-4).** An existing range whose bounds stay the same needs the CCT bit in its per-segment
  capability (`state_lc`, else `info_seglc`); the aggregate `info.leds.lc` alone never suffices. A new or moved range (X
  or rows changed) needs the uniform rule: `info.leds.lc` is an integer, every active segment reports exactly that
  capability, and it contains the CCT bit. Otherwise `UNSUPPORTED_CAPABILITY`, for the whole request.
- **Colors (TD-19-3, AC-19-06).** The channel width follows the white bit: with white 4 channels, RGB without white 3;
  the CCT bit does not change the width. A white-only range (white, no RGB) takes 4 channels with RGB 0 (`[0, 0, 0,
  W]`). Never padded or trimmed. An existing unchanged range uses its per-segment capability, else the aggregate
  (ISSUE-6-DEC-003). A moved range keeps three channels on per-segment RGB-only evidence; any other width needs the
  uniform rule. A new range keeps the RGB-only rule (ISSUE-7-DEC-004), else the uniform rule. With mixed segment
  capabilities a new or moved RGBW, white-only or CCT range stays refused.
- **Residual risk.** The uniform rule proves the capability of the pixels the active segments cover. Pixels outside
  every active segment (on another bus) are not proven; a new range there can read back with a different capability and
  is then a verification mismatch, never a silent success.

### Matrix geometry (TD-19-7)

On a matrix `start`/`stop` are X columns: `0 <= start < stop <= width`, and `0 <= start_y < stop_y <= height`; a
violation is `VALIDATION_ERROR` before any POST (AC-19-08). 1D devices are unchanged.

- Omitted rows are preserved: a patch that changes only `start`/`stop` sends no `startY`/`stopY`, and the firmware keeps
  them (`elem[key] | seg.key`).
- The firmware clears a segment name when the requested `start`/`stop` differ from the current ones, before clamping; a
  rows-only change keeps the name. The existing name is therefore resent for an X change only (`targeted_compensation`).
- A replace segment that does not exist yet needs explicit `start_y` and `stop_y` (planner rule, not a schema
  `required`; `VALIDATION_ERROR`).
- A trailing strip (a range starting at or after `width * height`, indexed after the matrix) is read and preserved when
  its `start`/`stop` and rows stay the same. Creating one, moving one, changing its rows, or moving a matrix range into
  it is `UNSUPPORTED_CAPABILITY`.
- Overlap is rectangle intersection: X ranges and rows both intersect. Trailing strips compare by index only. When the
  rows of an active segment on a matrix are unknown, a geometry change or overlap listing is `UNSUPPORTED_CAPABILITY`.

### Overlap opt-in (ISSUE-19-DEC-001)

Without `allow_overlap` overlap is rejected (rectangles on a matrix): a patch whose range change overlaps another active
segment, or a replace layout that overlaps itself, is `VALIDATION_ERROR` and the message names the opt-in. With
`allow_overlap=true` overlap is permitted and the plan adds:

- `overlaps`: every overlapping pair of the resulting active layout, lower ID first;
- `render_order`: the active IDs bottom to top (a higher slot is drawn on top, blended with its `blend_mode`).

The replace ordering still avoids every intermediate overlap that the final layout does not contain. `blend_mode` is
settable with field presence, independent of the opt-in. `wled_store_preset` and the bundles have no opt-in; overlap
stays rejected there.

### Plan, defaults and warnings

- `capability_evidence` (patch and replace plan, dry run and live): present when the request sets a #19 field; one entry
  `{"id", "field", "evidence"}` per supplied field, `evidence` one of `state_lc`, `info_seglc`, `uniform` (CCT),
  `field_present` or `matrix`. Color evidence is not listed.
- `resolved_segments` carries the #19 fields (requested value, else the current one) in the order of the read model.
- Replace create steps (TD-19-6) send, in addition to the defaults of
  [TOOL-CONTRACT.md](../TOOL-CONTRACT.md#layout-replacement-implemented-in-7) and `frz=false`: `cct` 127, `c1`/`c2` 128,
  `c3` 16, `o1`-`o3` false, `si` 0, `set` 0, `m12` 0 and `bm` 0, each only where every active segment reports the key;
  on a matrix also the requested `startY`/`stopY` and `rY`/`mY`/`tp` false. Supplied values replace the defaults (with
  the evidence above).
- `inherited_unexposed_state` lists only the keys a reused slot keeps because no default could be sent (`cct`,
  `c1`-`c3`, `o1`-`o3`, `si`, `set`, `m12`, `bm`); when every key is reset there is no warning.
- `freeze=true` adds a warning: turning the master on (from off) unfreezes every segment (`json.cpp` L389-391).
- The tools never send `len`; the firmware reads `len` only when `stop` is absent, so no payload can carry conflicting
  bounds. Patch payloads send only the supplied fields (AC-19-13).

Verification covers every sent wire key on readback. An ACKed write the firmware did not apply keeps the outcome
mappings of the segment tools (`wled_patch_segments` `unknown/mismatch`, a failed replace step after verified steps
`applied/mismatch`, a lost readback after a timeout `unknown/unknown` with `WRITE_OUTCOME_UNKNOWN`), and nothing is
replayed.

## Source evidence (WLED v16.0.1)

Pinned WLED source tag `v16.0.1`, commit `29b389df1c1aaec6ff53aea742d17063b985906c` (the WLED 16 pin in
[SOURCES.md](../SOURCES.md#issue-66-wled-16-preset-evidence)). Source review only; no hardware observation.

| Fact | Source |
| --- | --- |
| `serializeSegment` emits `lc`, `cct`, `set`, `frz`, `c1`-`c3`, `o1`-`o3`, `si`, `m12`, `bm` for every segment, and `startY`/`stopY`/`rY`/`mY`/`tp` only when `strip.isMatrix` | `wled00/json.cpp` L574-643 |
| `serializeInfo` emits `leds.matrix {w, h}` only when `strip.isMatrix`; `leds.seglc` (deprecated in favor of `state.seg[].lc`) per active segment in order; `leds.lc` as the bitwise OR | `wled00/json.cpp` L723-745 |
| `deserializeSegment` reads omitted keys from the current segment (`elem[key] \| seg.key`), so an omitted Y bound or option is kept | `wled00/json.cpp` L116-123, L156-165, L201-203, L302-312 |
| `c3` is constrained to 0-31; `m12` to 0-7 in `setGeometry` | `wled00/json.cpp` L303-305; `wled00/FX_fcn.cpp` L477 |
| `setGeometry` clamps X to the matrix width and Y to the height; a range starting at or after `width * height` is a trailing 1D strip bounded by the total LED count | `wled00/FX_fcn.cpp` L460-538 |
| A segment's capability is recomputed from the bus pixels it covers after a geometry change | `wled00/FX_fcn.cpp` `refreshLightCapabilities` L1027ff |
| Segment defaults: `cct` 127, `c1`/`c2` 128, `c3` 16, checks false, `bm` 0 | `wled00/FX.h` L42-48, L564-586 |
| The name is cleared when the requested `start`/`stop` differ from the current ones (before `setGeometry` clamps them); `si` and `set` are constrained to 0-3 | `wled00/json.cpp` L144-151, L277-278 |
| `cct` is applied by `setCCT` (values above 255 are Kelvin, not exposed); `bm` is stored as sent; turning the master on unfreezes every segment | `wled00/json.cpp` L201-203, L312, L389-391; `wled00/FX_fcn.cpp` L554-566 |
| 17 blend modes (0-16); an unsupported value renders as mode 0 | `wled00/FX_fcn.cpp` L1416-1429 |
| `refreshLightCapabilities` walks rows `startY..stopY` at `x + width * y`, also for a trailing strip | `wled00/FX_fcn.cpp` L1027-1044 |
