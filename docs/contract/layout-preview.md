# Static layout preview (`wled_preview_layout`, #29)

Requirements S3-PREVIEW-01 and S3-PREVIEW-02 ([STAGE-3.md](../STAGE-3.md)). Decisions:
[ISSUE-29-DEC-001](../decisions/issue-29.md) (agent technical proposals accepted by the
coordinator, not human decisions) and, for the 1D-only scope,
[ISSUE-27-DEC-001](../decisions/issue-27.md). Evidence:
[validation/issue-29.md](../validation/issue-29.md). Examples use synthetic IDs.

`wled_preview_layout` draws the segment layout of one configured 1D device as a static SVG so an
agent or a person can see boundaries, IDs, ranges, gaps and overlaps instead of reading a list.
It is a read-class, idempotent, non-destructive tool in every profile. It sends no write: the
module holds no write function, and a proposed layout is only passed to the existing pure layout
planner. Both transports use this same operation and contract.

## Request

| Field | Meaning |
| --- | --- |
| `device_id` | Required, 1-64 characters, a configured ID. |
| `segments` | Optional, 1-64 items of the same schema as `wled_replace_layout`, so a candidate list can be reused unchanged. Absent: draw the **observed** layout. Present: draw this **proposed** complete layout. |
| `allow_overlap` | Default `false`, same meaning as in `wled_replace_layout`. Only valid with `segments`. |
| `zone` | Optional stored zone ID or unique name ([zones.md](zones.md)); its ranges are drawn as bands. |
| `live_samples` | Default `false`. Colour the observed layout from one bounded `/json/live` read. Not valid with `segments`. |

The schema rejects unknown fields (there is no `dry_run`: every call is a preview).
`live_samples` together with `segments` and `allow_overlap` without `segments` are
`VALIDATION_ERROR` before any device or file read. The source label follows the request:
`data.source` is `observed` or `proposed`, and the picture's first line says the same.

## Delivery: a tool result, not a resource

The SVG is the string `data.svg` of the normal envelope with `data.media_type` set to
`image/svg+xml`. It is not an MCP resource and not image content: the server registers tools and
prompts only, a resource would need a new capability, a URI scheme and a client that forwards
resources, and both transports already return the tool result identically. The envelope carries
the payload twice (text content and `structuredContent`), which the size bound accounts for. An
agent or host that wants a file saves `data.svg` verbatim.

## Result (`data`)

| Key | Content |
| --- | --- |
| `source`, `media_type`, `svg` | As above. |
| `led_count`, `led_count_source` | LED count (nullable) and `info` or `unknown`. |
| `scale` | `{"viewbox_width": 1000, "leds_per_pixel": n}`. |
| `range_semantics` | `"[start,stop) exclusive stop"`. |
| `segments` | Per drawn lane: `id`, `start`, `stop`, `label`, `colour` (hex or `null`), `colour_mode`, `notes` and, for a proposed layout, `change` (`new`, `changed`, `unchanged`). |
| `omitted_segments` | Segments beyond the lane limit. |
| `gaps`, `overlaps` | Ranges, scoped to the drawn segment ranges; not inferred wiring. |
| `zone` | When requested: `id`, `name`, `status` (`drawn` or `topology_stale`) and the drawn `spans`. |
| `live` | When requested: `requested`, `status` and `sampling_step`. |
| `removed_segment_ids` | Proposed layout: active IDs the layout would remove (not drawn). |
| `colour_basis` | `state_slot_0`, `live_samples` or `plan`. |
| `approximations` | Fixed strings: `rgbw_white_added`, `cct_not_rendered`, `effects_not_simulated`, `live_rgb_brightness_scaled`, `unsampled_leds_unknown`. |
| `limits` | Fixed strings: 1D only, not calibrated colour, no animation, not a firmware simulator, effect and palette values not validated by the preview; plus one entry when the LED count is unknown. |
| `captured_at`, `observation` | Observed layout: UTC time of the reads. `observation` says that the reads are not atomic and nothing was written. |

