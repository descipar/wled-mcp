# Stage 2 — public project and product roadmap

Planning baseline: 2026-11-04. Tracker: [#15](https://github.com/descipar/wled-mcp/issues/15). Stage 1 remains [#1](https://github.com/descipar/wled-mcp/issues/1).

## Intent and authority

The confirmed direction is to make the project publicly available eventually and have it discoverable in MCPHub's marketplace. This stage plans what an independent user needs and which WLED features should follow the first working release. It does not change repository visibility, select a license, publish packages/images, reserve names or submit external listings now.

“Public release” means a maintained release of this project. It does not mean endorsement or ownership by the WLED project, the MCP organization or MCPHub. Metadata must represent actual authorship accurately.

Stage 1 delivers the working server, named devices, typed controls/layouts, persistent presets, both transports and actual acceptance evidence. Stage 2 builds on that foundation; it does not silently add every future feature to stage 1's completion criteria. Design/docs/release preparation can happen in parallel, but a public stable release requires the relevant stage-1 evidence.

The five later ideas—named physical zones, temporary signals, static SVG previews, evidence-based lighting explanations and effect-property search—belong to [stage 3](STAGE-3.md), tracker [#26](https://github.com/descipar/wled-mcp/issues/26), rather than this stage's launch criteria.

## Product judgment and priorities

The most useful next features are **setup and diagnosis**, **groups/scenes**, and **preset/playlist workflows**. Advanced CCT/2D support follows demonstrated device needs. Distribution, compatibility and maintenance are first-class release work: a catalog entry alone does not make installation reliable.

Priorities below:

- **Launch:** required for the proposed first public release; implementation and evidence must exist before claiming public readiness.
- **Should:** useful stage-2 product work; ship it if ready or explicitly defer it. A public release need not wait for every advanced feature.
- **Later:** outside this stage's default scope unless separately requested.

These are proposed product priorities, not individual user approvals of every technical choice. Both transports and the future public/marketplace direction are confirmed. Concrete names, support promises and license remain decisions to make with the owner.

## A. Setup that works outside the original household

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-SETUP-01 | Launch | Noninteractive setup/config validation and portable paths. A user can configure an explicit controller, start either transport and read state without editing source or knowing the private chat. Local config writes are explicit and atomic; no light changes during setup. |
| S2-SETUP-02 | Should | Optional, explicitly invoked bounded mDNS discovery returns candidate devices, deduplicates identities and requests explicit enrollment. Manual URLs remain fully supported. Explain multicast/VLAN/container limits; never silently scan subnets or enroll discovered devices. |
| S2-SETUP-03 | Launch | A read-only `doctor`/diagnostic command distinguishes package/runtime/config problems, MCP connectivity/auth, device reachability/capabilities and backup permissions. Provide a sanitized diagnostic export suitable for bug reports, with no secrets, full private inventory or unexpected telemetry. |

Suggested CLI behavior is a proposal to finalize in the setup issue: `config validate`, explicit config generation, `doctor`, and opt-in `discover`. Commands must have machine-readable output and deterministic exit status for agents. Interactive setup can be optional convenience; it must not be required by MCPHub.

## B. Groups and reusable scenes

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-GROUP-01 | Should | User-defined named groups reference existing configured device IDs and optional explicit segments. Group expansion shows exact targets; no implicit discovery. Reject unknown/duplicate/conflicting targets or resolve them under a documented policy before writing. |
| S2-GROUP-02 | Should | Versioned local scenes describe desired state across devices. Dry run resolves target capabilities and device-specific effect/palette names or mappings. Define strict preflight versus best-effort execution, bounded concurrency and ordering. Return per-device application/verification outcomes; no atomicity, frame synchronization or automatic compensating rollback claim. |

Example user outcome: “Apply Evening to both shelf strips” resolves a named scene and exact controllers, verifies each result and reports an offline strip independently. Scene definitions contain presentation intent and explicit mappings; a numeric effect ID from one firmware is not assumed portable to another.

## C. Preset portability and native playlists

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-PRESET-01 | Should | Export/import versioned preset bundles using a documented schema. Separate shareable preset content from addresses, credentials and deployment identity. Preserve supported unknown fields; report unsupported versions/fields rather than discarding them silently. |
| S2-PRESET-02 | Should | Import preview identifies destination IDs, overwrite conflicts, LED-range/capability mismatches, effect mappings and storage changes. Require explicit remapping or approved conversions; do not silently rescale a strip or overwrite a slot. Reuse stage-1 backup, persistence and uncertain-write rules. Finish explicit restore/supplied-state workflows where supported. |
| S2-PRESET-03 | Should | Author/edit native WLED playlist presets with validated referenced IDs, duration units, repeat/end behavior and active-playback implications. Reuse persistent preset verification; an independent automation scheduler is not introduced. |

Portable does not mean “guaranteed visually identical on every strip”. Color order, white handling, LED counts, firmware effects and matrix topology differ. Every conversion must be visible in the plan and tested against its declared scope. A partial import reports exactly what changed and what remains unknown; never replay uncertain writes.

## D. Capability-aware advanced segments

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-SEG-01 | Should | Complete typed grouping/spacing/offset/reverse/mirror and multiple-color controls, then RGBW/CCT options supported by observed firmware/build/device capabilities. Document units and unsupported/unknown values; do not infer support from a product name. |
| S2-SEG-02 | Should | Define 2D coordinate/range validation and layout behavior separately from 1D indices. Establish explicit overlap/layering policy where supported rather than bypassing stage-1 validation. Keep patch/replace/dry-run semantics consistent, with fixture and available-hardware evidence. |

Pixel streaming, arbitrary image/video/text rendering and audio capture are **Later**. Existing built-in effects remain available. Firmware flashing, network credentials, pin/bus configuration and factory reset are not necessary to make a public lighting MCP useful.

## E. Tool profiles and service operation

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-ACCESS-01 | Launch | Server-enforced read-only and control profiles, plus a distinct preset-management capability when available. Profile-disabled tools are omitted from listing and direct invocation is rejected. Imports, scenes and optional raw tools cannot bypass restrictions. Profiles are explicit deployment configuration applied equally to both transports. |
| S2-ACCESS-02 | Launch | Configured-device restrictions, HTTP credential storage/rotation instructions and no false isolation claims. A shared credential is not multi-user tenancy. Fine-grained per-user roles/OAuth/SaaS can remain Later; any additional credential-scoped permissions require their own tested design. |
| S2-ACCESS-03 | Launch | Bounded structured diagnostics with correlation IDs, device-independent liveness and meaningful readiness. Default operation sends no telemetry; diagnostic export is deliberate and sanitized. Status and metrics never imply unavailable devices are healthy. Avoid chatty polling that overloads small controllers. |

The single-worker v1 coordination boundary remains explicit. Multi-worker/distributed locking is Later unless measurements justify it. Increasing the worker count is not a free scalability upgrade for shared physical devices.

## F. Stable compatibility and upgrade behavior

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-COMPAT-01 | Launch | Define semantic versioning, PEP 440 mapping and one canonical version source across package/image/registry/docs. Document pre-1.0 behavior, breaking changes, deprecation and tool/result/config/backup schema evolution. No silent rename/removal of public tool fields. |
| S2-COMPAT-02 | Launch | Publish an honest support matrix for Python versions, OS/client scenarios, amd64/arm64 and WLED firmware/build capabilities. Clean-install/SDK tests are distinct from physical-device observations. Choose a narrow tested support range instead of unsupported platform badges. |
| S2-COMPAT-03 | Launch | Test upgrades and rollback with previous configuration/snapshot fixtures. Validate migrations before replacing state, preserve backups and explain when a downgrade cannot read newer data. A code rollback does not restore a device's live state automatically. |

Both stdio and Streamable HTTP remain release requirements. Test their actual installed entry points and result parity. Linux/container usage on amd64 and arm64 is the first target; Windows/macOS stdio support may be declared tested or explicitly experimental according to evidence. No requirement to own every possible device before releasing: state what was tested and keep unsupported features honest.

## G. Distribution and release artifacts

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-DIST-01 | Launch | Produce public-consumption wheel/sdist and a PyPI-ready identity so pinned uvx usage eventually needs no private Git access. Check normalized name collisions/ownership at release. A 404/name availability observation does not reserve a name. No npm wrapper is required for a Python package. |
| S2-DIST-02 | Launch | Versioned self-hosted OCI images for amd64/arm64, documented data/config/secrets mounts, appropriate unprivileged execution and explicit HTTP/stdio modes. Include digest pinning, liveness, shutdown and update/rollback instructions. HTTP support does not require a centrally hosted service. |
| S2-DIST-03 | Launch | Build/release pipeline links source commit, test results, artifacts, checksums and release notes; use narrowly scoped CI permissions and controlled publishing credentials. Include dependency/license inventory and provenance/SBOM or documented equivalents. Review vulnerability findings for material applicability. Public dependency declarations must not falsely promise the development lock freezes every user's environment. |

Preparing workflows and artifacts is authorized planning/implementation work only when commissioned. Actual PyPI/OCI publication, account setup/name reservation, public releases and visibility changes need the corresponding later release instruction. Do all concrete preparation first so the owner can review the exact candidate rather than approve an abstract proposal.

## H. Public identity, documentation and maintenance

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-PUBLIC-01 | Launch | Decide project/package/container/registry identities, author attribution and outbound license with the owner. Review reused code notices and repository history/artifacts for private content before changing visibility. Do not mark the project as officially endorsed by WLED or a marketplace without actual authorization. |
| S2-PUBLIC-02 | Launch | English quickstarts for uvx/stdio and self-hosted HTTP/Docker, generated/maintained tool reference, recipes, troubleshooting, capabilities, backups/restoration, upgrade and uninstall. Public docs must work without this chat or household-specific context. Use synthetic examples and reproducible no-hardware demonstrations. |
| S2-PUBLIC-03 | Launch | Prepare contribution guidance, security reporting/contact, support/bug templates, changelog and sustainable maintenance/release policy. State supported release lines and response expectations realistically; no unsupported SLA, mandatory hosted account or telemetry service. |

## I. Marketplace discovery and actual publication evidence

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-MARKET-01 | Launch | Prepare validated official MCP Registry `server.json`, verified publisher namespace and public package ownership metadata, version-consistent with the release. Use `io.github.<publisher>/wled-mcp` as a documentation placeholder until the publishing identity is chosen and authenticated. The registry stores metadata, not executable artifacts. |
| S2-MARKET-02 | Launch | Prepare the separate MCPHub local-catalog/MCPM entry path and, if desired, hosted MCPHub directory submission. Match current schemas, required runtime/config inputs, English descriptions and honest author status. Track drafted/submitted/accepted/visible/install-tested independently; admission and propagation are not guaranteed by our code. |
| S2-MARKET-03 | Launch | Test a fresh MCPHub installation using metadata-generated uvx configuration and separate self-hosted HTTP instructions. No private source access, real home URLs, fake remote endpoints, developer paths or committed secrets. Package listing does not publish a central WLED service; show how users supply their own controllers and endpoint. |

See [MARKETPLACE.md](MARKETPLACE.md) for researched paths and limitations. “Launch” here requires complete reviewable metadata and installation evidence; external listing acceptance may remain pending after an authorized release. Report that external state honestly rather than conflating a submitted form with marketplace availability.

## J. Beta and release decision

| ID | Priority | Requirement and observable outcome |
| --- | --- | --- |
| S2-LAUNCH-01 | Launch | Reproduce clean install/upgrade/rollback and both-transport interoperability; collect selected beta hardware evidence. An opt-in synthetic demo/simulator helps test without hardware and must never silently substitute for a real device. Record unrun tests and optional feature deferrals. |
| S2-LAUNCH-02 | Launch | Assemble one reviewable candidate: exact commit, artifact identities, license decision, public docs, known issues and listing drafts. After the actual release instruction, perform the authorized visibility/publish/submission steps and verify real install/visibility. Keep a factual status log for external review delays. |

## Issue map and order

| Issue | Work | Readiness |
| --- | --- | --- |
| [#15](https://github.com/descipar/wled-mcp/issues/15) | Stage-2 epic | Parent tracker, separate from stage 1 |
| [#16](https://github.com/descipar/wled-mcp/issues/16) | Setup, optional discovery, doctor | Setup/doctor Launch; discovery Should |
| [#17](https://github.com/descipar/wled-mcp/issues/17) | Groups and scenes | Should |
| [#18](https://github.com/descipar/wled-mcp/issues/18) | Preset portability, restore and playlists | Should |
| [#19](https://github.com/descipar/wled-mcp/issues/19) | Advanced segments, CCT and 2D | Should |
| [#20](https://github.com/descipar/wled-mcp/issues/20) | Tool profiles and service diagnostics | Launch |
| [#21](https://github.com/descipar/wled-mcp/issues/21) | Version contract, compatibility and migrations | Launch |
| [#22](https://github.com/descipar/wled-mcp/issues/22) | PyPI/OCI release pipeline | Launch |
| [#23](https://github.com/descipar/wled-mcp/issues/23) | Public docs, identity, license and maintenance | Launch |
| [#24](https://github.com/descipar/wled-mcp/issues/24) | Registry/marketplace metadata and install evidence | Launch; external acceptance separately tracked |
| [#25](https://github.com/descipar/wled-mcp/issues/25) | Beta evidence and reviewable release | Final integration of Launch criteria |

Start with portable setup and the compatibility/public-identity decisions. Product features can progress independently on the relevant stage-1 foundation. #22 needs #21; #24 needs the chosen identity/artifacts/docs; #25 assembles launch evidence after required tasks and stage-1 acceptance. #17–#19 do not automatically block #25 if explicitly deferred.

Existing stage-1 Should issue #13 remains a scope register. Link its proposed work to these owning issues; do not implement the same feature twice or quietly weaken stage-1 Must behavior.

## Stage-2 validation scenarios

| ID | Evidence expected |
| --- | --- |
| S2-T01 | Fresh-user synthetic config -> both transport starts -> successful read; doctor identifies a bad path/offline target/auth failure without mutation |
| S2-T02 | Profile-disabled operation absent from listing and rejected by direct call, scenes/import/raw paths and both transports; restricted device cannot be reached |
| S2-T03 | Group/scene with mixed capabilities/offline member produces exact preflight plan and truthful per-device outcomes; no implicit synchronization/replay |
| S2-T04 | Bundle/playlist roundtrip preserves intended fields, rejects incompatible ranges/unknown schemas, handles collisions and backup/persistence failure |
| S2-T05 | Capability fixtures distinguish RGB/RGBW/CCT/2D and unknown fields; each advertised hardware capability links actual observations |
| S2-T06 | Version/config/backup upgrade-downgrade matrix and public schema compatibility checks pass with previous fixtures |
| S2-T07 | Clean artifact installs, wheel/sdist and declared OCI architectures start both transports; provenance/version/checksum metadata are consistent |
| S2-T08 | Registry/MCPM metadata validates and generated config starts the real package in a clean MCPHub context; self-hosted HTTP recipe works without household data |
| S2-T09 | Public docs/history/artifact review, license/identity decision, secret-free diagnostics and exact release candidate are recorded |
| S2-T10 | After authorized publication only: verify actual package/image installation and each selected discovery route's independent visibility/status |

No stage-2 test has run: the server itself is not implemented. Optional-feature scenarios are required if those features ship, not invented completion claims or prerequisites for deferring them.
