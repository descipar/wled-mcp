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

## Issue-14 HTTP service evidence

Observed 2026-11-05 by inspecting the installed MCP SDK 2.3.0, starlette 1.10.0, uvicorn 0.54.0 and HTTPX2 2.16.0 sources and loopback runs with synthetic tools (no repository changes): the stateless JSON app issues no session ID, answers DELETE 405, serves a stale session ID, and opens a stream for a GET that offers `text/event-stream`; its Host check returns 421 after any authentication; a disconnected client does not cancel a running stateless handler (legacy and 2026-07-28 paths); uvicorn cancels in-flight handlers only after `timeout_graceful_shutdown` and re-raises a captured signal after serving. These observations motivate [ISSUE-14-DEC-002 to -004](decisions/issue-14.md) and are re-pinned by tests, not assumed.

## Licensing

No upstream code is included in this planning repository. A link is not a vendoring decision. If a later implementation reuses source, review its actual license at the pinned commit and retain required copyright/license notices. Do not infer reuse permission for projects lacking a license. The repository is private and no outbound project license has been selected. Reassess dependency and WLED-source licensing if copying code or distributing artifacts; HTTP API interoperability alone does not imply copying firmware code.
