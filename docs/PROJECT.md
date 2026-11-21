# Project status and maintainer guide

For maintainers and contributing agents. Users start with the [README](../README.md).

## Status

The repository is public. Releases are Git tags with a GitHub release; releases after 0.1.1 are also on PyPI as `wled-mcp` ([PUBLISHING.md](PUBLISHING.md)). The current version (`project.version` in `pyproject.toml`, the single source per [versioning](contract/versioning.md)) and the release history are in the [CHANGELOG](../CHANGELOG.md). Stage 1 (tracker [#1](https://github.com/descipar/wled-mcp/issues/1)) is closed; stage 2 ([STAGE-2.md](STAGE-2.md)) added #16 to #21 and closed out with #67, #130, #131 and the hardware check #134 ([record](validation/hardware-checks.md)). Open work follows the milestones in [ROADMAP.md](ROADMAP.md); the tools and their contract are in [TOOL-CONTRACT.md](TOOL-CONTRACT.md), the component layout in [ARCHITECTURE.md](ARCHITECTURE.md).

- **Transports.** stdio (default) and the authenticated stateless Streamable HTTP service (#14) share the same tools and resource graph; both are covered by mock and loopback tests.
- **Deployment (#11).** HTTP image and Compose example, uvx/stdio hub entry, staging helper and update/rollback procedures ([DEPLOYMENT.md](DEPLOYMENT.md)) are statically checked; one authorized live check of both modes is in [VALIDATION.md](VALIDATION.md#issue-11-live-deployment-check-2026-11-06). Drain and load moved to #12 (ISSUE-11-DEC-008); live version-to-version rollback is owned by [#25](https://github.com/descipar/wled-mcp/issues/25).
- **Hardware acceptance (#12).** One test controller, one firmware (WLED 16.0.1), both modes, three runs with restoration: [run 1](VALIDATION.md#issue-12-hardware-acceptance-2026-11-06) (HTTP load, SIGTERM drain), [run 2](VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06) (in-flight write drain, stdio H04 to H06, stdio load, owner visual checks) and [run 3](VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06) (owner-watched effect animation, speed, brightness transition). ISSUE-12-DEC-007 settles the remaining scope and moves the live H07 offline check to #25. Reboot persistence, other controllers/firmware and the other "Not run" items stay pending; no compatibility is claimed beyond these checks.
- **Findings.** Refused activation of presets saved by WLED 16 ([#66](https://github.com/descipar/wled-mcp/issues/66)) is fixed; `tools/list` builds its schemas once per server ([#67](https://github.com/descipar/wled-mcp/issues/67)); non-release builds are identified and staged ([#70](https://github.com/descipar/wled-mcp/issues/70)); the hub does not drain in-flight stdio calls when stopped (ISSUE-12-DEC-006); one write in run 3 timed out before dispatch with an unknown cause.
- **Scope (#13).** ISSUE-13-DEC-001 defers CCT/2D and further segment fields to [#19](https://github.com/descipar/wled-mcp/issues/19) and excludes the raw state patch, timers and realtime streaming.
- **Public-ready baseline (#62).** Tracked content stays installation-independent ([DEC-009](DECISIONS.md#dec-009--public-ready-repository-baseline)); `scripts/check_private_identifiers.py` enforces it in CI. License: Apache-2.0 with NOTICE ([DEC-011](DECISIONS.md#dec-011--apache-20-license-with-notice-attribution)); publication stays an owner decision ([STAGE-2.md](STAGE-2.md#h-public-identity-documentation-and-maintenance)).

[TRACEABILITY.md](TRACEABILITY.md) maps every Must requirement and scenarios T01-T21 to automated evidence and keeps hardware/deployment gaps pending. GitHub issues track status; neither an unchecked issue nor a planning paragraph proves completion.

## Documents

| File | Purpose |
| --- | --- |
| [Requirements](REQUIREMENTS.md) | Scope, identifiable requirements, priorities |
| [Tool contract](TOOL-CONTRACT.md) | Tools, parameters, results and mutation semantics |
| [WLED coverage](WLED-COVERAGE.md) | WLED features with support status and generated figures |
| [Contract examples](../examples/contracts/README.md) | Synthetic request/result cases |
| [Architecture](ARCHITECTURE.md) | Components and lifecycle |
| [Deployment](DEPLOYMENT.md) | HTTP-service and uvx/stdio deployment, update, rollback |
| [Troubleshooting](TROUBLESHOOTING.md) | Symptom-driven recovery |
| [Inventory and client](INVENTORY-CLIENT.md) | Inventory schema, bounded HTTP client |
| [Development](DEVELOPMENT.md) | Local checks, build, CI-equivalent commands |
| [Validation](VALIDATION.md) | Automated and opt-in hardware checks, per-issue evidence |
| [Traceability](TRACEABILITY.md) | Must requirements and T01-T21 to evidence |
| [Agent workflow](AGENT-WORKFLOW.md) | Roles, handoffs, human merge, issue completion |
| [Decision log](DECISIONS.md) | Scoped owner decisions |
| [Sources](SOURCES.md) | References, reviewed alternatives, license boundaries |
| [Roadmap](ROADMAP.md), [Stage 2](STAGE-2.md), [Stage 3](STAGE-3.md), [Stage 5](STAGE-5.md) | Milestones and requirement tables |
| [Marketplace](MARKETPLACE.md) | Catalog/registry routes and identities |

## Working on an issue

1. Read [AGENTS.md](../AGENTS.md), this page, the [requirements](REQUIREMENTS.md), the [decision log](DECISIONS.md) with the [issue records](decisions/README.md), the [tool contract](TOOL-CONTRACT.md) and the [architecture](ARCHITECTURE.md).
2. Use the GitHub issue and the [roadmap](ROADMAP.md) for scope and order.
3. Follow the [agent workflow](AGENT-WORKFLOW.md) ([shared roles](../agents/README.md)); record evidence in [VALIDATION.md](VALIDATION.md) and keep [TRACEABILITY.md](TRACEABILITY.md) honest. Roles run inside an active client session; checking them out starts nothing, and merges remain a human decision.
4. Run the CI-equivalent commands in [DEVELOPMENT.md](DEVELOPMENT.md#checks-and-build) before proposing a change; examples must stay synthetic (`.example`, `.invalid`, `.test` names, documentation address ranges).
