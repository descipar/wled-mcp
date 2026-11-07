# Issue #21 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-21-DEC-001 — Update and rollback evidence

- ID: ISSUE-21-DEC-001
- Recorded date: 2026-11-07
- Status: active for issues #21 and #25.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-07 to the Phase-0
  questions of the stage-2 parallel plan (DEC-021), packet
  `.agent-runs/stage2/issue-21/packet.md` (Q1): "alles nach empfehlung"
  (English: "everything as recommended"); no permalink.
- Scope: closure evidence for S2-COMPAT-03 (version-to-version update and rollback of
  the deployed service, HTTP and uvx/stdio).
- Decision: #21 closes on automated upgrade/rollback tests plus the documented
  procedure. The live update/rollback run on the deployed target is evidence for #25
  (S2-LAUNCH-01), performed once with the published artifacts.
- Applicability / conditions / expiry: the live run needs its own operation
  authorization when #25 reaches it; this entry does not authorize it.
- Rationale supplied: none beyond accepting the recommendation; the packet rationale
  (one live operation with the final artifacts, no second authorization) is agent
  analysis.
- Affected requirement IDs, files, issues and tests: S2-COMPAT-03, S2-LAUNCH-01;
  issues #21, #25; ISSUE-11-DEC-005 expectation of a live run is satisfied in #25.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-21 packet; #25.
- Revalidation needed / next action: none before implementation.

## ISSUE-21-DEC-002 — Technical defaults TD-21-1 to TD-21-10

- ID: ISSUE-21-DEC-002
- Recorded date: 2026-11-07
- Status: active for issue #21 (with #70, absorbed per DEC-021).
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: coordinator acceptance on 2026-11-07 of the technical defaults TD-21-1 to
  TD-21-10 in the issue-21 requirements packet
  (`.agent-runs/stage2/issue-21/packet.md`, refresh 2, pinned to main `96c1842`),
  including TD-21-7 (keep the 0.15.x baseline handling); recorded in the first #21
  implementation PR.
- Scope: issue #21 and #70. TD-21-5 (schema evolution) is cited as design input by the
  #16, #17 and #18 packets; it is not a global rule.
- Decision: the packet's TD-21-1 to TD-21-10 as refreshed at `96c1842`, in summary:
  - TD-21-1 one version source, static `project.version`; runtime via
    `importlib.metadata`; scripts, image files, examples and tests derive it.
  - TD-21-2 release versions `MAJOR.MINOR.PATCH` (optional `rcN`); PEP 440 string, OCI
    tag, registry version and git tag `v<version>` identical apart from the `v`.
  - TD-21-3 non-release builds `<base>+g<12hex>[.dirty]`, image tag with `+` mapped to
    `-`, staged by `stage_release.py --non-release` from `git archive`; immutability
    kept; no tracked-file edit.
  - TD-21-4 contract evolution rules within `0.x` and a retained 0.1.0 `tools/list`
    snapshot test that reuses `tests/tool_contract.py` (no second tool list), with a
    migration-note allowlist.
  - TD-21-5 integer schema versions; readers reject higher/unknown versions naming
    them; migrations in memory; config and snapshot files never rewritten by the server.
  - TD-21-6 firmware classifier `src/wled_mcp/compat.py` (floor 16.0.0; tested
    {16.0.1}; expected empty) surfaced additively in
    `wled_get_state.data.diagnostics.firmware_support`; warning only, never a refusal.
  - TD-21-7 keep the 0.15.x baseline handling; reword "pinned v0.15.1" wording; move
    default fixtures to 16.x and keep explicit 0.15.1 cases.
  - TD-21-8 native arm64 CI (`ubuntu-24.04-arm`) for checks and a container job per
    architecture, no QEMU as native evidence; fallback only on runner unavailability;
    container jobs on `pull_request` and `push` to `main`.
  - TD-21-9 retained 0.1.0 fixtures from `0da1249` with automated upgrade/rollback
    compatibility tests; no live deployed run (ISSUE-21-DEC-001).
  - TD-21-10 documentation in `docs/contract/versioning.md`,
    `docs/contract/compatibility.md` and `docs/validation/issue-21.md`; README support
    table keeping the DEC-013 phrases; no version bump.
  - R21-COVERAGE: no WLED-COVERAGE row changes status or figures.
- Applicability / conditions / expiry: applies while #21 is open; a deviation found
  during implementation goes back to the coordinator with its rationale. Not an owner
  decision; the owner can override any part.
- Rationale supplied: packet analysis (agent), accepted by the coordinator.
- Affected requirement IDs, files, issues and tests: S2-COMPAT-01 to -03, S2-T06,
  S2-T07 (version consistency); #70 acceptance; issues #16, #17, #18, #20, #22, #25;
  tests `tests/test_version_source.py` and the later compatibility tests.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-21 packet (refresh 2); #16/#17/#18
  packets cite TD-21-5.
- Revalidation needed / next action: none before implementation.
