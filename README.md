# WLED MCP

Specification and implementation backlog for a standalone WLED MCP server with MCPHub integration.

**Status, 2026-11-06:** version 0.1.0 provides an installable Python 3.13 stdio server with validated inventory, `wled_list_devices`, the read-only `wled_get_state`, `wled_get_effects` and `wled_get_palettes`, the typed `wled_set_state` and `wled_patch_segments` (#6), `wled_replace_layout` (#7; mock-tested, hardware check H05 partly recorded in #12) and the persistent-preset tools `wled_list_presets`, `wled_get_preset`, `wled_activate_preset`, `wled_save_preset` and `wled_delete_preset` (#9; mock-tested, hardware check H06 partly recorded in #12) with a durable snapshot before overwrite/delete (no restore tool; supplied-state save stays deferred to #13). Listing is network-free by default; explicit probes and reads use bounded requests to configured devices; effect/palette catalogs have a firmware-aware cache. A shared internal HTTP/deadline/lock foundation supports later operations. The authenticated stateless Streamable HTTP service (`--transport streamable-http`, #14) shares the same tools and resource graph; it is validated with mocks and loopback only. Deployment artifacts for both modes (#11: HTTP image and Compose example, uvx/stdio hub entry, staging, update/rollback procedures) are statically checked, and one authorized live check of both modes ran on one target hub (see [validation](docs/VALIDATION.md#issue-11-live-deployment-check-2026-11-06)); a live removal and redeploy of the HTTP service followed, and the HTTP mode remains deployed there. Live version-to-version update/rollback moved to stage 2 ([#21](https://github.com/descipar/wled-mcp/issues/21), [#25](https://github.com/descipar/wled-mcp/issues/25)); the documented procedures stay in #11. Hardware acceptance (#12) is partly recorded for one test controller on one firmware (WLED 16.0.1) through the HTTP mode, including restoration (see [validation](docs/VALIDATION.md#issue-12-hardware-acceptance-2026-11-06)); activation of presets saved by WLED 16 is refused ([#66](https://github.com/descipar/wled-mcp/issues/66)), `tools/list` is CPU-bound on small hosts ([#67](https://github.com/descipar/wled-mcp/issues/67)), and H07, the visual check and the other listed items remain pending. No hardware compatibility is claimed beyond these checks. See [development commands](docs/DEVELOPMENT.md), [inventory behavior](docs/INVENTORY-CLIENT.md), [validation](docs/VALIDATION.md) and [traceability](docs/TRACEABILITY.md).

The repository also includes [shared Codex and Claude Code roles](agents/README.md) and a [human-in-the-loop workflow](docs/AGENT-WORKFLOW.md) for requirements, implementation, independent review and post-merge issue completion. These run inside an active or resumed client session; no autonomous background service or WLED backlog run is started by checking them out.

## Goal

Let an agent inspect and control several WLED controllers by meaningful names, create and modify segment layouts, and manage presets through clear MCP tools. Reuse WLED's built-in effects rather than building an animation engine. Keep operation lightweight enough for the existing Raspberry Pi hub.

**Confirmed transport scope:** support Streamable HTTP as an independent service and stdio for client-managed launch via `uvx`. Both modes expose the same tools. This supersedes the initial stdio-only proposal; [issue #14](https://github.com/descipar/wled-mcp/issues/14) tracks HTTP implementation.

**Stage 2:** plan a reusable public project with additional WLED workflows, distributable releases and MCPHub marketplace discovery. See the [stage-2 roadmap](docs/STAGE-2.md) and [tracker #15](https://github.com/descipar/wled-mcp/issues/15). The repository remains private; public release and external submissions have not been performed.

**Stage 3:** named lighting zones, temporary signals, static layout previews, explanations of ineffective changes and property-based effect search. See the [stage-3 roadmap](docs/STAGE-3.md) and [tracker #26](https://github.com/descipar/wled-mcp/issues/26). These extensions do not block stage-2 publication.

## Start here

1. Read [AGENTS.md](AGENTS.md).
2. Read [requirements](docs/REQUIREMENTS.md), especially authority, priorities, and acceptance conditions.
3. Read the [tool contract](docs/TOOL-CONTRACT.md) and [architecture](docs/ARCHITECTURE.md).
4. Use the [implementation plan](docs/IMPLEMENTATION-PLAN.md) and its linked GitHub issues.
5. Work from the [agent handoff](docs/AGENT-HANDOFF.md); record evidence using [validation](docs/VALIDATION.md).

## Documents

| File | Purpose |
| --- | --- |
| [Requirements](docs/REQUIREMENTS.md) | Context, scope, identifiable requirements, priorities, unresolved inputs |
| [Tool contract](docs/TOOL-CONTRACT.md) | V1 design: tools, parameters, result format and mutation semantics |
| [Contract examples](examples/contracts/README.md) | Synthetic patch/layout/preset/error cases and snapshot format |
| [Architecture](docs/ARCHITECTURE.md) | Components, runtime, configuration, design decisions |
| [Deployment](docs/DEPLOYMENT.md) | HTTP-service and uvx/stdio MCPHub deployment: build/stage, update, rollback, removal (one live check of both modes plus HTTP service removal/redeploy; live update/rollback between versions in stage 2) |
| [Validation](docs/VALIDATION.md) | Meaningful automated checks, opt-in hardware checks, release criteria |
| [Traceability](docs/TRACEABILITY.md) | Must requirement and T01–T21 to automated evidence; hardware/deployment gaps marked pending |
| [Implementation plan](docs/IMPLEMENTATION-PLAN.md) | Issue order, dependency graph, requirement traceability |
| [Agent handoff](docs/AGENT-HANDOFF.md) | Concrete instructions for the next implementing agent |
| [Agent workflow](docs/AGENT-WORKFLOW.md) | Five shared roles with native Codex/Claude adapters, handoffs, human merge and evidenced issue completion |
| [Decision log](docs/DECISIONS.md) | Scoped project knowledge from human answers, sources and supersession |
| [Sources](docs/SOURCES.md) | Official references, reviewed alternatives, license boundaries |
| [Stage 2](docs/STAGE-2.md) | Product extensions, public-release requirements, issue map and evidence |
| [Stage 3](docs/STAGE-3.md) | Five additional usability features, dependencies and acceptance scenarios |
| [Marketplace plan](docs/MARKETPLACE.md) | Separate catalog/registry routes, distribution identities and submission sequence |
| [Configuration example](examples/devices.example.toml) | Synthetic device inventory, never an actual home-network configuration |
| [Stdio hub example](examples/mcphub.example.json) | Proposed uvx entry with separate arguments and placeholder artifact path |
| [HTTP hub example](examples/mcphub.http.example.json) | Streamable HTTP URL (default port 8000) and placeholder service credential |

## Example deployment

Synthetic starting points for both modes; replace every placeholder before use and follow [DEPLOYMENT.md](docs/DEPLOYMENT.md) for staging, verification, update, rollback and removal:

- [compose.http.example.yaml](examples/compose.http.example.yaml): independent Streamable HTTP service (Compose)
- [mcphub.http.example.json](examples/mcphub.http.example.json): MCPHub entry for the HTTP service
- [mcphub.example.json](examples/mcphub.example.json): MCPHub entry for client-managed stdio via `uvx`
- [devices.example.toml](examples/devices.example.toml): synthetic device inventory used by either mode

## Development status

The package has locked development/build/runtime dependencies and installed-wheel/uvx checks. Follow [DEVELOPMENT.md](docs/DEVELOPMENT.md). Use [bootstrap.toml](examples/bootstrap.toml) for an empty inventory or the executable synthetic [inventory example](examples/devices.example.toml) for configured listing/probes. State/control, layout and preset tools and the HTTP lifecycle are implemented and covered by mock/loopback tests mapped in [TRACEABILITY.md](docs/TRACEABILITY.md); deployment artifacts (#11) have one recorded live check of both modes on one target, including removal and redeploy of the HTTP service, catalog/preset reads and hub container recreation (drain on the target and load measurements moved to #12 per ISSUE-11-DEC-008); live version-to-version update/rollback belongs to stage 2 (#21, #25). The #12 hardware acceptance is partly recorded for one controller and firmware, with HTTP load and drain of in-flight reads; its "Not run" items (including H07, the visual check, the in-flight write drain and #66) remain pending.

## Boundaries

- No cloud account, public endpoint, web interface, or MQTT broker required for v1.
- The server controls WLED directly through its API and works independently of other home-automation systems.
- Device inventory, firmware versions, topology, RGBW/CCT/2D needs, and test-device availability are still unknown.
- Repository remains private. A distribution license has not been selected; upstream code has not been copied.
- GitHub issues track implementation status. This repository documents the contract and decisions; neither an unchecked issue nor a planning paragraph proves completion.

Repository: https://github.com/descipar/wled-mcp

Backlog: [delivery tracker #1](https://github.com/descipar/wled-mcp/issues/1), with thirteen child issues covering contract, both transports, implementation, validation, integration and optional scope. Review [contract decisions #2](https://github.com/descipar/wled-mcp/issues/2) before downstream packaging/runtime work; a document change does not close the live issue.

Future public/product work has its own [stage-2 tracker #15](https://github.com/descipar/wled-mcp/issues/15), with ten child issues (#16–#25), all labeled `stage:2`. These do not silently expand stage-1 acceptance.

Additional usability features have a separate [stage-3 tracker #26](https://github.com/descipar/wled-mcp/issues/26), with five child issues (#27–#31), all labeled `stage:3`.
