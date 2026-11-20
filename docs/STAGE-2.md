# Stage 2 — public project and product roadmap

Planning baseline: 2026-11-04. Tracker: [#15](https://github.com/descipar/wled-mcp/issues/15). Stage 1 remains [#1](https://github.com/descipar/wled-mcp/issues/1). Open work is organised by milestones ([ROADMAP.md](ROADMAP.md), [DEC-029](DECISIONS.md#dec-029--milestones-instead-of-stages)); this document keeps the requirement tables and scenario IDs.

## Intent and authority

The confirmed direction is a publicly available, maintained project that is discoverable in MCPHub's marketplace. "Public release" does not mean endorsement or ownership by the WLED project, the MCP organization or MCPHub; metadata states the actual authorship. The first public release is staged ([DEC-023](DECISIONS.md#dec-023--staged-first-public-release)); publication, visibility, license and listing steps need the owner's explicit instruction. Stage 1 delivers the working server; the later ideas (zones, signals, previews, explanations, effect search) are in [STAGE-3.md](STAGE-3.md). Launch requirements that were not met at close-out (#22 to #25) moved to [STAGE-5.md](STAGE-5.md) ([DEC-027](DECISIONS.md#dec-027--re-stage-the-open-work-by-value-per-effort)) and must not be described as delivered.

Priorities: **Launch** is required for public readiness, **Should** is useful and ships if ready or is explicitly deferred, **Later** is out of default scope. Both transports and the public direction are confirmed; names, support promises and license were decided with the owner (see the list below).

## A. Setup that works outside the original installation

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-SETUP-01 | Launch | Noninteractive setup/config validation and portable paths. A user configures an explicit controller, starts either transport and reads state without editing source. Local config writes are explicit and atomic; no light changes during setup. |
| S2-SETUP-02 | Should | Optional, explicitly invoked bounded mDNS discovery returns candidates, deduplicates identities and requests explicit enrollment. Manual URLs stay fully supported; never silently scan or enroll. Extended by M8 (DEC-035): [contract/discovery.md](contract/discovery.md). |
| S2-SETUP-03 | Launch | A read-only `doctor` command distinguishes package/runtime/config problems, MCP connectivity/auth, device reachability/capabilities and backup permissions, with a sanitized diagnostic export (no secrets, no full inventory, no telemetry). |

CLI commands have machine-readable output and deterministic exit status; interactive setup is optional.

## B. Groups and reusable scenes

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-GROUP-01 | Should | Named groups reference configured device IDs and optional explicit segments. Expansion shows exact targets; no implicit discovery. Unknown/duplicate/conflicting targets are rejected or resolved under a documented policy before writing. |
| S2-GROUP-02 | Should | Versioned local scenes describe desired state across devices. Dry run resolves capabilities and device-specific effect/palette names. Strict preflight versus best-effort execution, bounded concurrency, per-device outcomes; no atomicity, frame synchronization or automatic rollback claim. |

## C. Preset portability and native playlists

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-PRESET-01 | Should | Export/import versioned preset bundles with a documented schema, separated from addresses, credentials and deployment identity. Unknown fields are preserved; unsupported versions/fields are reported. |
| S2-PRESET-02 | Should | Import preview shows destination IDs, overwrite conflicts, LED-range/capability mismatches, effect mappings and storage changes; explicit remapping, no silent rescale or overwrite. Reuses stage-1 backup, persistence and uncertain-write rules; restore workflows where supported. |
| S2-PRESET-03 | Should | Author native WLED playlist presets with validated IDs, duration units, repeat/end behavior and active-playback implications; no independent scheduler. |

Portable does not mean visually identical on every strip; every conversion is visible in the plan and a partial import reports what changed. Uncertain writes are never replayed.

## D. Capability-aware advanced segments

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-SEG-01 | Should | Typed grouping/spacing/offset/reverse/mirror and multiple-color controls, then RGBW/CCT options supported by observed firmware/build/device capabilities; support is never inferred from a product name. |
| S2-SEG-02 | Should | 2D coordinate/range validation and layout behavior separate from 1D indices, with an explicit overlap policy where supported; patch/replace/dry-run semantics stay consistent. |

Pixel streaming, image/video/text rendering and audio capture are **Later**; so are firmware flashing, network credentials, pin/bus configuration and factory reset.

## E. Tool profiles and service operation

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-ACCESS-01 | Launch | Server-enforced read-only and control profiles plus a distinct preset-management capability. Profile-disabled tools are omitted from listing and rejected on direct invocation; imports, scenes and raw tools cannot bypass them. Same configuration on both transports. |
| S2-ACCESS-02 | Launch | Configured-device restrictions, HTTP credential storage/rotation instructions and no false isolation claims; a shared credential is not multi-user tenancy. Per-user roles/OAuth are Later. |
| S2-ACCESS-03 | Launch | Bounded structured diagnostics with correlation IDs, device-independent liveness and meaningful readiness. No default telemetry; sanitized deliberate export; status never implies unavailable devices are healthy; no chatty polling. |

The single-worker v1 coordination boundary stays explicit; multi-worker locking is Later.

## F. Stable compatibility and upgrade behavior

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-COMPAT-01 | Launch | Semantic versioning, PEP 440 mapping and one canonical version source across package/image/registry/docs; documented pre-1.0 behavior, deprecation and schema evolution. No silent rename/removal of public tool fields. |
| S2-COMPAT-02 | Launch | Honest support matrix (Python, OS/client, amd64/arm64, WLED firmware/build) per [DEC-020](DECISIONS.md#dec-020--support-and-version-policy): WLED 16.0.0 or newer, firmware tiers tested/expected/unknown, Python as tested in CI, Linux supported, Windows/macOS experimental. Clean-install tests are distinct from device observations. |
| S2-COMPAT-03 | Launch | Test upgrade and rollback with previous configuration/snapshot fixtures; validate migrations before replacing state, preserve backups, explain unreadable newer data. A code rollback does not restore live device state. |

## G. Distribution and release artifacts

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-DIST-01 | Launch | Public wheel/sdist and a PyPI-ready identity so pinned uvx usage needs no private access; check name collisions at release (availability does not reserve a name). |
| S2-DIST-02 | Launch | Versioned self-hosted OCI images (amd64/arm64) with documented data/config/secrets mounts, unprivileged execution, explicit HTTP/stdio modes, digest pinning, liveness, shutdown and update/rollback instructions. |
| S2-DIST-03 | Launch | A release pipeline linking source commit, test results, artifacts, checksums and notes, with narrowly scoped CI permissions, dependency/license inventory, provenance/SBOM or documented equivalents and a vulnerability review. Dependency declarations do not promise that the development lock freezes a user's environment. |

Preparing workflows is authorized only when commissioned; PyPI/OCI publication, name reservation, releases and visibility changes need a later release instruction.

## H. Public identity, documentation and maintenance

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-PUBLIC-01 | Launch | Project/package/container/registry identities, author attribution and outbound license decided with the owner; reused-code notices and history reviewed for private content before visibility changes; no claimed endorsement by WLED or a marketplace. |
| S2-PUBLIC-02 | Launch | English quickstarts (uvx/stdio, self-hosted HTTP/Docker), tool reference, recipes, troubleshooting, capabilities, backups, upgrade and uninstall that work without project history, with synthetic examples. |
| S2-PUBLIC-03 | Launch | Contribution guidance, security statement (no security support, [DEC-013](DECISIONS.md#dec-013--general-contact-and-no-security-support)), support/bug templates, changelog and a realistic maintenance/release policy; no SLA, hosted account or telemetry service. |

Owner decisions for publication (from #62, tracked by [#23](https://github.com/descipar/wled-mcp/issues/23)) are all resolved: license [DEC-011](DECISIONS.md#dec-011--apache-20-license-with-notice-attribution); identities [DEC-012](DECISIONS.md#dec-012--project-and-package-identity) (`descipar/wled-mcp`, PyPI `wled-mcp`, `ghcr.io/descipar/wled-mcp`, registry `io.github.descipar/wled-mcp`, unofficial); contact and no security support DEC-013; history [DEC-014](DECISIONS.md#dec-014--keep-the-existing-git-history); issue/PR review before visibility [DEC-015](DECISIONS.md#dec-015--issue-and-pr-review-before-visibility-change); agent tooling ships [DEC-016](DECISIONS.md#dec-016--ship-the-agent-tooling-and-decision-records); verbatim owner quotes with translation [DEC-017](DECISIONS.md#dec-017--verbatim-owner-quotes-with-english-translation); private denylist and branch rules [DEC-018](DECISIONS.md#dec-018--private-denylist-and-main-branch-rules); visibility before release [DEC-019](DECISIONS.md#dec-019--make-the-repository-public-before-the-release) (#90).

## I. Marketplace discovery and publication evidence

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-MARKET-01 | Launch | Validated official MCP Registry `server.json` with the verified namespace `io.github.descipar/wled-mcp` (DEC-012), version-consistent with the release; the registry stores metadata only. |
| S2-MARKET-02 | Launch | The separate MCPHub local-catalog/MCPM entry path and, if desired, a hosted directory submission; current schemas, English descriptions, honest author status. Drafted/submitted/accepted/visible/install-tested are tracked independently. |
| S2-MARKET-03 | Launch | A fresh MCPHub installation test with metadata-generated uvx configuration and separate self-hosted HTTP instructions; no private paths, fake remotes or committed secrets; users supply their own controllers. |

See [MARKETPLACE.md](MARKETPLACE.md). External acceptance may stay pending after an authorized release and is reported as such.

## J. Beta and release decision

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-LAUNCH-01 | Launch | Clean install/upgrade/rollback, both-transport interoperability and selected beta hardware evidence; unrun tests and deferrals recorded. The simulator was dropped by the owner ([ISSUE-25-DEC-001](decisions/issue-25.md)). |
| S2-LAUNCH-02 | Launch | One reviewable candidate (exact commit, artifact identities, license, docs, known issues, listing drafts); after the release instruction, perform and verify the authorized steps with a factual status log. |

## Issue map

| Issue | Work | Readiness |
| --- | --- | --- |
| [#15](https://github.com/descipar/wled-mcp/issues/15) | Stage-2 epic | Parent tracker |
| [#16](https://github.com/descipar/wled-mcp/issues/16) | Setup, optional discovery, doctor | Setup/doctor Launch; discovery Should |
| [#17](https://github.com/descipar/wled-mcp/issues/17) | Groups and scenes | Should |
| [#18](https://github.com/descipar/wled-mcp/issues/18) | Preset portability, restore and playlists | Should |
| [#19](https://github.com/descipar/wled-mcp/issues/19) | Advanced segments, CCT and 2D | Should |
| [#20](https://github.com/descipar/wled-mcp/issues/20) | Tool profiles and service diagnostics | Launch |
| [#21](https://github.com/descipar/wled-mcp/issues/21) | Version contract, compatibility and migrations | Launch |
| [#22](https://github.com/descipar/wled-mcp/issues/22) | PyPI/OCI release pipeline | Launch |
| [#23](https://github.com/descipar/wled-mcp/issues/23) | Public docs, identity, license and maintenance | Launch |
| [#90](https://github.com/descipar/wled-mcp/issues/90) | Visibility readiness (DEC-019) | Before release |
| [#24](https://github.com/descipar/wled-mcp/issues/24) | Registry/marketplace metadata and install evidence | Launch |
| [#25](https://github.com/descipar/wled-mcp/issues/25) | Beta evidence and reviewable release | Final integration |

Stage-1 Should issue #13 deferred its work to #16, #18 and #19 (ISSUE-13-DEC-001); do not implement a feature twice or weaken stage-1 Must behavior.

## Stage-2 validation scenarios

| ID | Evidence expected |
| --- | --- |
| S2-T01 | Fresh synthetic config, both transports start and read; doctor identifies a bad path/offline target/auth failure without mutation |
| S2-T02 | Profile-disabled operation absent from listing and rejected by direct call, scenes/import/raw paths and both transports; restricted device unreachable |
| S2-T03 | Group/scene with mixed capabilities/offline member gives an exact preflight plan and truthful per-device outcomes |
| S2-T04 | Bundle/playlist roundtrip preserves intended fields, rejects incompatible ranges/unknown schemas, handles collisions and backup/persistence failure |
| S2-T05 | Capability fixtures distinguish RGB/RGBW/CCT/2D and unknown fields |
| S2-T06 | Version/config/backup upgrade-downgrade matrix and schema compatibility pass with previous fixtures |
| S2-T07 | Clean wheel/sdist and OCI installs start both transports with consistent version/checksum metadata |
| S2-T08 | Registry/MCPM metadata validates and generated config starts the real package in a clean MCPHub context |
| S2-T09 | Public docs/history/artifact review, license/identity decision and the release candidate are recorded |
| S2-T10 | After authorized publication only: real package/image installation and each listing route's status |

Optional-feature scenarios are required only if those features ship.
