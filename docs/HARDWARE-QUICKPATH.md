# Hardware quick path: read-only H01/H02 over local stdio

Early, optional check that the implemented read tools match a real device, without
MCPHub, deployment or any write. It does not replace #11/#12; H03-H07 stay pending.
Requires explicit authorization for read-only access to one selected device.

## Setup (any machine)

1. `uv sync --frozen` on current `main`.
2. `mkdir -p runtime/h01-h02` and copy `examples/h01-h02.devices.example.toml` to
   `runtime/h01-h02/devices.toml` (git-ignored). Replace the placeholder address with
   the selected device. Real addresses and raw output never enter Git.
3. Record timers, other API clients, playlists and realtime inputs on the device.
   Record them; never disable them silently.

## Run

    uv run --frozen python scripts/hw_read_only_probe.py testdev

Calls only `wled_list_devices(probe=true)`, `wled_get_state`, `wled_get_effects`,
`wled_get_palettes`. The script refuses any other tool. Output: `runtime/h01-h02/out/`.

## Check

- H01: firmware, LED count, RGB/RGBW/CCT and segment capabilities from the real
  response; compare with the WLED UI info page.
- H02: effect and palette IDs/names (including high IDs and reserved entries),
  segment list/bounds/on/bri/colors, and `lc`/`seglc` capability interpretation match
  the UI. Run `wled_get_effects` once with `refresh=true` and observe freshness.
- Presets can be read with `wled_list_presets`/`wled_get_preset` (#9, mock-tested); the
  preset part of H02 stays pending until it is actually run.

## Record

Sanitized summary only (alias, firmware, LED count, capability bits, mismatches) in
VALIDATION.md. Mismatches against the v0.15.1 fixture assumptions become issues, not
silent fixes. Unrun checks stay explicitly pending.
