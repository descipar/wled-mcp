# Issue #11 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-11-DEC-001 — Scoped implementation authority for #11

- ID: ISSUE-11-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #11 only.
- Authority: human decision.
- Source: human request in the project conversation on 2026-11-06 to start #11
  following the defined workflow (DEC-001); no permalink available.
- Scope: issue #11 implementation work on its feature branch: deployment artifacts
  (Dockerfile, Compose and hub examples, staging helper), documentation, routine
  device-free tests, independent review and a reviewable pull request.
- Decision: implement #11 under the defined workflow. Explicitly excluded: merge,
  deployment to any hub or home server, starting a container on a hub, hub entry
  registration, LAN or device contact, physical writes, image/registry/package
  publication, license selection and router forwarding.
- Applicability / conditions / expiry: bounded to the #11 candidate and its review
  cycle. Local developer-machine checks (image build pulling a public base image,
  `docker compose config`, loopback container run) are allowed and must be labeled
  "local developer machine, not target". Live checks H02/H03 and any deployment need a
  separate human instruction naming the mode(s) and target.
- Rationale supplied: none beyond the request.
- Affected requirement IDs, files, issues and tests: OPS-01–05, MCP-01–04, TEST-01;
  #11; packet `.agent-runs/issue-11/packet.md`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements packet "Authorized scope";
  implementer and reviewer through the coordinator.
- Revalidation needed / next action: none for the candidate; the human merge decision
  remains separate.

## ISSUE-11-DEC-002 — Technical deployment defaults TD-1 to TD-9

- ID: ISSUE-11-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #11 only.
- Authority: technical proposal by the requirements agent, accepted by the coordinator
  within ISSUE-11-DEC-001. This is not a human decision; the human did not choose these
  defaults and may veto them at review.
- Source: requirements packet `.agent-runs/issue-11/packet.md`, section "Technical
  defaults", 2026-11-06, no permalink.
- Scope: issue #11 deployment artifacts and documentation.
- Decision:
  - TD-1 Both modes consume a pre-staged versioned directory
    `/app/binaries/wled-mcp/<version>/` (wheel, `requirements-runtime.txt`,
    `SHA256SUMS`). Private Git pinned to a full commit is documented only as an
    alternative; an offline wheelhouse is optional.
  - TD-2 HTTP base image: official `python:3.13.<patch>-slim-<debian>` with an exact
    patch tag (and digest) in the Dockerfile.
  - TD-3 Image built locally on the target from the staged artifacts, local tag
    `wled-mcp:<version>`, no push; pip install of the wheel with `--constraint`;
    fixed non-root UID 10001 (adjustable); exec-form `ENTRYPOINT ["wled-mcp"]`.
  - TD-4 Separate Compose project joining the hub network as `external`; no host port;
    `restart: unless-stopped`; `stop_grace_period` above the 122 s drain bound;
    read-only root filesystem with writable data mount and tmpfs `/tmp`; all
    capabilities dropped; `no-new-privileges`.
  - TD-5 Liveness: Compose healthcheck is a TCP connect to the service port with the
    image's Python; an authenticated `ping` is the documented stronger manual check.
  - TD-6 Credential: Compose `secrets:` from a git-ignored file mounted at
    `/run/secrets/wled_mcp_http_token`, read with `--http-token-file`.
  - TD-7 Stdio: the hub entry sets persistent `UV_CACHE_DIR`, `UV_TOOL_DIR` and
    `UV_PYTHON_INSTALL_DIR`; a runtime/ABI change requires an environment rebuild.
  - TD-8 Static YAML checks use a dev-only YAML parser; an optional
    `docker compose config` check is opt-in and never required in CI.
  - TD-9 Placement: `deploy/http/Dockerfile` with an allowlist
    `deploy/http/Dockerfile.dockerignore`, `examples/compose.http.example.yaml`, hub
    examples in `examples/`.
- Applicability / conditions / expiry: implementation-level refinements made by the
  implementer are recorded in the implementation handoff and DEPLOYMENT.md (uv paths in
  a tree separate from the server data directory; `--isolated` in the stdio entry;
  a staging helper `deploy/stage_release.py`). Actual network name, service name,
  credential storage, hub field schema and target architecture remain deployment-time
  facts to be confirmed when a deployment is requested.
- Rationale supplied: none by the human. Agent rationale: see the packet; pre-staged
  wheels avoid Git credentials on the target, slim Debian has glibc wheels for the
  compiled dependencies, and the separate Compose project keeps the hub untouched.
- Affected requirement IDs, files, issues and tests: OPS-01–05, MCP-01/03/04;
  `deploy/**`, `examples/*`, `docs/DEPLOYMENT.md`, `tests/test_deployment_artifacts.py`,
  `scripts/check_distribution.py`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: packet TD-1–TD-9; implementer handoff
  `.agent-runs/issue-11/implementation.md`; reviewer through the coordinator.
- Revalidation needed / next action: independent review; a human veto of any default
  (for example base image family or a separate Compose project) requires a refreshed
  packet and tests.
