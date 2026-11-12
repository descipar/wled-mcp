# WLED feature coverage

This list compares WLED's own feature surface with what this unofficial server
delivers. Each row is one WLED feature with exactly one status, so a reader can see
what is supported, what is planned and what is deliberately left out. Two figures
summarize the rows; they are generated from the tables, never typed by hand.

**Basis:** WLED source tag `v16.0.1`, commit `29b389df1c1aaec6ff53aea742d17063b985906c`
(the WLED 16 pin recorded in [SOURCES.md](SOURCES.md#issue-66-wled-16-preset-evidence):
`wled00/json.cpp`, `wled00/wled_server.cpp`, `wled00/set.cpp`, `wled00/ws.cpp`), and the
official [WLED JSON API documentation](https://kno.wled.ge/interfaces/json-api/). The
features come from WLED's interfaces, not from this server's tool list or any
home-automation integration. Supported firmware starts at WLED 16.0.0
([DEC-020](DECISIONS.md#dec-020--support-and-version-policy)).

A status describes this server's implementation against that source, checked by mocked
tests. It is not a hardware compatibility claim. Under DEC-020, firmware is in one of
three tiers: tested (hardware evidence), expected (source-reviewed and mock-tested) and
unknown (no claim). Hardware evidence exists for one RGB controller on WLED 16.0.1 only
([VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-2026-11-06)); all other
devices and versions are at most expected.

## Figures

<!-- wled-coverage:start -->
**WLED coverage: 48 %** (42.5 of 89 features). **Planned-scope coverage: 60 %** (42.5 of 71 features, excluded rows removed).

| Area | Features | Supported | Partial | Planned | Unplanned | Excluded | Planned scope | WLED overall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Master state (STATE) | 13 | 3 | 2 | 0 | 8 | 0 | 31 % | 31 % |
| Segments (SEG) | 25 | 22 | 0 | 0 | 0 | 3 | 100 % | 88 % |
| Effects and palettes (CAT) | 6 | 3 | 0 | 0 | 2 | 1 | 60 % | 50 % |
| Presets and playlists (PRESET) | 13 | 8 | 1 | 0 | 3 | 1 | 71 % | 65 % |
| Information and diagnostics (INFO) | 9 | 4 | 2 | 0 | 3 | 0 | 56 % | 56 % |
| Configuration (CFG) | 12 | 0 | 0 | 0 | 8 | 4 | 0 % | 0 % |
| System and maintenance (SYS) | 5 | 0 | 0 | 0 | 0 | 5 | n/a | 0 % |
| Realtime and streaming (RT) | 5 | 0 | 0 | 0 | 1 | 4 | 0 % | 0 % |
| Usermods (UM) | 1 | 0 | 0 | 0 | 1 | 0 | 0 % | 0 % |
| **All** | 89 | 40 | 5 | 0 | 26 | 18 | 60 % | 48 % |
<!-- wled-coverage:end -->

Method:

- S = supported + 0.5 x partial. Every row weighs the same.
- WLED coverage = S / all rows.
- Planned-scope coverage = S / (all rows - excluded rows). Planned and unplanned rows
  stay in both denominators.
- Percentages are integers, rounded half up. An area without non-excluded rows shows
  "n/a" for its planned scope.
- The block above is written by `python scripts/check_coverage.py --update`. Without
  `--update` the script only checks, and CI fails when the block or the README line
  differs from the rows.

## Statuses

| Status | Meaning | Counts as |
| --- | --- | --- |
| supported | The server reads and, where WLED allows it, sets the feature. `Delivered by` names the tools or CLI commands. | 1 |
| partial | Only part of the feature is delivered, for example read but not write. `Delivered by` names the tools; Notes say what is missing. | 0.5 |
| planned | An open roadmap issue owns the feature. Link: that issue. | 0 |
| unplanned | No owning issue and no exclusion decision ([ISSUE-94-DEC-001](decisions/issue-94.md#issue-94-dec-001--unplanned-features-and-upload-exclusion-scope)). The status decides nothing about future scope. | 0 |
| excluded | A recorded decision keeps the feature out. Link: that decision. Excluded rows leave the planned-scope denominator only. | 0 |

## Granularity rules

1. One row per independently usable WLED function exposed by the JSON API, an HTTP
   route or another documented WLED interface.
2. Aliases and alternative encodings are not rows: `len` folds into segment bounds,
   hex/Kelvin/object color forms into segment colors, the `lx`/`ly` build option and the
   `"t"` toggle value into their base features, `/json/si` into the state and
   information reads, and the legacy `/win` HTTP API is an interface, not a feature
   ([ISSUE-19-DEC-002](decisions/issue-19.md#issue-19-dec-002--segment-features-not-exposed)).
3. Web UI pages and assets, and this server's own features (inventory, snapshots,
   dry run, transports, diagnostics), are not rows.
4. Raw passthrough counts only for read-only information: `raw.info` fields returned
   unnormalized make a read-only diagnostics row partial. A settable state key that is
   merely visible in `raw.state` is not support.
5. Reading but not writing a settable feature is partial.
6. A feature delivered by a CLI command counts like one delivered by an MCP tool; the
   reference is written `cli: wled-mcp <command>`.
7. Every top-level group of `/json/cfg` has a row: `id` W-CFG-10, `nw`/`ap`/`wifi`
   W-CFG-03, `eth` and the `hw` pin settings W-CFG-02, `hw.led.matrix` W-CFG-05, button
   and IR behavior in `hw` W-CFG-08, `light` W-CFG-11, `def` W-PRESET-13, `if.ntp`
   W-CFG-09, the other `if` groups and `dmx` W-CFG-06, `ol` W-CFG-12, `timers` W-CFG-04,
   `ota` and `pin` W-CFG-07, `um` W-UM-01; reading the whole file is W-CFG-01. The
   format markers `rev` and `vid` are not features.
8. Row IDs (`W-<AREA>-NN`) are stable. They are never renumbered, and a removed ID is
   not reused.

Columns: `Delivered by` lists backticked MCP tools or CLI commands, or `-`. `Link` is the
owning issue for planned rows and the decision for excluded rows.

## Master state

| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W-STATE-01 | Master power | `on` | supported | `wled_set_state`, `wled_get_state`, `wled_apply_scene` | - | Power rules in TOOL-CONTRACT.md. |
| W-STATE-02 | Master brightness | `bri` | supported | `wled_set_state`, `wled_get_state`, `wled_apply_scene` | - | Remembered and effective brightness are reported separately. |
| W-STATE-03 | One-call transition | `tt` | supported | `wled_set_state`, `wled_apply_scene` | - | `transition_ms`, rounded to 100 ms units. |
| W-STATE-04 | Default transition time | `transition` | partial | `wled_get_state` | - | Read as `default_transition_ms`; not settable. |
| W-STATE-05 | Main segment | `mainseg` | partial | `wled_get_state`, `wled_replace_layout` | - | Read; set only implicitly when a layout replacement removes the main segment. |
| W-STATE-06 | Transition blending style | `bs` | unplanned | - | - | Preserved in saved presets; not settable. |
| W-STATE-07 | Nightlight | `nl` (`on`, `dur`, `mode`, `tbri`) | unplanned | - | - | - |
| W-STATE-08 | UDP sync send and groups | `udpn` (`send`, `sgrp`, `rgrp`, `nn`) | unplanned | - | - | Runtime toggles; sync settings are W-CFG-06. |
| W-STATE-09 | Realtime override and live mode | `lor`, `live` | unplanned | - | - | Realtime input itself is excluded (RT rows). |
| W-STATE-10 | Device time and effect timebase | `time`, `tb` | unplanned | - | - | - |
| W-STATE-11 | Advance playlist | `np` | unplanned | - | - | - |
| W-STATE-12 | Ledmap selection | `ledmap` | unplanned | - | - | Uploading ledmap files is W-SYS-05. |
| W-STATE-13 | Reset to automatic segments | `rSeg` | unplanned | - | - | - |

## Segments

| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W-SEG-01 | Segment bounds (1D) | `start`, `stop` (`len`) | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | On a matrix `start`/`stop` are X columns (W-SEG-20). |
| W-SEG-02 | Create and remove segments, complete layout | `seg` array, `stop: 0` | supported | `wled_replace_layout` | - | Overlapping segments only with `allow_overlap` (W-SEG-19). |
| W-SEG-03 | Segment power and opacity | `on`, `bri` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state`, `wled_apply_scene` | - | - |
| W-SEG-04 | Segment colors (three slots) | `col` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state`, `wled_apply_scene` | - | RGB arrays; other color forms are encodings (rule 2). |
| W-SEG-05 | Effect | `fx` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state`, `wled_apply_scene` | - | By ID; by catalog name only in scenes (#17). |
| W-SEG-06 | Effect speed and intensity | `sx`, `ix` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state`, `wled_apply_scene` | - | - |
| W-SEG-07 | Palette | `pal` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state`, `wled_apply_scene` | - | By ID; by catalog name only in scenes (#17). |
| W-SEG-08 | Grouping and spacing | `grp`, `spc` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | - |
| W-SEG-09 | Offset | `of` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | - |
| W-SEG-10 | Reverse and mirror | `rev`, `mi` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | - |
| W-SEG-11 | Segment selection | `sel` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | - |
| W-SEG-12 | Segment name | `n` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | Up to 32 UTF-8 bytes. |
| W-SEG-13 | White channel (RGBW) | `col` fourth channel | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | Existing ranges by their reported capability; new or moved RGBW and white-only ranges under the uniform-capability rule. |
| W-SEG-14 | Correlated color temperature | `cct` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state`, `wled_apply_scene` | - | 0-255 only where the range reports the CCT bit; no Kelvin input (ISSUE-19-DEC-002). |
| W-SEG-15 | Effect custom sliders and options | `c1`-`c3`, `o1`-`o3` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state`, `wled_apply_scene` | - | Settable where the readback carries the key; labels and defaults are parsed by `wled_get_effects` (#148). |
| W-SEG-16 | Sound simulation | `si` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | 0-3, where the readback carries the key. |
| W-SEG-17 | Segment LED set | `set` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | 0-3, where the readback carries the key. |
| W-SEG-18 | Freeze | `frz` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | Master power-on unfreezes every segment; the plan warns. |
| W-SEG-19 | Blend mode and overlapping segments | `bm` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | `bm` 0-16 where reported; overlap only with `allow_overlap` (ISSUE-19-DEC-001), with pairs and render order in the plan. |
| W-SEG-20 | 2D segment bounds | `startY`, `stopY` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | Only with `info.leds.matrix`; creating or moving a trailing 1D strip after the matrix is refused. |
| W-SEG-21 | 2D orientation | `rY`, `mY`, `tp` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | Only with `info.leds.matrix`. |
| W-SEG-22 | 1D effect mapping on 2D | `m12` | supported | `wled_patch_segments`, `wled_replace_layout`, `wled_get_state` | - | 0-4, where the readback carries the key. |
| W-SEG-23 | Individual LED colors | `i` | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | SEG-06 "Pixel art"; restated in ISSUE-19-DEC-002. |
| W-SEG-24 | Segment repetition | `rpt` | excluded | - | [ISSUE-19-DEC-002](decisions/issue-19.md#issue-19-dec-002--segment-features-not-exposed) | - |
| W-SEG-25 | Effect defaults | `fxdef` | excluded | - | [ISSUE-19-DEC-002](decisions/issue-19.md#issue-19-dec-002--segment-features-not-exposed) | - |

## Effects and palettes

| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W-CAT-01 | Effect list | `/json/eff` | supported | `wled_get_effects` | - | Cached per firmware. |
| W-CAT-02 | Effect metadata | `/json/fxdata` | supported | `wled_get_effects` | - | Raw and leniently parsed labels, palette selector, flags and defaults; ID-preserving filters. One read-only live probe on one controller (#148). |
| W-CAT-03 | Palette list | `/json/pal` | supported | `wled_get_palettes` | - | Built-in and gradient palettes; WLED does not list custom palettes there. |
| W-CAT-04 | Palette color data | `/json/palx` | unplanned | - | - | - |
| W-CAT-05 | Custom palette upload | `/upload` (`palette<n>.json`) | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | ADV-02 "filesystem uploads", applied to palette files by ISSUE-94-DEC-001. |
| W-CAT-06 | Custom palette removal | `rmcpal` | unplanned | - | - | - |

## Presets and playlists

| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W-PRESET-01 | List presets | `/presets.json` | supported | `wled_list_presets`, `wled_export_presets` | - | Export carries the stored objects in a versioned bundle without device data. |
| W-PRESET-02 | Read one preset | `/presets.json` | supported | `wled_get_preset` | - | Exact stored object. |
| W-PRESET-03 | Activate a state preset | `ps` | supported | `wled_activate_preset` | - | - |
| W-PRESET-04 | Activate a playlist | `ps` (playlist entry) | supported | `wled_activate_preset` | - | Members must be state presets. |
| W-PRESET-05 | Save the current state as a preset | `psave` | supported | `wled_save_preset` | - | Overwrite needs `overwrite=true` and takes a snapshot. |
| W-PRESET-06 | Delete a preset | `pdel` | supported | `wled_delete_preset` | - | Snapshot first. |
| W-PRESET-07 | API-command presets | `win` in a preset | partial | `wled_list_presets`, `wled_get_preset`, `wled_export_presets` | - | Readable and backed up; activation is refused; exported for inspection only with `include_unwritable`, never imported or restored. |
| W-PRESET-08 | Write a supplied preset object | `psave` with a supplied state object | supported | `wled_store_preset`, `wled_restore_preset`, `wled_import_presets` | - | Applied live, then stored (ISSUE-18-DEC-001); storing without a live change is unsupported on WLED 16; control keys are refused. |
| W-PRESET-09 | Create and edit playlists | `playlist` (`ps`, `dur`, `transition`, `repeat`, `end`, `r`) | supported | `wled_save_playlist`, `wled_import_presets`, `wled_restore_preset` | - | Saving starts the playlist (ISSUE-18-DEC-001); refused while a playlist runs; `end=255` (refused for activation too) and negative `repeat` refused. |
| W-PRESET-10 | Upload the whole preset file | `/upload` (`presets.json`) | excluded | - | [ISSUE-18-DEC-001](decisions/issue-18.md#issue-18-dec-001--write-route-for-supplied-preset-and-playlist-objects) | - |
| W-PRESET-11 | Quick-load labels | `ql` | unplanned | - | - | Preserved in stored presets; not settable. |
| W-PRESET-12 | Preset cycling and random selection | `ps` (`"a~b~"`, `"r"`) | unplanned | - | - | - |
| W-PRESET-13 | Boot preset and power-on defaults | `/json/cfg` (`def`: `ps`, `on`, `bri`) | unplanned | - | - | - |

## Information and diagnostics

| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W-INFO-01 | Firmware identity | `/json/info` (`ver`, `vid`, `product`, `brand`, `arch`) | supported | `wled_get_state` | - | - |
| W-INFO-02 | LED count, segment limit and color capabilities | `/json/info` (`leds.count`, `leds.maxseg`, `leds.lc`, `leds.seglc`, `leds.matrix`; state `seg[].lc`) | supported | `wled_get_state` | - | - |
| W-INFO-03 | Reachability | `/json/info` | supported | `wled_list_devices`, `cli: wled-mcp doctor` | - | Optional bounded probe. |
| W-INFO-04 | Runtime diagnostics | `/json/info` (`uptime`, `freeheap`, `wifi`, `fs`) | partial | `wled_get_state` | - | Raw `info` only, not normalized; `mac`, `ip` and `wifi.bssid` are removed. |
| W-INFO-05 | Live LED colors | `/json/live`, `/liveview`, WebSocket `lv` | partial | `wled_get_live_snapshot` | [#150](https://github.com/descipar/wled-mcp/issues/150) | Bounded sampled 1D JSON observation; matrices explicitly unmapped, no liveview/WebSocket stream or calibrated-color claim. |
| W-INFO-06 | Sync nodes | `/json/nodes` | unplanned | - | - | - |
| W-INFO-07 | Wi-Fi network scan | `/json/net` | unplanned | - | - | - |
| W-INFO-08 | Pin usage | `/json/pins` | unplanned | - | - | - |
| W-INFO-09 | mDNS discovery | mDNS announcement | supported | `cli: wled-mcp discover` | - | CLI: one-shot IPv4 mDNS query on explicit invocation; candidates only (ISSUE-16-DEC-001, superseded in part by DEC-034). MCP discovery, unicast probe and enrollment: M8, [contract](contract/discovery.md). |

## Configuration

| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W-CFG-01 | Read the configuration | `/json/cfg` | unplanned | - | - | - |
| W-CFG-02 | Hardware pin and bus configuration | `/json/cfg` (`hw.led` except `matrix`, `hw.btn` pins and pull-up, `hw.ir.pin`, `hw.relay`, `hw.if`, `hw.baud`, `eth`), `/settings/leds` | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | ADV-02 "hardware pin/bus configuration": LED buses, button, IR and relay pins, I2C/SPI pins, serial speed and the Ethernet board type with its pins. Button actions and IR remote behavior are W-CFG-08. |
| W-CFG-03 | Wi-Fi and access point settings | `/json/cfg` (`nw`, `ap`, `wifi`), `/settings/wifi`, state `wifi` | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | ADV-02 "Wi-Fi changes"; includes the address and DNS fields of the Wi-Fi network entries. |
| W-CFG-04 | Timers and schedules | `/json/cfg` (`timers`), timer fields of `/settings/time` | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | ADV-02 "Timer editing": scheduled presets and the countdown target. NTP and time zone are W-CFG-09. |
| W-CFG-05 | 2D matrix and panel configuration | `/json/cfg` (`hw.led.matrix`), `/settings/2D` | excluded | - | [ISSUE-19-DEC-002](decisions/issue-19.md#issue-19-dec-002--segment-features-not-exposed) | - |
| W-CFG-06 | Sync and integration settings | `/json/cfg` (`if.sync`, `if.nodes`, `if.live`, `if.va`, `if.mqtt`, `if.hue`, `dmx`), `/settings/sync`, `/settings/dmx` | unplanned | - | - | UDP sync, node list, realtime receive options, Alexa, MQTT, Hue and DMX output; one row. |
| W-CFG-07 | Security settings | `/json/cfg` (`ota`), settings `pin`, `/settings/sec` | unplanned | - | - | Settings PIN and OTA lock. |
| W-CFG-08 | Button and IR remote behavior | `/json/cfg` (`hw.btn.ins` `type` and `macros`, `hw.btn.tt`, `hw.btn.mqtt`, `hw.ir.type`, `hw.ir.sel`) | unplanned | - | - | Button types, press-to-preset actions and the IR remote type; not pin settings, so not read as ADV-02. |
| W-CFG-09 | Time and NTP settings | `/json/cfg` (`if.ntp`), time fields of `/settings/time` | unplanned | - | - | NTP server, time zone, UTC offset and location. |
| W-CFG-10 | Device identity | `/json/cfg` (`id`: `name`, `mdns`, `inv`) | unplanned | - | - | Device name, mDNS name and Alexa invocation name; `id.sui` is a web UI option (rule 3). |
| W-CFG-11 | Light defaults | `/json/cfg` (`light`: `scale-bri`, `pal-mode`, `aseg`, `gc`, `tr`, `nl`) | unplanned | - | - | Brightness factor, gamma, default transition and palette blending, nightlight defaults, auto segments. The runtime default transition is W-STATE-04. |
| W-CFG-12 | Clock overlay | `/json/cfg` (`ol`) | unplanned | - | - | - |

## System and maintenance

| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W-SYS-01 | Reboot | `rb`, `/reset` | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | ADV-02 "reboot". |
| W-SYS-02 | Firmware update | `/update`, `/updatebootloader` | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | ADV-02 "firmware updates". |
| W-SYS-03 | Factory reset | `/settings/sec` (`RS`) | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | ADV-02 "factory reset". |
| W-SYS-04 | File upload and editing | `/upload`, `/edit` | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | ADV-02 "filesystem uploads": `/edit` also lists, downloads and deletes files; it is the file manager around uploads and is read as part of that exclusion. Preset and palette files have their own rows. |
| W-SYS-05 | Ledmap file upload | `/upload` (`ledmap.json`, `ledmap<n>.json`) | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | ADV-02 "filesystem uploads", applied to ledmap files by ISSUE-94-DEC-001. |

## Realtime and streaming

| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W-RT-01 | Realtime pixel input over UDP or serial | UDP realtime (WARLS, DRGB, DRGBW, DNRGB, tpm2.net), Adalight serial | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | SEG-06 "custom realtime animation streaming". |
| W-RT-02 | E1.31 and Art-Net input | E1.31, Art-Net | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | SEG-06 "custom realtime animation streaming". |
| W-RT-03 | DDP | DDP | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | SEG-06 "DDP". |
| W-RT-04 | Audio input | AudioReactive usermod | excluded | - | [ISSUE-13-DEC-001](decisions/issue-13.md#issue-13-dec-001--shouldlater-scope-for-stage-1) | SEG-06 "audio capture". |
| W-RT-05 | WebSocket state push | `/ws` | unplanned | - | - | - |

## Usermods

| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W-UM-01 | Usermod state, information and settings | usermod keys in `/json/state`, `/json/info`, `/json/cfg` (`um`) | unplanned | - | - | Build-specific; individual usermods are not listed. |

## Tools without a WLED feature row

Registered tools that deliver no WLED feature are listed here with a reason and are not
counted.

- `wled_get_service_status`: reports the server's own profile, per-device ceilings, last
  observed outcomes and call counters (#20); it reads process memory only and contacts no
  device, so it is not a WLED reachability feature (W-INFO-03 stays `wled_list_devices`).
- `wled_search_effects`: searches a project-curated property catalog (shipped data, #31)
  intersected with the device's effect list; WLED has no such API, so it is not a WLED
  feature row (W-CAT-01 and W-CAT-02 stay as they are).
- `wled_explain_lighting`: combines two reads with process-local evidence into candidate
  causes (#30); it only reads an indicator allowlist and does not deliver or extend a WLED
  feature row (W-STATE-08 and W-STATE-09 stay `unplanned`).
- `wled_list_zones`: lists the server's own named physical zones (reviewed local files in
  the data directory, #27); no device is contacted and no WLED feature is involved.
- `wled_plan_zone`: reads state of the zone's devices to resolve a zone onto existing
  segments (a project concept, not a WLED API); it sends no write and adds no feature row.
- `wled_preview_layout`: draws an observed or planner-validated proposed 1D segment layout as
  a static SVG (#29) from the state and info reads (and optionally `/json/live`); it sends no
  write and is a project rendering, not a WLED API, so it adds no feature row.
- `wled_start_signal`: shows a colour on chosen segments and later restores the fields it
  changed, only if they still hold the signal value (#28); it uses the same verified state
  write as the segment and master tools, so no feature row changes.
- `wled_get_signal_status`: reads the server's own in-memory signal records (#28); no device is
  contacted and no WLED feature is involved.
- `wled_cancel_signal`: ends a signal early with the same conditional restore (#28); no WLED
  feature row.
- `wled_apply_zone`: writes segment fields to the segments a zone resolves to, through the
  same verified path as `wled_patch_segments` (W-SEG rows stay as they are); it never
  changes geometry or master state.
- `wled_list_snapshots`: lists the server's own preset snapshots in the data directory;
  no WLED feature is involved.
- `wled_list_groups`: lists the server's own device groups (local files in the data
  directory, #17); WLED's own sync groups are a different feature (W-STATE-08).
- `wled_save_group`: stores a device group as a local file; no device is contacted.
- `wled_delete_group`: deletes a stored device group file; no device is contacted.
- `wled_list_scenes`: lists the server's own scenes and returns a scene document or its
  shareable export; local files only.
- `wled_save_scene`: validates and stores a scene as a local file; no device is contacted.
- `wled_delete_scene`: deletes a stored scene file; no device is contacted.
- `wled_plan_scene`: reads state and catalogs of the target devices to plan a scene; it
  writes nothing and delivers no WLED feature (`wled_apply_scene` delivers the master and
  segment features it sets, see the rows above).

## Maintenance

- A pull request that changes WLED support (a new or changed tool or CLI command, or a
  new exclusion decision) updates the affected rows by ID and runs
  `python scripts/check_coverage.py --update`.
- The check fails when a registered tool is in no supported or partial row and not in
  the list above, when a row names a tool that is not registered, when a planned row does
  not link a roadmap issue, or when an excluded row does not link an existing decision.
- After merging `main`, a conflict inside a generated block is resolved by running
  `--update` again.
- A row moves from unplanned to planned or excluded only through an issue or a recorded
  decision.
