# Issue #21 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-21-DEC-001 — Update and rollback evidence

- ID: ISSUE-21-DEC-001
- Recorded date: 2026-11-07
- Status: active for issues #21 and #25.
- Authority/source: human decision, owner answer in the coordinator session, 2026-11-07, to the
  Phase-0 questions of the stage-2 plan (DEC-021): "alles nach empfehlung" (English: "everything
  as recommended"); no permalink.
- Scope: closure evidence for S2-COMPAT-03 (version-to-version update and rollback, HTTP and
  uvx/stdio).
- Decision: #21 closes on automated upgrade/rollback tests plus the documented procedure. The
  live update/rollback run on the deployed target is evidence for #25 (S2-LAUNCH-01), performed
  once with the published artifacts.
- Conditions: the live run needs its own operation authorization when #25 reaches it.

## ISSUE-21-DEC-002 — Technical defaults TD-21-1 to TD-21-10

- ID: ISSUE-21-DEC-002
- Recorded date: 2026-11-07
- Status: active for issue #21 (with #70, absorbed per DEC-021); technical proposal accepted by
  the coordinator (refresh 2 of the packet, main `96c1842`), not a human decision; the owner can
  override any part.
- Scope: #21 and #70. TD-21-5 is design input for #16, #17 and #18, not a global rule.
- Decision:
  - TD-21-1 one version source, static `project.version`; runtime via `importlib.metadata`;
    scripts, image files, examples and tests derive it.
  - TD-21-2 release versions `MAJOR.MINOR.PATCH` (optional `rcN`); PEP 440 string, OCI tag,
    registry version and git tag `v<version>` identical apart from the `v`.
  - TD-21-3 non-release builds `<base>+g<12hex>[.dirty]`, image tag `+` mapped to `-`, staged
    by `stage_release.py --non-release` from `git archive`; no tracked-file edit.
  - TD-21-4 contract evolution rules within `0.x`; retained 0.1.0 `tools/list` snapshot test
    reusing `tests/tool_contract.py`, with a migration-note allowlist.
  - TD-21-5 integer schema versions; readers reject higher/unknown versions naming them;
    migrations in memory; config and snapshot files never rewritten by the server.
  - TD-21-6 firmware classifier `src/wled_mcp/compat.py` (floor 16.0.0; tested {16.0.1};
    expected empty) in `wled_get_state.data.diagnostics.firmware_support`; warning only.
  - TD-21-7 keep the 0.15.x baseline handling; reword "pinned v0.15.1"; default fixtures 16.x.
  - TD-21-8 native arm64 CI (`ubuntu-24.04-arm`) for checks and a container job per
    architecture, no QEMU as native evidence; fallback only if the runner is unavailable.
  - TD-21-9 retained 0.1.0 fixtures from `0da1249` with automated upgrade/rollback tests; no
    live run (ISSUE-21-DEC-001).
  - TD-21-10 documentation in `docs/contract/versioning.md`, `docs/contract/compatibility.md`,
    `docs/validation/issue-21.md`; README support table keeps the DEC-013 phrases; no version
    bump. R21-COVERAGE: no WLED-COVERAGE row changes.
- Conditions: applies while #21 is open; deviations go back to the coordinator.
