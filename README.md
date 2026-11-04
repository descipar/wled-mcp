# WLED MCP

Specification and implementation backlog for a standalone WLED MCP server with MCPHub integration.

**Status, 2026-11-04:** version 0.1.0 provides an installable Python 3.13 stdio server with validated inventory and `wled_list_devices`. Listing is network-free by default; explicit probes use bounded reads of configured devices. A shared internal HTTP/deadline/lock foundation supports later operations. HTTP service selection still fails before listening until #14. No deployment or hardware compatibility is claimed. See [development commands](docs/DEVELOPMENT.md), [inventory behavior](docs/INVENTORY-CLIENT.md) and [validation](docs/VALIDATION.md).

The repository also includes [Codex role definitions and a human-in-the-loop workflow](docs/AGENT-WORKFLOW.md) for requirements, implementation, independent review and post-merge issue completion. These run inside an active or resumed Codex session; no autonomous background service or WLED backlog run is started by checking them out.

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
| [Deployment](docs/DEPLOYMENT.md) | Proposed persistent MCPHub integration, update and rollback procedure |
| [Validation](docs/VALIDATION.md) | Meaningful automated checks, opt-in hardware checks, release criteria |
| [Implementation plan](docs/IMPLEMENTATION-PLAN.md) | Issue order, dependency graph, requirement traceability |
| [Agent handoff](docs/AGENT-HANDOFF.md) | Concrete instructions for the next implementing agent |
| [Agent workflow](docs/AGENT-WORKFLOW.md) | Five Codex role definitions, kickoff prompts, handoffs, human merge and evidenced issue completion |
| [Decision log](docs/DECISIONS.md) | Scoped project knowledge from human answers, sources and supersession |
| [Sources](docs/SOURCES.md) | Official references, reviewed alternatives, license boundaries |
| [Stage 2](docs/STAGE-2.md) | Product extensions, public-release requirements, issue map and evidence |
| [Stage 3](docs/STAGE-3.md) | Five additional usability features, dependencies and acceptance scenarios |
| [Marketplace plan](docs/MARKETPLACE.md) | Separate catalog/registry routes, distribution identities and submission sequence |
| [Configuration example](examples/devices.example.toml) | Synthetic device inventory, never an actual home-network configuration |
| [Stdio hub example](examples/mcphub.example.json) | Proposed uvx entry with separate arguments and placeholder artifact path |
| [HTTP hub example](examples/mcphub.http.example.json) | Proposed Streamable HTTP URL and placeholder service credential |

## Development status

The package has locked development/build/runtime dependencies and installed-wheel/uvx checks. Follow [DEVELOPMENT.md](docs/DEVELOPMENT.md). Use [bootstrap.toml](examples/bootstrap.toml) for an empty inventory or the executable synthetic [inventory example](examples/devices.example.toml) for configured listing/probes. State/control tools and full HTTP lifecycle remain future work.

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
