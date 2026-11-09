# Named physical lighting zones (`wled_list_zones`, `wled_plan_zone`, `wled_apply_zone`, #27)

Requirements S3-ZONE-01 and S3-ZONE-02 ([STAGE-3.md](../STAGE-3.md)). Decisions:
[ISSUE-27-DEC-001](../decisions/issue-27.md) (agent technical proposals accepted by the
coordinator, not human decisions). Evidence: [validation/issue-27.md](../validation/issue-27.md).
Examples use synthetic IDs.

A zone gives a physical region ("shelf, left side") a name and maps it to configured device
IDs and explicit LED ranges. An agent addresses it by ID or name, previews the exact device,
segment and range targets without any write, and applies segment fields that change only LEDs
inside the zone. Nothing is inferred from names, discovered, enrolled or silently
re-segmented. Delivery follows DEC-028: zones are reviewed files, the policy is conservative
and small.

## Tools

| Tool | Class | Purpose |
| --- | --- | --- |
| `wled_list_zones` | read | Local files only, no device I/O. Without arguments: summaries (`id`, `name`, part and span counts, devices with `in_inventory`), `invalid_count` and warnings (name collisions, `duplicate_mapping`, devices not in the inventory). With `zone` (ID or name): the stored document and `overlaps_zones`. |
| `wled_plan_zone` | read | Read-only preview. Reads fresh state of each device (at most four in flight) and resolves the zone. With `segments` it also runs the real `wled_patch_segments` planner. Sends no write. |
| `wled_apply_zone` | control | `segments` required. Preflights every device (resolution, planner, access ceiling), then writes each device through the verified write path. `dry_run` returns exactly the plan. |

All three are registered on stdio and Streamable HTTP alike (`create_server` is shared). The
read tools are served in every profile; `wled_apply_zone` only in `control` and `full`, and a
device capped below `control` is refused per device before any read of it. `wled_plan_zone`
still previews a read-capped device. `dry_run` does not lower the class.

### Request

| Tool | Fields |
| --- | --- |
| `wled_list_zones` | optional `zone` |
| `wled_plan_zone` | `zone` (ID or name, 1-128 chars), optional `segments`, `mode` `strict` (default) or `best_effort` |
| `wled_apply_zone` | `zone`, `segments`, `mode`, `dry_run` |

`segments` is a list with **exactly one** object of segment fields: `on`, `brightness`,
`colors`, `effect_id` or `effect_name`, `palette_id` or `palette_name`, `speed`, `intensity`,
`cct`, `custom1`-`custom3`, `check1`-`check3` (the scene entry allowlist, with the scene
validation). Every segment inside the zone receives the same fields; one object only because
several would address the same segments twice. `ids`, geometry (`start`, `stop`, `offset`,
`grouping`, `spacing`, `reverse`, `mirror`, `name`, ...) and master state (`on`, `brightness`,
`transition_ms` at the top level) are rejected: a zone apply never changes geometry and never
writes master state, which would light LEDs outside the zone.

## Zone document, format `wled-mcp.zone` 1

