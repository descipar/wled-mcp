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
| [json.cpp, power and transition](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L291) and [serialization](https://github.com/wled/WLED/blob/4f3992b4dc57c888b53d9576c894a278e03e4cfc/wled00/json.cpp#L526) | Master power/brightness are coupled; readback reports remembered brightness. Temporary transition uses 100 ms units. |
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
| A reused inactive slot keeps old runtime state (colors, effect, `frz`, `cct`, c1-c3, o1-o3, ...); only sent fields change; `grp`/`spc` are `uint8_t` (grp 0 becomes 1); `setGeometry` restarts the effect | Explicit defaults plus `frz=false`; unexposed state only warned about; grouping/spacing limits |
| Explicit `of` is reduced modulo length; an unsent `of` is clamped to `len-1` after shrinking; names are truncated to the build limit (64 ESP32, 32 ESP8266) | Reject clamping moves without explicit offset; name limit 32 characters as #6 (firmware truncation is a shared limit) |
| `bri` sent and > 0 sets opacity and ON; a later `on` key overrides; `on:true` with `bri:0` stays ON; `bri:0` without `on` turns the segment off | `on=true` with `brightness=0` rejected; `bri` sent as #6 does (no extra `on`; off segment may be switched on, reported by readback) |
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
| `handlePresets` with a `win` key runs the stored HTTP API command string; `deserializeState` also acts on `psave`, `pdel`, `ps`, `pd`, `rb`, `live`, `time`, `bootps` and `playlist` | An entry with any of these keys is not a plain state preset; `win` with a string value classifies as `api-command`; everything else with control keys is `unknown` (never activated) |

Not verified: the real file layout after deletion on hardware, flash timing, whether
saving moves `ps` or visibly interrupts output, firmware other than v0.15.1, files
beyond the client's 2 MiB response bound, and real playlist behavior. Residual race
(documented in TOOL-CONTRACT): the preset file has no transaction or compare-and-set,
so another client can write between the final recheck and the firmware's asynchronous
write.

## Issue-14 HTTP service evidence

Observed 2026-11-05 by inspecting the installed MCP SDK 2.3.0, starlette 1.10.0, uvicorn 0.54.0 and HTTPX2 2.16.0 sources and loopback runs with synthetic tools (no repository changes): the stateless JSON app issues no session ID, answers DELETE 405, serves a stale session ID, and opens a stream for a GET that offers `text/event-stream`; its Host check returns 421 after any authentication; a disconnected client does not cancel a running stateless handler (legacy and 2026-07-28 paths); uvicorn cancels in-flight handlers only after `timeout_graceful_shutdown` and re-raises a captured signal after serving. These observations motivate [ISSUE-14-DEC-002 to -004](decisions/issue-14.md) and are re-pinned by tests, not assumed.

## Licensing

No upstream code is included in this planning repository. A link is not a vendoring decision. If a later implementation reuses source, review its actual license at the pinned commit and retain required copyright/license notices. Do not infer reuse permission for projects lacking a license. The repository is private and no outbound project license has been selected. Reassess dependency and WLED-source licensing if copying code or distributing artifacts; HTTP API interoperability alone does not imply copying firmware code.
