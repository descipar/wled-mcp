# WLED MCP

Private specification and implementation backlog for a WLED MCP server used through Kai's existing MCPHub.

**Status, 2026-11-04:** planning and handoff only. There is no implementation, installable package, deployed server, or validated hardware compatibility yet. Repository creation and issue creation were requested; installing software or changing lighting was not requested.

## Goal

Let an agent inspect and control several WLED controllers by meaningful names, create and modify segment layouts, and manage presets through clear MCP tools. Reuse WLED's built-in effects rather than building an animation engine. Keep operation lightweight enough for the existing Raspberry Pi hub.

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
| [Tool contract](docs/TOOL-CONTRACT.md) | Proposed tools, parameters, result format, mutation semantics |
| [Architecture](docs/ARCHITECTURE.md) | Components, runtime, configuration, design decisions |
| [Deployment](docs/DEPLOYMENT.md) | Proposed persistent MCPHub integration, update and rollback procedure |
| [Validation](docs/VALIDATION.md) | Meaningful automated checks, opt-in hardware checks, release criteria |
| [Implementation plan](docs/IMPLEMENTATION-PLAN.md) | Issue order, dependency graph, requirement traceability |
| [Agent handoff](docs/AGENT-HANDOFF.md) | Concrete instructions for the next implementing agent |
| [Sources](docs/SOURCES.md) | Official references, reviewed alternatives, license boundaries |
| [Configuration example](examples/devices.example.toml) | Synthetic device inventory, never an actual home-network configuration |
| [Hub example](examples/mcphub.example.json) | Proposed stdio entry with separate arguments and placeholder paths |

## Development status

No bootstrap commands are claimed to work yet. The first implementation issue must add packaging, dependency locking, the console entry point, and reproducible development commands. Tools and configuration in these documents are the proposed v1 contract, not a description of existing executable behavior.

## Boundaries

- No cloud account, public endpoint, web interface, or MQTT broker required for v1.
- Home Assistant remains available. Direct WLED access adds detailed layout and preset authoring; routine light control overlaps intentionally.
- Device inventory, firmware versions, topology, RGBW/CCT/2D needs, and test-device availability are still unknown.
- Repository remains private. A distribution license has not been selected; upstream code has not been copied.
- GitHub issues track implementation status. This repository documents the contract and decisions; neither an unchecked issue nor a planning paragraph proves completion.

Repository: https://github.com/descipar/wled-mcp

Backlog: [delivery tracker #1](https://github.com/descipar/wled-mcp/issues/1), with twelve child issues covering contract, implementation, validation, integration and optional scope. Start implementation with [contract decisions #2](https://github.com/descipar/wled-mcp/issues/2).