A local file `<data-dir>/zones/<id>.json`, one strict JSON document per zone, written by hand or
by tools outside this server (no save or delete tool in this version: geometry knowledge of an
installation is reviewed, not invented by an agent). It is read through the same store as
groups and scenes (0600/0700, symlinks refused, unusable files counted and never rewritten or
migrated) and versioned like them ([versioning](versioning.md#schema-evolution)).

```json
{
  "format": "wled-mcp.zone",
  "format_version": 1,
  "id": "shelf-left",
  "name": "Shelf, left side",
  "description": "optional, 1-256 characters",
  "parts": [
    {
      "device": "strip_a",
      "led_count": 150,
      "spans": [
        {"start": 100, "stop": 150, "reversed": true},
        {"start": 0, "stop": 20, "segment": 1}
      ]
    }
  ]
}
```

- `id` follows the definition-ID rule and is the file name; `name` is 1-128 characters.
- `parts`: 1-16, one per configured device (a device twice is rejected: merge its `spans`).
- `led_count` (required): the LED count of the device when the zone was written. It is the
  stale-topology anchor.
- `spans`: 1-16 `[start, stop)` LED ranges (exclusive stop, `0 <= start < stop <= led_count`),
  not overlapping within a part (adjacent is fine). File order is the zone's logical order.
  Optional `segment` (0-254) must match the live segment exactly; it cross-checks the range
  and never replaces it. Optional `reversed` is metadata (below).
- Bounds: 64 KiB, 100 zones. 1D only: `start_y` and similar keys are rejected as unknown, and
  a matrix device is `UNSUPPORTED_CAPABILITY`. No address, host or credential field exists.

## Lookup

`zone` is the exact ID first, then a unique case-folded name. Two zones with the same
case-folded name are `AMBIGUOUS_NAME` with bounded candidates (`data.candidates`); selecting
by ID still works. When a value is one zone's ID and another zone's name, the ID wins and a
warning says so. `wled_list_zones` warns about name collisions and about two zones that map the
same range of the same device (`duplicate_mapping`, an alias, not an error).

## Resolution and the existing-segments policy

Zone operations use the device's **existing active segments only** and never change geometry.
After the fresh read, under the device lock, each part is resolved:

1. The live LED count must equal `led_count`, else `topology_stale` (unknown count:
   `UNSUPPORTED_CAPABILITY`).
2. A matrix device is `UNSUPPORTED_CAPABILITY`.
3. For each span, the active segments that intersect it must all lie fully inside it and tile
   it without a gap. Otherwise the call is refused before any write:

| `data.problem.reason` | Meaning | `layout_change_required` |
| --- | --- | --- |
| `span_unsegmented` | No active segment covers the span | true |
| `boundary_crossing` | A segment straddles the zone edge, is larger than the zone, or overlaps from outside; the segment ID and range are named | true |
| `span_gap` | Some LEDs of the span are covered by no segment | true |
| `segment_mismatch` | The `segment` hint names another segment than the range resolves to | false |
| `topology_stale` | Live LED count differs from `led_count` | false |
| `topology_changed` | The layout changed between preview and write (below) | false |
| `matrix_unsupported`, `led_count_unknown` | See above | false |

These are `VALIDATION_ERROR` with the reason in `data` (no new error code); the exceptions
are `UNSUPPORTED_CAPABILITY`, `UNKNOWN_DEVICE`, `AMBIGUOUS_NAME`, `ACCESS_DENIED` and the
usual write outcomes. `data.problem.layout_hint` states the zone span and the offending live
segment ranges for information. When a layout change is required, the caller reviews and
makes it explicitly (`wled_replace_layout` or a range change with `wled_patch_segments`) and
previews the zone again; the zone tools never generate or apply a layout. This is what keeps a
partial-zone command from affecting LEDs outside the requested region: only segments wholly
inside the zone are patched.

A resolved part reports (`targets[].zone_target`): `segment_ids` (sorted, what the patch
addresses), `spans` in logical order with each segment's `id`, `start` and `stop`,
`flow_reversed`, `warnings` (overlaps already present in the live layout) and
`layout_changes: false`. `reversed` is reporting metadata: a reversed span lists its segments
from the high LED end first and carries `flow_reversed`; the apply never sets a segment
`reverse`. A caller that wants a reversed effect direction sets `reverse` explicitly with
`wled_patch_segments`.

### Write-time guard

The preview is not a reservation, and segment IDs are not stable. The apply resolves each part
again after its fresh read under the device lock; if the resolution differs from the preflight
(or no longer resolves) that device fails with `topology_changed`, `application`
`not_attempted`, nothing sent and no retry. Other devices keep their own outcome.

## Plan and apply behavior

The tools reuse the scene machinery: one target per part, `plan_device` for the read and the
planner, `apply_device` and `Resources.write_verified` for the verified write (a segment step
only), strict by default (`best_effort` skips failing devices), at most four devices in
flight, 16 devices at most. The per-device and aggregate outcomes, `WRITE_OUTCOME_UNKNOWN` and
`VERIFICATION_MISMATCH` are those of `wled_apply_scene`
([groups-scenes.md](groups-scenes.md)): not atomic, not synchronized, no rollback,
compensation or replay.

`data.zone` holds `{id, name}`, `data.zone_document` the stored document, and the plan adds,
for information only and without expanding anything: `overlaps_zones` (other zones whose
ranges intersect this one on a shared device) and `overlaps_groups` (stored groups that list a
device of the zone with segments the zone resolved to). One call applies one zone, so no other
zone or group is touched.

## Not in this version

Zone targets inside scenes and groups (needs scene `format_version` 2), a zone save or delete
tool, a generated layout proposal, 2D or matrix zones, master power or brightness, SVG
rendering ([#29](https://github.com/descipar/wled-mcp/issues/29)) and any hardware claim.
A scene or group may already name the segment IDs a zone resolved to; the existing planners and
their one-device-once rule then apply unchanged.
