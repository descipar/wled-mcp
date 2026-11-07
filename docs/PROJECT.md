# Project status and maintainer guide

This page is for maintainers and contributing agents: delivery status, roadmap,
document index and the agent workflow. Users start with the [README](../README.md).

## Status

Package version 0.1.0 carries the stage-1 scope below. All stage-1 work packages listed
in delivery tracker [#1](https://github.com/descipar/wled-mcp/issues/1) are closed, and
the tracker itself was closed as completed on 2026-11-06. Deferred items and remaining limits are tracked in the
linked follow-up issues. Nothing has been published.

- **Package and transports.** An installable Python 3.13 package with the console
  command `wled-mcp`. stdio is the default transport; the authenticated stateless
  Streamable HTTP service (`--transport streamable-http`, #14) shares the same tools and
  resource graph. Both are covered by mock and loopback tests.
- **Tools.** Validated inventory and `wled_list_devices`; the read-only
  `wled_get_state`, `wled_get_effects` and `wled_get_palettes` (#5); the typed
  `wled_set_state` and `wled_patch_segments` (#6); `wled_replace_layout` (#7); and the
  persistent-preset tools `wled_list_presets`, `wled_get_preset`,
  `wled_activate_preset`, `wled_save_preset` and `wled_delete_preset` (#9) with a
  durable snapshot before overwrite/delete (#8). There is no restore tool; restore and
  supplied-state save are deferred to [#18](https://github.com/descipar/wled-mcp/issues/18)
  per ISSUE-13-DEC-001. Listing is network-free by default; explicit probes and reads
  use bounded requests to configured devices; effect/palette catalogs have a
  firmware-aware cache.
- **Deployment artifacts (#11).** HTTP image and Compose example, uvx/stdio hub entry,
  staging helper and update/rollback procedures in [DEPLOYMENT.md](DEPLOYMENT.md) are
  statically checked. One authorized live check of both modes ran on one MCPHub target
  ([validation](VALIDATION.md#issue-11-live-deployment-check-2026-11-06)), followed by a
  live removal and redeploy of the HTTP service, catalog/preset reads and a hub
  container recreation. Drain on the target and the
  load measurements moved to #12 per ISSUE-11-DEC-008. Live version-to-version update/rollback moved to stage 2
  ([#21](https://github.com/descipar/wled-mcp/issues/21),
  [#25](https://github.com/descipar/wled-mcp/issues/25)); the documented procedures stay
  in #11.
- **Hardware acceptance (#12).** Recorded for one test controller on one firmware
  (WLED 16.0.1) in both modes, in three runs with restoration: the first through the
  HTTP mode, including HTTP load and a SIGTERM drain in which read calls sent before
  the stop command completed with HTTP 200 and at least one was certainly in flight at
  the signal ([run 1](VALIDATION.md#issue-12-hardware-acceptance-2026-11-06)); the
  second in both modes with an in-flight write drain, peak connections, stdio H04-H06,
  rate-limited stdio load through the hub, a stdio drain finding and owner visual
  checks ([run 2](VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06)); the
  third an owner-watched HTTP check of effect animation, speed and a brightness
  transition ([run 3](VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06)).
  ISSUE-12-DEC-007 settles the remaining #12 scope (UI comparison through the
  controller endpoints, stdio H04/drain/load as recorded) and moves the live H07
  offline check to stage 2 ([#25](https://github.com/descipar/wled-mcp/issues/25)).
  Reboot persistence, other controllers and firmware and the other "Not run" items
  remain pending. No hardware compatibility is claimed beyond these checks.
- **Findings and follow-ups.** The refused activation of presets saved by WLED 16
  ([#66](https://github.com/descipar/wled-mcp/issues/66)) is fixed and was re-checked on
  that controller in run 2. `tools/list` is CPU-bound on small hosts
  ([#67](https://github.com/descipar/wled-mcp/issues/67)). In stdio mode the hub does not
  drain in-flight calls when the entry is stopped (a documented stdio limitation,
  ISSUE-12-DEC-006). Staging of non-release builds is not yet defined
  ([#70](https://github.com/descipar/wled-mcp/issues/70)). One write in run 3 timed out
  before dispatch with an unknown cause.
- **Scope decisions (#13).** ISSUE-13-DEC-001 keeps inventory changes to a documented
  restart (reload and a validate command in
  [#16](https://github.com/descipar/wled-mcp/issues/16)), defers CCT/2D and further
  segment fields to [#19](https://github.com/descipar/wled-mcp/issues/19), and excludes
  the raw state patch, timers and realtime streaming from stage 1.
- **Public-ready baseline (#62).** Tracked content is kept installation-independent
  under [DEC-009](DECISIONS.md#dec-009--public-ready-repository-baseline);
  `scripts/check_private_identifiers.py` enforces it in CI. The outbound license is
  Apache-2.0 with a NOTICE file ([DEC-011](DECISIONS.md#dec-011--apache-20-license-with-notice-attribution));
  visibility and publication remain owner decisions listed in
  [STAGE-2.md](STAGE-2.md#open-owner-decisions-before-publication-from-62).

[TRACEABILITY.md](TRACEABILITY.md) maps every Must requirement and scenarios T01-T21
to automated evidence and keeps hardware/deployment gaps visibly pending. GitHub issues
track implementation status; neither an unchecked issue nor a planning paragraph proves
completion.

## Roadmap

- **Stage 1** — first usable server; tracker
  [#1](https://github.com/descipar/wled-mcp/issues/1). Requirements in
  [REQUIREMENTS.md](REQUIREMENTS.md), contract decisions in
  [#2](https://github.com/descipar/wled-mcp/issues/2).
- **Stage 2** — reusable public project: portable setup, groups/scenes, preset
  portability, advanced segments, tool profiles, compatibility policy, release pipeline,
  public documentation and marketplace listings. Tracker
  [#15](https://github.com/descipar/wled-mcp/issues/15) with child issues #16-#25, #44, #67 and #70
  (label `stage:2`); see [STAGE-2.md](STAGE-2.md) and [MARKETPLACE.md](MARKETPLACE.md).
  These do not silently expand stage-1 acceptance.
- **Stage 3** — named lighting zones, temporary signals, static layout previews,
  explanations of ineffective changes and property-based effect search. Tracker
  [#26](https://github.com/descipar/wled-mcp/issues/26) with child issues #27-#31 (label
  `stage:3`); see [STAGE-3.md](STAGE-3.md). Stage 3 does not block stage-2 publication.

## Documents

| File | Purpose |
| --- | --- |
| [Requirements](REQUIREMENTS.md) | Context, scope, identifiable requirements, priorities, unresolved inputs |
| [Tool contract](TOOL-CONTRACT.md) | V1 design: tools, parameters, result format and mutation semantics |
| [Contract examples](../examples/contracts/README.md) | Synthetic patch/layout/preset/error cases and snapshot format |
| [Architecture](ARCHITECTURE.md) | Components, runtime, configuration, design decisions |
| [Deployment](DEPLOYMENT.md) | HTTP-service and uvx/stdio MCPHub deployment: build/stage, update, rollback, removal |
| [Inventory and client](INVENTORY-CLIENT.md) | Inventory schema and limits, bounded HTTP client behavior |
| [Development](DEVELOPMENT.md) | Local checks, build, wheel launch and CI-equivalent commands |
| [Validation](VALIDATION.md) | Meaningful automated checks, opt-in hardware checks, per-issue evidence records |
| [Traceability](TRACEABILITY.md) | Must requirements and T01-T21 to automated evidence; hardware/deployment gaps marked pending |
| [Implementation plan](IMPLEMENTATION-PLAN.md) | Issue order, dependency graph, requirement traceability |
| [Hardware quick path](HARDWARE-QUICKPATH.md) | Read-only probe first, then authorized hardware checks |
| [Agent handoff](AGENT-HANDOFF.md) | Concrete instructions for the next implementing agent |
| [Agent workflow](AGENT-WORKFLOW.md) | Five shared roles with native Codex/Claude adapters, handoffs, human merge and evidenced issue completion |
| [Decision log](DECISIONS.md) | Scoped project knowledge from owner answers, sources and supersession |
| [Sources](SOURCES.md) | Official references, reviewed alternatives, license boundaries |
| [Stage 2](STAGE-2.md) | Product extensions, public-release requirements, issue map and evidence |
| [Stage 3](STAGE-3.md) | Five additional usability features, dependencies and acceptance scenarios |
| [Marketplace plan](MARKETPLACE.md) | Separate catalog/registry routes, distribution identities and submission sequence |

## Working on an issue

1. Read [AGENTS.md](../AGENTS.md) and this page.
2. Read the [requirements](REQUIREMENTS.md), especially authority, priorities and
   acceptance conditions, and the [decision log](DECISIONS.md) with the applicable
   [issue records](decisions/README.md).
3. Read the [tool contract](TOOL-CONTRACT.md) and the [architecture](ARCHITECTURE.md).
4. Use the [implementation plan](IMPLEMENTATION-PLAN.md) and its linked GitHub issues.
5. Work from the [agent handoff](AGENT-HANDOFF.md); record evidence in
   [VALIDATION.md](VALIDATION.md) and keep [TRACEABILITY.md](TRACEABILITY.md) honest.

The repository includes [shared Codex and Claude Code roles](../agents/README.md) and a
[human-in-the-loop workflow](AGENT-WORKFLOW.md) for requirements, implementation,
independent review and post-merge issue completion. These run inside an active or
resumed client session; no autonomous background service or backlog run is started by
checking them out. Merges remain a human decision. Run the CI-equivalent commands in
[DEVELOPMENT.md](DEVELOPMENT.md#checks-and-build) before proposing a change; they include
the private-identifier check, so examples must stay synthetic (`.example`, `.invalid`,
`.test` names and documentation address ranges).
