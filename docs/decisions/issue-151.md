# Issue #151 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

## ISSUE-151-DEC-001 — Build the MCPB bundle with every release, untested and without warranty

- ID: ISSUE-151-DEC-001
- Recorded date: 2026-11-12
- Status: active for issue #151 only.
- Authority: human decision (owner chat answers in the main coordinator session; recorded by
  the coordinator).
- Source: owner messages in the main session on 2026-11-12 (no permalink): "also eigentlich
  müsste das ding mit erstellt werden, wenn wir ein release für pypi erstellen" (English:
  "actually that thing should be built along when we create a release for PyPI"); "a, aber in
  der readme vermerken das wir das nicht testen werden und einfach mitbauen ohne gewähr"
  (English: "a, but note in the README that we will not test it and simply build it along
  without warranty"), answering the coordinator's choice between (a) a separate job that
  attaches the bundle to the GitHub release automatically after the PyPI upload and (b) a
  workflow artifact only; "Ja, Workflow für #151 starten" (English: "yes, start the workflow
  for #151").
- Scope: the MCPB bundle of #151 (requirement DIST-04) only.
- Decision:
  1. The bundle is built as part of the release workflow from the tagged version and attached,
     with its SHA-256, to the GitHub release by a separate job that runs only after the PyPI
     upload succeeded (option (a)); only that job gets `contents: write`.
  2. The project does not test the bundle. No Claude Desktop install run is required; the
     README, `docs/MARKETPLACE.md` and `docs/PUBLISHING.md` state that it is built along with
     each release, is not tested by the project and comes without warranty.
  3. Publishing or submitting the bundle to any directory stays an owner action (DEC-023).
- Applicability / conditions / expiry: bounded to #151. The owner still publishes the GitHub
  release and approves the PyPI upload; this decision authorizes no tag, release, upload,
  submission or repository setting. The release-time job is first executed with the next
  release the owner publishes.
- Rationale supplied: a bundle that is built along with the release cannot drift from it;
  the owner does not want to test it.
- Affected requirement IDs, files, issues and tests: DIST-04; `.github/workflows/publish.yml`,
  the bundle manifest and pack script, README.md, docs/MARKETPLACE.md, docs/PUBLISHING.md;
  issue #151 (body rewritten 2026-11-12); related #181 (review of `publish.yml`).
- Supersedes / superseded by: supersedes, for #151 only, the acceptance item "one manual
  Claude Desktop run" and the stand-alone manual pack step of the earlier issue text.
- Propagated to roles / packet references: requirements, implementer and reviewer through the
  #151 work packet.
- Revalidation needed / next action: the #151 work packet and PR; full-depth review because
  the change adds a write permission to the release workflow.
