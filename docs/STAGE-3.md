# Stage 3 — lighting experience and agent usability

Planning baseline: 2026-11-04. Tracker: [#26](https://github.com/descipar/wled-mcp/issues/26).

The five additional ideas are assigned to stage 3 by the user's scope decision. Stage 1 (#1) remains the working server; stage 2 (#15) remains public-release readiness and its existing product roadmap. Stage-3 features are not prerequisites for a first public release. This assignment creates requirements/issues only; no feature is implemented or tested yet.

## Work order

Superseded by milestones ([DEC-029](DECISIONS.md#dec-029--milestones-instead-of-stages)): the order and grouping of these issues are in [ROADMAP.md](ROADMAP.md). The earlier order of [DEC-027](DECISIONS.md#dec-027--re-stage-the-open-work-by-value-per-effort) is kept as history. This document keeps the requirement tables.

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

All features reuse the versioned tool/result contract, capability handling, authorization/profile checks, per-device coordination and uncertain-write behavior. Supporting both transports does not permit one adapter to expose weaker restrictions.

## Scope and sequencing

| Work | Foundation / coordination | Suggested order |
| --- | --- | --- |
| Named zones #27 | Stage-1 controls/layouts #6/#7; coordinate with groups/scenes #17 | First: high practical value without timing service logic |
| Static preview #29 | State/layouts #5/#7; optional zone labels #27 and matrix #19 | Alongside/after zones; useful for inspection and proposed changes |
| Explanations #30 | State/control evidence #5/#6; doctor #16 and diagnostics #20 | Reuse diagnostics rather than build a separate subsystem |
| Effect search #31 | Catalogs #5 and compatibility policy #21 | Start with a small reviewed taxonomy, expand with evidence |
| Temporary signals #28 | Controls/layouts #6/#7, shared HTTP lifecycle #14 and profiles #20 | After restoration/conflict/restart semantics are finalized |

The order is a recommendation, not an instruction to implement now. Temporary signals add a bounded operation lifecycle; they must not quietly introduce a general scheduler contrary to earlier scope. Scene/zone changes need explicit conflict semantics. Missing optional dependencies should narrow advertised functionality rather than create hidden assumptions.

## Agent-facing examples

- A named-zone command resolves “example shelf left” into a documented range and shows whether the existing layout supports that operation.
- A signal displays a selected color for a requested interval, then restores relevant prior state only if no intervening change is observed. An offline device can leave the outcome uncertain; report that rather than replaying later without policy.
- A preview shows how a proposed split covers a synthetic 60-LED strip, including gaps, without changing any device.
- A diagnostic reports an observed active-playback indicator as one possible explanation for a verification mismatch; it does not assert a cause it cannot prove.
- Effect search returns only available effects, explaining verified and unverified properties. Applying one is a separate explicit mutation.

## Acceptance scenarios

| ID | Required evidence if the feature ships |
| --- | --- |
| S3-T01 | Zone resolution with multiple spans/reversed physical order, stale layout, unknown/ambiguous names and restricted targets; no silent range spill or implicit layout writes |
| S3-T02 | Controlled-clock signal lifecycle: cancellation, overlap, external edits, disconnect, timeout, crash/restart, stale recovery and failed restoration; no blind replay |
| S3-T03 | SVG structural/snapshot checks for sparse IDs, gaps/overlaps, large strips, escaped labels, invalid plans and unsupported color/geometry; no device mutation |
| S3-T04 | Diagnostics with competing plausible causes, missing firmware indicators, stale evidence and unattributable mismatch; no corrective POSTs or sensitive output |
| S3-T05 | Effect catalog with changed IDs, missing metadata, strict/partial filters, ambiguous names and firmware differences; unknown flashing/motion properties do not become guarantees |

Run domain/mocked tests and both transport adapters without LAN devices by default. Add opt-in physical validation only where needed and authorized. A static layout preview is not evidence of physical color accuracy or firmware animation fidelity. Update issue status and public tool docs only when behavior is actually implemented and verified.
