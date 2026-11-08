# Sources and prior research

## Issue-3 bootstrap evidence

Checked 2026-11-04: [official SDK release 2.3.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0),
[official SDK docs](https://py.sdk.modelcontextprotocol.io/),
[PyPI SDK metadata](https://pypi.org/pypi/mcp/2.3.0/json) and installed package
source establish the selected maintained SDK/API. PyPI reports MIT and Python
>=3.10; the bootstrap deliberately supports/tests Python 3.13 only. SDK 2.3.0
supports current automatic and legacy initialization paths; both are exercised.
[uv tools documentation](https://docs.astral.sh/uv/concepts/tools/) and installed
uv/uvx 0.11.14 help establish isolated tool environments and constraint flags.
Installed wheel and uvx versions are independently compared with the lock export.
These are packaging/protocol facts, not firmware compatibility evidence.

Reviewed 2026-11-04. Sources inform implementation; proposals in this repository are original design choices and are not claims that the upstream projects implement this contract. Recheck source behavior and dependency versions during implementation.

## Primary references

| Reference | Use |
| --- | --- |
| [WLED JSON API](https://kno.wled.ge/interfaces/json-api/) | Device state/info, segment representation, catalogs and documented API routes |
| [WLED presets](https://kno.wled.ge/features/presets/) | Persistent preset semantics, storage and backup behavior |
| [WLED segments](https://kno.wled.ge/features/segments/) | Segment concepts and device limits |
| [WLED effects](https://kno.wled.ge/features/effects/) | Built-in effect behavior and metadata context |
| [WLED source](https://github.com/wled/WLED) | Verify firmware-dependent behavior against matching release code |
| [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Protocol/runtime implementation; choose and lock a compatible version |
| [MCP tools specification, 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | Tool schemas/results/errors and annotations; implementation negotiates supported protocol via SDK |
| [MCP transports specification, 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) | stdio and Streamable HTTP, endpoint handling, Origin checks, sessions and disconnect semantics |
| [uv tool execution](https://docs.astral.sh/uv/guides/tools/) | uvx launch, pinned source/artifact selection and isolated environment behavior |
| [MCPHub repository](https://github.com/samanhappy/mcphub) | Hub entry/integration behavior; actual installed version must be checked |
| [Stage-2 marketplace research](MARKETPLACE.md) | Primary catalog/registry sources, observed submission paths and publication limitations, checked 2026-11-04 |

## Issue-2 contract evidence

Checked 2026-11-04. WLED tag `v0.15.1` resolves to immutable commit
`4f3992b4dc57c888b53d9576c894a278e03e4cfc` (GitHub commit API). This is a source
reference profile, not the latest-version claim or observed installed firmware.

| Pinned evidence | Contract consequence |
| --- | --- |
| [json.cpp, segment allocation/name handling](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L16) | New IDs append; geometry changes can clear omitted names. Require representability and targeted preservation compensation. |
| [json.cpp, deletion handling](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L358) | Array deletion can purge/renumber; single-object ID removal follows a different path. Exact-ID multi-step planning needs adapter tests. |
| [json.cpp, power and transition](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L291) and [serialization](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L526) | Master power/brightness are coupled; readback reports remembered brightness. Temporary transition uses 100 ms units. Issue #52: [json.cpp L314-318](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L314-L318) sets `on = root["on"] \| (bri > 0)` and calls [`toggleOnOff`](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/led.cpp#L50-L62) when power and `bri` disagree, so a positive `bri` alone turns an off master on, while `{"on": false, "bri": X}` toggles back in the same call (`bri=0`, `briLast=X`); [L324](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L324) unfreezes segments only when turning on; [L571-575](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L571-L575) reports `on = bri > 0` and `bri = briLast`. The adapter therefore sends the resolved `on=false` with a positive `bri` on an off master and verifies the resolved `on` ([ISSUE-52-DEC-001](decisions/issue-52.md)). Source-derived only: a visible blip, `tt` consumption and the `ps` change on real devices are unverified (#12). |
| [presets.cpp, save controls](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/presets.cpp#L200) and [capture](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/presets.cpp#L15) | Persistent IDs 1–250, temporary 255, key 0 initializer; 32-byte name payload; current-state capture is asynchronous. |

Live fields are processed before preset save in the reviewed API. The custom-command
storage branch does not establish a safe general supplied-state save/restore path;
those Should operations remain deferred. Server defaults, conservative RGB/RGBW
validation and result semantics are original design choices. No firmware code was
copied. [MCP transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
and [tool result](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
rules inform the protected stateless design; a compatible SDK and protocol execution
are still downstream work.

## Reviewed alternatives

| Project | Observed state | Why not adopted automatically |
| --- | --- | --- |
| [mrkprdo/wled_mcp](https://github.com/mrkprdo/wled_mcp), MIT | Default branch `dev`; commit `92e58bf97848972ec68d91edf805410d4d11efbc`, 2025-08-14; eleven stdio tools | Useful minimal adapter; module-start and effect-name documentation/code mismatches; typed segment/preset authoring limited |
| [film42/wled-mcp](https://github.com/film42/wled-mcp), MIT | Commit `204c3407c27433317b2c2307e2bb53dd886d1c57`, 2026-04-09; nine HTTP tools | Richer preset/layout operations but own service and mDNS; no exposed speed/intensity parameters; no dedicated preset activation tool |
| [timrogers/wld](https://github.com/timrogers/wld), MIT | Main commit `32b0a04a06e1eb1d4aa47d2daa1968c05e7a426a`, 2025-11-22; release v0.0.2, 2025-11-13 | Five MCP tools limited to inventory/status/power/brightness |
| [doccaz/wled-mcp](https://github.com/doccaz/wled-mcp) | MQTT, SUSE Rancher/Liz and Helm orientation | Different deployment context; not a necessary dependency |
| [cosmo058/mcp-wled](https://github.com/cosmo058/mcp-wled) | 16×16 matrix graphics and text orientation; no README/license file observed | Specialized use case and unclear reuse permission |

No candidate was installed or tested on actual WLED hardware during this research. GitHub push timestamps were not treated as main-branch release dates. Both MCPHub catalogs were searched: 43 local substring matches and 340 registry version entries, with no relevant direct WLED entry after filtering names/descriptions/repositories; `knowledge` caused unrelated matches.

## Issue-4 client evidence

Checked 2026-11-04 against the installed locked HTTPX2 2.16.0 API and its
[official package metadata](https://pypi.org/project/httpx2/) and
[documentation](https://pydantic.dev/docs/httpx2/). HTTPX2 continues the maintained
client line used by the selected MCP SDK; the dependency is declared directly.
Its package metadata is separate from the unselected project outbound license.
Installed API/source confirms `trust_env=false`, redirect refusal, stream contexts,
MockTransport injection and zero transport retries by default. Per-I/O inactivity
timeouts do not provide one logical-operation deadline; an outer AnyIO deadline
bounds the complete operation. WLED endpoints follow the existing official JSON
API sources. No upstream WLED server implementation was copied.

## Issue-5 state/catalog evidence

Checked 2026-11-04 against the same pinned tag `v0.15.1`, commit
`4f3992b4dc57c888b53d9576c894a278e03e4cfc` (raw `wled00/json.cpp`, `FX.cpp`,
`FX_fcn.cpp`, `const.h`). Facts used by the read tools; none is hardware evidence:

| Pinned fact | Consequence |
| --- | --- |
| `serializeModeNames` skips only empty entries; unused effect slots hold the literal `"RSVD"` (`_data_RESERVED`, filled by `setupEffectData`) and are emitted | Catalog ID = array index; `RSVD` flagged as placeholder for effects |
| Names are cut at `@`; `serializeModeData` emits the text after `@` (or `""`) for the same non-empty entries, in mode order | `/json/fxdata` is a string array parallel to `/json/eff`; exposed raw, attached by index only on equal length, never parsed |
| `/json/pal` serves the static `JSON_palette_names` array; `getPaletteCount()` is `13 + gradient palettes + customPalettes.size()` | Custom palettes are not in `/json/pal`; a `palcount` difference is a warning only |
| `serializeInfo`: `leds.count`, `leds.maxseg`, `leds.lc` (OR of active segment capabilities) and `leds.seglc` (array, one entry per active segment, in order) are nested under `leds`; `ver`, `vid`, `fxcount`, `palcount`, `mac`, `ip` are top-level; `bssid` is under `wifi` | Capability facts read from `info.leds`; the packet's "info `lc`" refers to `info.leds.lc` |
| Capability bits `SEG_CAPABILITY_RGB=0x01`, `_W=0x02`, `_CCT=0x04` (`const.h`) | `lc`/`seglc` decoded as rgb/white/cct; RGB-only means `(lc & 7) == 1` |
| `serializeSegment` emits `id,start,stop,len,grp,spc,of,on,frz,bri,cct,n,col,fx,sx,ix,pal,sel,rev,mi`; no per-segment `lc` or `seglc`; `bri` is `255` when opacity is 0 | Per-segment capability only via `info.leds.seglc` (aligned by position in the state segment list) |
| `serializeState`: `ps` is `-1` without a preset, `pl` is `currentPlaylist`, `transition` is in 100 ms units, `bri` is the remembered brightness, `mainseg` is the main segment ID | Normalization of preset/playlist/transition/brightness |

Not verified: behavior of other firmware versions or forks, a real controller's output,
whether `pl` is exactly `-1` when no playlist runs on every build (the read tool maps
`-1` to null and passes other integers through). No firmware code was copied.

## Issue-7 layout evidence

Read 2026-11-05 from the same pinned tag `v0.15.1`, commit
`4f3992b4dc57c888b53d9576c894a278e03e4cfc` (`wled00/json.cpp`, `FX_fcn.cpp`, `FX.h`,
`const.h`). Source evidence only, not hardware evidence; the stateful test fake models
exactly these facts:

| Pinned fact | Consequence |
| --- | --- |
| `deserializeSegment`: `stop = elem["stop"] \| -1`; `setGeometry` with `i2 <= i1` sets `stop = 0`; `isActive()` is `stop > start`; a geometry change without `n` clears the name; removing the main slot resets main to 0 | Removal payload `{"seg":{"id":N,"stop":0}}`; name resend after a geometry change |
| A removed slot stays in the segment vector; `serializeState` emits active segments only; `purgeSegments()` runs only on the ARRAY path when `getSegmentsNum() > 3 && deleted >= getSegmentsNum()/2` | One single-object POST per removal, never an array |
| `id >= getSegmentsNum()` appends one segment at the end and re-assigns the ID; `stop <= 0` there is ignored; `id >= getMaxSegments()` returns false | New ID `n` is exact only if `n <=` slot count; observable lower bound is `max(active)+1` |
| A reused inactive slot keeps old runtime state (colors, effect, `frz`, `cct`, c1-c3, o1-o3, ...); only sent fields change; `grp`/`spc` are passed to `setGeometry` as `uint8_t` (grp 0 becomes 1 and resets spacing to 0); `setGeometry` restarts the effect | Explicit defaults plus `frz=false`; unexposed state only warned about; grouping 1-255 and spacing 0-255 in both segment tools (#48). A value above 255 cannot be stored; whether the firmware ignores it or wraps it modulo 256 depends on the ArduinoJson conversion and is unverified (the test fake models wrapping) |
| Explicit `of` is reduced modulo length; an unsent `of` is clamped to `len-1` after shrinking; names are truncated by bytes (`strlen`, `strlcpy`, possibly splitting a multibyte character) to the build limit `WLED_MAX_SEGNAME_LEN` (default 64 ESP32, 32 ESP8266; a build override below 32 is raised to 32), and a U+0000 ends the C string | Reject clamping moves without explicit offset; names limited to 32 UTF-8 bytes and no U+0000 in both segment tools (#48), the only build-independent guarantee |
| `bri` sent and > 0 sets opacity and ON; a later `on` key overrides; `on:true` with `bri:0` stays ON; `bri:0` without `on` turns the segment off | Both segment tools (#48): `on=true` with `brightness=0` and `brightness=0` with omitted `on` on an on segment rejected; a positive `bri` with omitted `on` on an off segment is sent with `on=false`; the resolved `on` is verified whenever `bri` is sent. Whether `{bri:X,on:false}` causes a visible transition blip on an off segment is unverified (#12) |
| `mainseg` is processed before `seg`; `setMainSegmentId(n)` accepts only `n < segment slots` (may be inactive) else resets to 0 | Main redirect before removals when the target is active, after creation otherwise |
| `serializeSegment` emits `n` only when a name exists | Missing `n` is the empty name |

Not verified: any real device, other firmware versions, `lc` semantics on mixed bus types
beyond ISSUE-5-DEC-008. No firmware code was copied.

## Issue-9 preset evidence

Read 2026-11-05 from the same pinned tag `v0.15.1`, commit
`4f3992b4dc57c888b53d9576c894a278e03e4cfc` (`wled00/json.cpp`, `presets.cpp`, `file.cpp`,
`playlist.cpp`). Source evidence only, not hardware evidence; the stateful test fake
models exactly these facts and nothing beyond them. No firmware code was copied.

| Pinned fact | Consequence |
| --- | --- |
| [`deserializeState`](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L430): after all state keys, `psave` in 1-250 calls `savePreset(ps, nullptr, root)` and, right after, `pdel` in 1-250 calls `deletePreset(ps)`. Values outside 1-250 are ignored | Save is `{"psave": id, ...}`, delete is `{"pdel": id}`, both POSTed to `/json/state`; the ID range 1-250 is firmware-enforced |
| [`deletePreset`](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/presets.cpp#L279) writes an empty document with `writeObjectToFileUsingId`; [`writeObjectToFile`](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/file.cpp#L265) treats null content as delete: the old object is overwritten with spaces (with its comma), so the key is no longer present. A dummy `"0":{}` object is kept so the first entry can be deleted ([file.cpp header](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/file.cpp#L23)) | Delete is evidenced as single-entry removal. After deletion the key is absent from `/presets.json`; absence by missing key, `null` or `{}` is accepted (PRE-01 rule). No whole-file upload or null-entry POST is used |
| [`savePreset`](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/presets.cpp#L217): `n` is copied with `strlcpy(..., 33)` (32 bytes); without an `o` key the save is deferred (`presetToSave`) and serialized later from the main loop by [`doSaveState`](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/presets.cpp#L25) / `handlePresets`, which wraps it in `strip.suspend()`/`resume()`; `ib`, `sb`, `sc` select brightness/bounds/selected-only; a payload containing `o` or `playlist` is a different (API/playlist) save path | The save payload carries no `o`/`playlist`; persistence is asynchronous, hence bounded polling. The brief strip suspension while saving is source-evidenced but its visible effect is unverified |
| `doSaveState` uses [`serializeState(forPreset=true, ib, sb, sc)`](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L571): `on`, `bri` (remembered), `transition` (100 ms units), `mainseg`, then `seg` with one object per active slot (`id`, `start`, `stop`, `grp`, `spc`, `of`, `on`, `frz`, `bri`, `cct`, `set`, `n` (empty string if unnamed), `col`, `fx`, `sx`, `ix`, `pal`, `c1`-`c3`, `sel`, `rev`, `mi`, `o1`-`o3`, `si`, `m12`) and `{"stop": 0}` markers (no `id`) for inactive slots; then `n`, optional `ql`/`ledmap` | Capture comparison fields and the marker rule; unknown stored fields are preserved |
| [`handlePresets`](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/presets.cpp#L144): `applyPreset(id)` only sets `presetToApply`; the main loop reads the entry, applies it and sets `currentPreset` (reported as `ps`) when it changed state. The JSON `ps` branch ([json.cpp L455](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L455)) ignores an ID equal to `currentPreset`. `applyPreset` first calls `unloadPlaylist()` | Activation is asynchronous (bounded polling); re-selecting the active preset is a firmware no-op (warning); activating a state preset leaves `pl = -1` |
| [`loadPlaylist`](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/playlist.cpp#L56): reads `playlist.ps` (list of preset IDs, at most 100 used), `dur`, `transition`, `repeat`, `end`, `r`; sets `currentPlaylist = presetId` (reported as `pl`) | Playlist type = `playlist.ps` nonempty ID list; activation verifies `pl == id`; members are checked to be plain state entries |
| `handlePresets` with a `win` key runs the stored HTTP API command string; `deserializeState` acts on many more top-level keys than light state (`psave`, `pdel`, `ps`, `pd`, `rb`, `live`, `time`, `bootps`, `playlist`, `nl`, `udpn`, `lor`, `rmcpal`, `wifi`, `np`, ...) | A plain `state` entry is classified by an allowlist of what a save emits (`on`, `bri`, `transition`, `mainseg`, `seg`, `n`, `ql`, `ledmap`) with at least one of `on`, `bri`, `seg`; `win` with a string value is `api-command`; anything else is `unknown` (never activated). Amended for WLED 16 by `bs` ([Issue-66 WLED 16 preset evidence](#issue-66-wled-16-preset-evidence), ISSUE-66-DEC-001) |
| `handlePlaylist`/`loadPlaylist`: at playlist end the `end` preset is applied (`applyPresetFromPlaylist`); `end` 255 restores the preset that ran before; `end` is stored in a byte (low 8 bits) before the >250 check, so integers outside 0-255 wrap | Members checked for activation are `playlist.ps` plus a persistent `end`; `end=255` and integer `end` outside 0-255 are refused; 251-254 and non-integers mean no end preset; a `pl` that is already the requested ID is a weaker warning because the playlist is restarted |

Not verified: the real file layout after deletion on hardware, flash timing, whether
saving moves `ps` or visibly interrupts output, firmware other than v0.15.1, files
beyond the client's 2 MiB response bound, and real playlist behavior. Residual race
(documented in TOOL-CONTRACT): the preset file has no transaction or compare-and-set,
so another client can write between the final recheck and the firmware's asynchronous
write.

## Issue-66 WLED 16 preset evidence

Read 2026-11-06 from tag `v16.0.1`, commit `29b389df1c1aaec6ff53aea742d17063b985906c`
(`v16.0.0` is `4374f013f5a287630ef33b2d14a6ff0162891bf1`, not separately reviewed).
Source evidence only, not hardware evidence; no firmware code was copied. Basis of
[ISSUE-66-DEC-001](decisions/issue-66.md).

| Pinned fact (v16.0.1) | Consequence |
| --- | --- |
| [`wled.h`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/wled.h#L607): `bs` is the global runtime variable `blendingStyle` (effect blending/transition style), `uint8_t`, default 0 | A light-state value of the same kind as `transition` |
| [`deserializeState`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp#L397-L408): `blendingStyle = root["bs"] \| blendingStyle; blendingStyle &= 0x1F;` directly after the `transition` handling, with no other action | Applying a stored `bs` changes only the style of later transitions; no value check is needed by this server |
| [`serializeState`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp#L645-L652) emits `bs` in the `includeBri` block with `on`, `bri`, `transition`; [the default `includeBri = true`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/fcn_declare.h#L176) means live `/json/state` carries `bs` too | `bs` is compared on save when the live state has it |
| [`doSaveState`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/presets.cpp#L29-L50) calls `serializeState(forPreset=true, includeBri, ...)` then adds `n`, optional `ql`, `ledmap`; `includeBri` comes from the save payload's `ib` ([presets.cpp](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/presets.cpp#L245-L249)), which this server always sends as `true` | A saved state preset carries `bs` |
| [Serialized top-level keys](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp#L645-L701) of a state-preset save: `on`, `bri`, `transition`, `bs`, `mainseg`, `seg`, `n`, optional `ql`, `ledmap`; usermod state is emitted only when not saving a preset | `bs` is the only new top-level key versus v0.15.1; the `state` allowlist gains exactly `bs` |
| Blending values `TRANSITION_FADE` 0 to `TRANSITION_PUSH_BL` 0x17 ([FX.h](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/FX.h#L378-L404)); only the renderer reads `blendingStyle` ([FX_fcn.cpp](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/FX_fcn.cpp#L1462-L1464), [FX_2Dfcn.cpp](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/FX_2Dfcn.cpp#L152-L182)); the UI transition select sends `{"bs": n}` ([index.htm](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/data/index.htm#L286-L310)) | Visual transition style only |
| No occurrence of `blendingStyle` or `"bs"` in `wled00/cfg.cpp`, `set.cpp`, `udp.cpp`, `presets.cpp` or `playlist.cpp` of the tag (full-tree search during the requirements review) | Not persisted to configuration, not synced, not a preset/playlist/control action |
| Per-segment additions in the same serialization ([json.cpp](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp#L630-L642)): `bm` (blend mode), `rY`/`mY`/`tp` on matrices | Segment-level; classification checks top-level keys only and the save compare ignores segment fields outside its list |
| No `blendingStyle`/`bs` in `wled00/json.cpp` at v0.15.1 (`4f3992b4dc57c888b53d9576c894a278e03e4cfc`) or anywhere in `wled00` at v0.15.5 (`c2b968a7019c2dc76b09225ade0dc847946a8cb0`) | 0.15.x entries and live state are unchanged; the `bs` compare does not apply there |

Not verified: hardware save-then-activate on WLED 16 (pending as a #12 follow-up),
other 16.x revisions and forks, and the visible effect of a restored `bs`.

## Issue-18 WLED 16 preset write evidence

Read 2026-11-07 from tag `v16.0.1`, commit `29b389df1c1aaec6ff53aea742d17063b985906c`
(the Phase-0 requirements review, re-read for the first #18 pull request; `playlist.cpp`
and `FX.h` re-read 2026-11-08 for the second). Source
evidence only, not hardware evidence; no firmware code was copied. Basis of
[ISSUE-18-DEC-001](decisions/issue-18.md) and the write routes in
[contract/presets.md](contract/presets.md).

| Pinned fact (v16.0.1) | Consequence |
| --- | --- |
| [`deserializeState`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp#L370-L505) applies `bri`, `on`, `transition`, `bs`, `seg` and other light state before it reaches `psave`; [`psave` 1-250 calls `savePreset`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp#L504-L505) with the request document | A state object sent with `psave` changes the live output first; no storage-only JSON path |
| [`savePreset`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/presets.cpp#L218-L278): with a non-null `o` and no `playlist` key the document minus `o`, `v`, `time`, `error`, `psave` (and `bootps`, removed earlier) is written immediately with `writeObjectToFileUsingId`; `n` is set to `Preset <id>` when absent; the firmware comment warns that this path often causes `presets.json` corruption | State route: one entry, stored verbatim; verification compares the sent object minus these keys, with the default name |
| Without `o`, `savePreset` only schedules [`doSaveState`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/presets.cpp#L29-L80) (`ib`, `sb`, `sc`), which serializes the live state | The #9 save-current path is unchanged and is not a supplied-object route |
| With `o` and `playlist`, `savePreset` sets `playlistSave`; the request's [`playlist` is loaded afterwards](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp#L539-L544) and starts; `doSaveState` then stores [`serializePlaylist`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L185-L198) plus `on: true`, the name and `ql` | Playlist route: the playlist starts, then is stored re-serialized; fields other than `ps`, `dur`, `transition`, `repeat`, `end`, `r`, `on`, `n`, `ql` are dropped |
| [`loadPlaylist`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L58-L147): at most 100 entries; `dur` constrained to 0-42949670 tenths, a scalar or short list padded with the last value (default 100); `transition` likewise (default: the device transition); a negative `repeat` means shuffle; `end` 255 restores the previous preset, above 250 means none; `r` sets shuffle | Restore refuses values the firmware would clamp or reinterpret and compares per-entry values semantically |
| [`serializePlaylist`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L190-L192) stores `repeat` minus the extra pass only while `playlistIndex` is -1 (not yet advanced) and `r` as `playlistOptions & 1` (an integer). The main loop runs [`handlePlaylist` only when no preset save is pending](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/wled.cpp#L123-L126), the request holds the [JSON buffer lock across `deserializeState`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/wled_server.cpp#L414-L447) so the save follows `loadPlaylist`, and [`shufflePlaylist` runs only inside `handlePlaylist`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L173). The `savePreset` comment ("will have repeat counter increased by 1 it will also be randomised if selected") is outdated | A finite `repeat` and shuffle are stored unchanged and are accepted; the semantic readback checks `repeat`, `r` and the `ps` order. Source-derived; hardware pending |
| [`playlistRepeat` and `playlistEndPreset`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L13-L14) are bytes; [`loadPlaylist`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L114-L122) stores `repeat` plus one extra pass in that byte and `end` unchecked; each step's `tr` is applied as [`setTransition(tr * 100)`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L177) with a [`uint16_t` millisecond argument](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/FX.h#L908); `dur` is [constrained to 0-42949670 tenths](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L83-L98) and 0 means [no automatic advance](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L178) | Authoring (issue #18, second pull request) accepts `repeat` 0-254 (255 would wrap to endless), a per-entry transition of at most 655 tenths (x 100 must fit 16 bits) and `dur` 0-42949670 tenths; restore and import refuse a `repeat` above 254 as well. Source-derived; hardware pending |
| [`loadPlaylist`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp#L58) returns early when a nested playlist is already active and otherwise keeps the running playlist as parent; the save then serializes the runtime playlist | The playlist route is refused while `state.pl` reports a running playlist (planning and after the snapshot) |
| [`transitionDelay`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/wled.h#L609) is a `uint16_t` in milliseconds set from `transition` tenths x 100 | Supplied `transition` is bounded to 655 tenths |
| After `psave`, [`win`, `ps`, `playlist`, `rmcpal`, `np`, `wifi`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp#L507-L560) still run | Supplied and restored objects never contain these keys |

Not verified: hardware behavior of both routes, flash timing and the corruption risk
named in the firmware comment, the save/playlist ordering on hardware, other 16.x
revisions and forks, and firmware below 16.0.0.

## Issue-14 HTTP service evidence

Observed 2026-11-05 by inspecting the installed MCP SDK 2.3.0, starlette 1.10.0, uvicorn 0.54.0 and HTTPX2 2.16.0 sources and loopback runs with synthetic tools (no repository changes): the stateless JSON app issues no session ID, answers DELETE 405, serves a stale session ID, and opens a stream for a GET that offers `text/event-stream`; its Host check returns 421 after any authentication; a disconnected client does not cancel a running stateless handler (legacy and 2026-07-28 paths); uvicorn cancels in-flight handlers only after `timeout_graceful_shutdown` and re-raises a captured signal after serving. These observations motivate [ISSUE-14-DEC-002 to -004](decisions/issue-14.md) and are re-pinned by tests, not assumed.

## Issue-16 WLED mDNS discovery evidence

Read 2026-11-08 from tag `v16.0.1`, commit `29b389df1c1aaec6ff53aea742d17063b985906c`
(GitHub contents API), as required by [ISSUE-16-DEC-001](decisions/issue-16.md).

| Pinned evidence | Consequence for `wled-mcp discover` |
| --- | --- |
| [`wled.cpp` L850-L861](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/wled.cpp#L850-L861): only `if (strlen(cmDNS) > 0)`, WLED calls `MDNS.begin(cmDNS)`, `MDNS.addService("http", "tcp", 80)`, `MDNS.addService("wled", "tcp", 80)` and `MDNS.addServiceTxt("wled", "tcp", "mac", escapedMac.c_str())` | The query asks for the PTR records of `_wled._tcp.local`; the port comes from SRV (80 in this source); the TXT key `mac` is the duplicate key. A controller with an empty mDNS name announces nothing (documented limit) |
| [`wled.cpp` L471-L473](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/wled.cpp#L471-L473): `escapedMac = WiFi.macAddress()`, colons removed, lower case | A `mac` value is accepted only as 12 lower-case hex digits (colons removed, case folded); anything else is ignored |
| [`wled.cpp` L535-L536](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/wled.cpp#L535-L536): the default mDNS name becomes `wled-` plus the last six MAC hex digits | Typical instance and host names look like `wled-a1b2c3`; the suggested device ID is derived from the instance name |

The multicast exchange itself (an IPv4 one-shot query from an ephemeral port, RFC 6762
section 5.1, and the responder libraries' answers to it) was not observed on hardware;
the tests use a fake socket. No firmware code was copied.

## Licensing

No upstream code is included in this planning repository. A link is not a vendoring decision. If a later implementation reuses source, review its actual license at the pinned commit and retain required copyright/license notices. Do not infer reuse permission for projects lacking a license. The repository is private and no outbound project license has been selected. Reassess dependency and WLED-source licensing if copying code or distributing artifacts; HTTP API interoperability alone does not imply copying firmware code.