`application` is `not_attempted` and `verification` `not_requested`. `device_id` is set only for a
configured device. The envelope keeps the tolerant output schema ([#130](https://github.com/descipar/wled-mcp/issues/130)).

## Sources

**Observed.** Under the device lock and one total deadline the tool reads `/json/state` and
`/json/info` and normalises them exactly as `wled_get_state` does. `/json/live` is read only with
`live_samples`. Zero-length inactive segments are omitted. No raw info, host, address, MAC or
firmware string is rendered or returned.

**Proposed.** The tool builds the `wled_replace_layout` request (with `dry_run`) and runs the
existing planner `build_layout_plan` over the same fresh read, with no catalog read. Planner
refusals (stop beyond the LED count, duplicate IDs, overlap without `allow_overlap`, a new ID
without colours, more segments than the device maximum, unknown LED count) are the normal
not-attempted error envelope with no `svg`, exactly as for a dry run of `wled_replace_layout`.
The drawing shows the planner's resolved ranges and colours, marks each lane `new`, `changed` or
`unchanged` and lists removed IDs in the caption and in `data`. `effect_name` and `palette_name`
are accepted and ignored with a warning: names are not resolved, effects are not rendered, and
the preview does not validate effects, palettes or option fields beyond what the planner already
checks. A proposed layout needs no `control` class because nothing is sent; this is the same
precedent as `wled_plan_zone`.

## Drawing and bounds

- One lane per segment with its ID, name (24 characters, truncated with an ellipsis), range
  `[start,stop)` (the stop is exclusive, stated in the picture), a scale axis with at most eleven
  labelled round ticks, a coverage row for gaps (dashed) and overlaps (marked), and a legend.
- A fixed `viewBox` width of 1000 maps any LED count to the same scale, stated as
  "1 LED = n px" or "1 px = n LEDs". There is no element per LED: unit ticks are one dashed line
  and only for strips of at most 120 LEDs.
- At most 64 lanes (the first 64 by ID; `omitted_segments` and a legend line report the rest), 256
  colour rectangles in total (live runs of adjacent equal colour are merged, the remainder is
  reported per lane as "n more runs not drawn") and 16 zone bands. Strings are truncated: segment
  name 24, zone name 32, other text 150 characters.
- `data.svg` is at most 48 KiB (UTF-8) and the whole `data` at most 128 KiB; exceeding either
  returns `INVALID_RESPONSE` and never a truncated or invalid SVG. The measured worst case (64
  lanes with 24 `&` characters in every name, 100 live runs per lane over 100,000 LEDs) is about
  46 kB, so the lane and rectangle limits keep a valid result under the cap.
- Gaps and overlaps come from the same sweep as the live snapshot, over the drawn valid ranges,
  including the trailing gap up to the LED count. They are labelled as scoped to the drawn ranges.
- The renderer is deterministic: the same model gives the same bytes; the capture time is in
  `data`, never in the SVG.

## Colour and approximation labels

| Case | Drawing | Label |
| --- | --- | --- |
| RGB | First colour slot as is | none |
| RGBW (four channels) | White added to each channel, clamped at 255 | `rgbw_white_added`, "white added" |
| CCT only (reported capability CCT without RGB) | Neutral grey, the `cct` value printed | `cct_not_rendered` |
| Segment off (`on` false or brightness 0) | Outline only | "off" |
| Colour unknown | Neutral grey | "colour unknown" |
| Brightness | Printed as text and applied as fill opacity only (floor 0.25); master power and brightness are printed in the header, not applied | none |
| Non-default `effect_id` | The static colour; the legend says "effect not simulated" once | `effects_not_simulated` |

Colours approximate the first colour slot (or the sampled live colours). They are not
calibrated, no effect, palette or animation is simulated and no animation element exists.

## Zone overlay and live samples

**Zone.** A stored zone ([zones.md](zones.md)) is resolved with the same lookup as the zone tools:
exact ID, then a unique case-folded name; an ambiguous name is `AMBIGUOUS_NAME` with candidates; a
zone without a part for this device is `VALIDATION_ERROR` before any device read. A part whose
stored `led_count` differs from the live count is not drawn and reported as
`status=topology_stale`. Otherwise each span is drawn verbatim as a band `[start,stop)`; a
`reversed` span is printed as metadata. The preview does not resolve the zone against segments,
does not check that segments tile the spans and does not claim alignment.

**Live samples.** The lane is coloured from the sampled runs of `wled_get_live_snapshot`'s decoder
and mapping ([live-snapshot.md](live-snapshot.md)), with the run budget set to the colour
rectangle limit. With a sampling step above one the legend says that unsampled LEDs are unknown.
Per-lane live statuses (`missing_samples`, `truncated`, `unknown_or_stale_geometry`, ...) become a
lane note. HTTP 404 or 501 from `/json/live` keeps `ok=true`, draws the state colours and adds the
warning "live samples unavailable (cause unknown)"; any other live failure is the existing safe
error envelope. The firmware's live RGB is brightness-scaled and folds white into RGB.

## 1D only

A matrix device (reported matrix, or a segment beyond one row) is refused with
`UNSUPPORTED_CAPABILITY` ("2D/matrix preview is not supported in this version") before anything
is rendered, for an observed and for a proposed layout. No 2D geometry is inferred. An unknown LED
count is drawn with the scale of the highest segment end, labelled, and listed in `limits`; a
segment beyond a known count is drawn clipped and marked, never invented.

## Security of the output

The renderer emits only `svg`, `title`, `desc`, `g`, `rect`, `line` and `text` and a fixed set of
presentation and geometry attributes. No script, style, image, link, animation or foreign object
exists, and the only URL-shaped string is the namespace `http://www.w3.org/2000/svg`. Every
foreign string (segment names, device and zone names, notes) passes one sanitiser: control
characters become spaces, format, surrogate and unassigned code points (which include the
bidirectional controls) are dropped, whitespace is collapsed and the text is truncated, then
escaped. Foreign strings are placed in element content only, never in an attribute. Numbers come
from integers or clamped floats and colours from validated hexadecimal digits. The output
contains no host, address, MAC, firmware string or raw state; the configured `device_id` and a
zone ID or name the caller can already read may appear.

## Access

The tool is registered in the `read-only`, `control` and `full` profiles, and a device capped at
`read` can still be previewed ([profiles.md](profiles.md)). Restricted deployments therefore keep
observation and reach no write path through it. There is no arbitrary endpoint forwarding,
discovery or file write; the zone store is read only.

## Errors

| Condition | Result |
| --- | --- |
| Unknown device | `UNKNOWN_DEVICE`, `device_id` null |
| Matrix or segment beyond one row | `UNSUPPORTED_CAPABILITY`, no `svg` |
| `live_samples` with `segments`, `allow_overlap` without `segments`, zone without a part for the device, unknown zone | `VALIDATION_ERROR`, no `svg` |
| Ambiguous zone name | `AMBIGUOUS_NAME` with `candidates` |
| Planner refusal of a proposed layout | The planner's `VALIDATION_ERROR` or `UNSUPPORTED_CAPABILITY`, no `svg` |
| Unreachable, timeout, malformed state or live data, HTTP error other than 404/501 on live | The existing safe error codes |
| Output over the bound | `INVALID_RESPONSE` |

## Not in this version

2D or matrix drawing, effect, palette or animation rendering, calibrated colour, a graphical
editor, preview of scenes, groups or presets, polling or stored previews, image formats other
than SVG, MCP resources and image content, and any write or `dry_run` path.
