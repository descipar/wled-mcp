# Stage 3 — lighting experience and agent usability

Planning baseline: 2026-11-04. Tracker: [#26](https://github.com/descipar/wled-mcp/issues/26).

The five additional ideas are not prerequisites for a first public release; stage 1 (#1) is the working server and stage 2 (#15) is public-release readiness.

## Work order

Order and grouping follow the milestones ([DEC-029](DECISIONS.md#dec-029--milestones-instead-of-stages), [ROADMAP.md](ROADMAP.md)); this document keeps the requirement tables.

## Requirements and owning issues

| ID | Requirement | Issue |
| --- | --- | --- |
| S3-ZONE-01 | Versioned named physical zones resolve to configured controller IDs and explicit segment/range targets. Preview the mapping without writing; do not infer geometry from names or enroll devices. | [#27](https://github.com/descipar/wled-mcp/issues/27) |
| S3-ZONE-02 | Validate stale topology, ambiguous names and overlapping/conflicting targets. Define existing-segment versus explicit layout-change behavior so a zone command cannot silently affect LEDs outside the requested region. Apply profiles and device restrictions after target resolution. | [#27](https://github.com/descipar/wled-mcp/issues/27) |
| S3-SIGNAL-01 | A temporary signal has an explicit target, bounded duration, operation ID, dry run, status and cancellation policy. Capture relevant restorable state, use device locks, and define overlapping-signal behavior. Never create/overwrite persistent presets merely to display a temporary signal. | [#28](https://github.com/descipar/wled-mcp/issues/28) |
| S3-SIGNAL-02 | Restore conditionally only when the operation's relevant state still matches; skip on observed intervening edits. Define offline/uncertain outcome, restart/shutdown recovery, expired work and bounded task cleanup. No blind write replay or guarantee of exact duration across outages; a general scheduler remains separate scope. | [#28](https://github.com/descipar/wled-mcp/issues/28) |
| S3-PREVIEW-01 | Produce a static SVG of observed state or a validated proposed layout: boundaries/IDs, ranges, representative colors, gaps and overlaps. Label source, scale, exclusive endpoints, missing geometry and color approximations. Do not claim animated effect simulation. | [#29](https://github.com/descipar/wled-mcp/issues/29) |
| S3-PREVIEW-02 | Keep previews read-only with bounded output and identical documented delivery across transports. Escape labels and exclude scripts, external URLs and private data. Start with 1D; 2D requires an explicitly validated matrix geometry, not inferred coordinates. | [#29](https://github.com/descipar/wled-mcp/issues/29) |
| S3-EXPLAIN-01 | Diagnose ineffective/nonpersistent light changes from timestamped available observations. Separate observed facts, inferred causes and uncertainty; return evidence and next checks, not unsupported attribution to a particular external actor. | [#30](https://github.com/descipar/wled-mcp/issues/30) |
| S3-EXPLAIN-02 | Extend existing diagnostics with bounded read-only lighting-state analysis. Do not stop playback, disable realtime inputs or apply corrective writes automatically. Missing indicators and ambiguous explanations remain explicit; avoid sensitive configuration dumps. | [#30](https://github.com/descipar/wled-mcp/issues/30) |
| S3-EFFECT-01 | Search a curated, versioned effect-property catalog intersected with the target device's real effect catalog. Properties may include motion, flashing, color/palette use and strip-length suitability, with provenance, confidence and firmware/build matching. IDs are not assumed universal. | [#31](https://github.com/descipar/wled-mcp/issues/31) |
| S3-EFFECT-02 | Explain matches and unverified properties; unknown behavior cannot satisfy a strict filter requiring verified properties. Search is read-only; applying a result uses an explicit existing control call. No mandatory cloud/LLM account, telemetry or unverified promise to classify every effect. | [#31](https://github.com/descipar/wled-mcp/issues/31) |

All features reuse the versioned tool/result contract, capability handling, profile checks, per-device coordination and uncertain-write behavior on both transports. Temporary signals must not grow into a general scheduler; missing optional dependencies narrow advertised functionality.

## Acceptance scenarios

| ID | Required evidence if the feature ships |
| --- | --- |
| S3-T01 | Zone resolution with multiple spans/reversed physical order, stale layout, unknown/ambiguous names and restricted targets; no silent range spill or implicit layout writes |
| S3-T02 | Controlled-clock signal lifecycle: cancellation, overlap, external edits, disconnect, timeout, crash/restart, stale recovery and failed restoration; no blind replay |
| S3-T03 | SVG structural/snapshot checks for sparse IDs, gaps/overlaps, large strips, escaped labels, invalid plans and unsupported color/geometry; no device mutation |
| S3-T04 | Diagnostics with competing plausible causes, missing firmware indicators, stale evidence and unattributable mismatch; no corrective POSTs or sensitive output |
| S3-T05 | Effect catalog with changed IDs, missing metadata, strict/partial filters, ambiguous names and firmware differences; unknown flashing/motion properties do not become guarantees |

Tests run mocked on both transports without LAN devices; physical validation is opt-in and authorized. A static layout preview is no evidence of physical color accuracy or animation fidelity.
