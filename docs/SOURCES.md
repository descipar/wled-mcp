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
| [Home Assistant WLED integration](https://www.home-assistant.io/integrations/wled/) | Existing functionality and overlap; its compatibility floor is not this server's compatibility guarantee |
| [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Protocol/runtime implementation; choose and lock a compatible version |
| [MCP tools specification, 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | Tool schemas/results/errors and annotations; implementation negotiates supported protocol via SDK |
| [MCPHub repository](https://github.com/samanhappy/mcphub) | Hub entry/integration behavior; actual installed version must be checked |

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
