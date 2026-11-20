# Issue #151 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

## ISSUE-151-DEC-001 — Build the MCPB bundle with every release, untested and without warranty

- ID: ISSUE-151-DEC-001
- Recorded date: 2026-11-12
- Status: active for issue #151 only.
- Authority/source: human decision, owner chat in the main session, 2026-11-12 (no permalink).
  Owner: "also eigentlich müsste das ding mit erstellt werden, wenn wir ein release für pypi
  erstellen" (English: "actually that thing should be built along when we create a release for
  PyPI"); "a, aber in der readme vermerken das wir das nicht testen werden und einfach mitbauen
  ohne gewähr" (English: "a, but note in the README that we will not test it and simply build it
  along without warranty").
- Scope: the MCPB bundle of #151 (DIST-04) only.
- Decision:
  1. The bundle is built in the release workflow from the tagged version and attached, with its
     SHA-256, to the GitHub release by a separate job that runs only after the PyPI upload
     succeeded; only that job gets `contents: write`.
  2. The project does not test the bundle (no Claude Desktop install run); README,
     `docs/MARKETPLACE.md` and `docs/PUBLISHING.md` state it is built along, untested, without
     warranty.
  3. Publishing or submitting the bundle to any directory stays an owner action (DEC-023).
- Conditions: authorizes no tag, release, upload, submission or setting; the job first runs with
  the next owner-published release. Full-depth review (adds a write permission to the workflow).
- Supersedes, for #151 only, the acceptance item "one manual Claude Desktop run" and the manual
  pack step of the earlier issue text.

## ISSUE-151-DEC-002 — Technical defaults for the bundle packet

- ID: ISSUE-151-DEC-002
- Recorded date: 2026-11-12
- Status: active for issue #151 only; technical proposal (requirements role, one coordinator
  adjustment), not an owner decision; the owner may overrule any item.
- Scope: bundle design, workflow shape and tests of #151.
- Decision:
  1. Manifest spec 0.3, `server.type` `python`, command `uvx` with the pinned
     `wled-mcp==<version>` launch; the `uv` type is not used. `user_config`: inventory path and
     data directory; HTTP off.
  2. A Python script in `deploy/` packs and validates against a vendored, byte-identical copy of
     the upstream schema; no Node `mcpb` tool in the workflow (one pinned cross-check is
     recorded in validation). DIST-04 is defined in `docs/contract/mcpb-bundle.md`.
  3. The manifest template uses the `REPLACE_WITH_VERSION` placeholder; version and author are
     injected at build time.
  4. Coordinator adjustment: the bundle is built in its own read-only job that does not gate the
     PyPI `publish` job; a bundle failure never changes the PyPI upload. The `release-asset` job
     needs both, has `contents: write` as its only elevated permission, uses SHA-pinned actions,
     never overwrites an existing asset and accepts an already attached identical one.
- Conditions: bounded to #151; no publication authorized. Item 4 replaces the packet's proposal
  that a bundle failure fails the shared `build` job.
