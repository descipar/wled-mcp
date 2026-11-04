# Sources and prior research

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

## Licensing

No upstream code is included in this planning repository. A link is not a vendoring decision. If a later implementation reuses source, review its actual license at the pinned commit and retain required copyright/license notices. Do not infer reuse permission for projects lacking a license. The repository is private and no outbound project license has been selected. Reassess dependency and WLED-source licensing if copying code or distributing artifacts; HTTP API interoperability alone does not imply copying firmware code.
