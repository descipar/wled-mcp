# Issue #181: bounded source security review

One pass over five selected areas on 2026-11-13, starting from `origin/main` commit
`bab46c94b0049c9c07387217677be16fe3bf424f`. This is not an exhaustive audit, penetration
test, dependency incident investigation or security guarantee. Scope/evidence were
bounded before implementation under DEC-028 (packet SEC181-01–09); no additional
hardware or operational acceptance was introduced. Severity is a qualitative estimate
under the trusted-network/operator-owned-files threat model, not a CVSS score.

## Findings and decisions

| Area | Finding and inspected code | Severity | Decision |
| --- | --- | --- | --- |
| HTTP endpoint | `http_config.py`, `http_service.py`, `server.py`: token required even on loopback; SHA-256 constant-time credential comparison; exact single Host and optional Origin allowlists checked before body/tool execution; default loopback bind; forwarded headers disabled. The SDK's legacy protocol-validation errors could quote raw input. | Medium: authenticated input disclosure in error responses | Fix the adapter error boundary: bounded error-body parsing, fixed transport error text, no SDK error data. Preserve HTTP status, JSON-RPC code/ID and allowlisted fixed server errors, including generated correlation IDs; successful responses stay unchanged. Existing access/parity tests plus new malformed-protocol sentinel tests cover both HTTP protocol paths. Hub authorization is separate; document direct-access limits. |
| Inputs and outbound requests | `config.py`, `client.py`, `discovery.py`, request models and bundle parsers: configured credential-free HTTP(S) root URLs, fixed enum endpoints, no redirects or environment proxy use, TLS verification on; deadlines and bounded request/response bytes, JSON nodes/depth and strict typed operation arguments. Non-default ports and operator-configured DNS/addresses are allowed intentionally. CLI mDNS has datagram/record/name/candidate/deadline caps and never probes/enrolls candidates. | Informational: configuration/DNS remains trusted | Keep those limits, document that URL validation is not an outbound firewall. M8 enrollment, unicast probing and range-write tools are **not implemented** at this baseline; RFC1918/DISC-05 caps in `contract/discovery.md` are future implementation requirements, not tested runtime safeguards. No discovery or LAN probe ran. |
| Inputs and outbound requests: discovery interface exposure | CodeQL [alert #1](https://github.com/descipar/wled-mcp/security/code-scanning/1), `py/bind-socket-all-network-interfaces`, identifies `discovery.py:517`: explicit CLI mDNS discovery binds an ephemeral UDP reply socket to all IPv4 interfaces. It accepts untrusted packets from any IPv4 source using port 5353 during a requested 0.5–10 second window. Existing parsing/deadline caps apply, the socket closes in `finally`, and no candidates are probed/enrolled/written. | Medium: genuine residual exposure, not a false positive | Independent reviewer technical assessment: retain the alert open and document trusted-network use; [#222](https://github.com/descipar/wled-mcp/issues/222), Backlog, defines cross-platform interface selection before changing the binding. Blindly switching to loopback would break discovery. No CodeQL suppression, dismissal or workflow exclusion was added. This is an agent technical assessment, not a claim of human risk acceptance. |
| Files | `backups.py`, `scene_store.py`, `formats.py`, `bundles.py`, `groups.py`, `scenes.py`, `zones.py`, their tool adapters: fixed ID-derived paths, bounded reads/strict imports and item limits, exclusive temporary files and atomic promotion; files 0600/directories 0700 when created on POSIX. Snapshot root symlinks were followed although leaf links were rejected. Definition counting continued traversing beyond its stated directory cap and could use an incomplete count. | Medium: local filesystem redirection; Low: local resource/capacity limit | Fix snapshot root checks before read/create and refuse new definitions when a capped count cannot prove capacity. Regressions cover no outside creation/read, bounded iterator consumption and no-write refusal. Parent-path replacement races need broader platform-aware storage work: [#220](https://github.com/descipar/wled-mcp/issues/220), Backlog, medium risk with an untrusted concurrent local writer. Keep storage operator-owned/private meanwhile. |
| Secrets and diagnostics | `diagnostics.py`, `cli.py`, `server.py`, read models and store/parser errors: stdio stdout belongs to MCP, exceptions are normally reduced to fixed classes, tool validation avoids raw Pydantic errors, read models omit address/MAC fields. HTTP startup printed the bind address, and Uvicorn logged raw bind exceptions before exiting; unknown keys in untrusted definition/bundle errors were echoed. | Low: diagnostic content disclosure | Fix startup to a value-free stderr notice, filter Uvicorn warning/error text and traceback fields during startup (retain severity and bounded numeric OS errno), and redact unknown keys (including nested bundle keys/catalog keys and shared group/scene/zone helpers). Sentinel regressions plus existing stdout/error/log tests. Intentional product content (names, IDs, presets, discovery candidates and JSON-RPC IDs) is not a diagnostic scrubber; document that users must not embed secrets in it. |
| Release/CI pipeline | `.github/workflows/ci.yml`, `publish.yml`, `deploy/build_mcpb.py`: CI action tags were movable and checkout credentials persisted. Publication already has SHA pins, no persisted checkout token, read-only separate distribution/MCPB build jobs, OIDC only in the `pypi` environment job, and contents-write only in the dependent asset job with no checkout/install. MCPB attachment waits for PyPI and bundle success, verifies checksums and refuses different existing assets. | Low: avoidable CI supply-chain exposure; residual build trust | Pin CI actions and disable persisted checkout credentials. Builds can install public dependencies and reach the internet on hosted runners; they receive no publish/OIDC/write token, but are not network sandboxes. Existing release boundaries retained. Read-only API inspection confirmed `pypi` required-reviewer protection exists (self-review prevention is off); this is a live setting observation, not a guarantee supplied by YAML. No settings changed and no release job ran. |

The larger storage finding is represented by #220; CodeQL's discovery-interface finding
is tracked by #222. Routine operational limits are documented rather than redesigned.
Each follow-up has exactly one milestone, Backlog, and no stage prefix/label. No exploit
details or installation data were included. No advisories, disclosure, publication or announcements were performed;
the owner decides any disclosure. DEC-013 remains unchanged: no security support,
private channel, advisory process, guaranteed fix or response commitment.

## Automated analysis and dependency handling

- **Ruff S rules:** use the already locked Ruff, avoiding another tool dependency.
  An independent `security-lint` CI job scans `src` on every PR/main run, including
  documentation-only changes. It uses `--select S --ignore S101`: assertions serve
  type narrowing/internal invariants, never replace required input/access checks.
  Narrow source-site exceptions explain the mDNS reply socket, metadata marker,
  credential environment-variable name and diagnostics observer isolation. No broad
  finding baseline or severity suppression is used.
- **CodeQL:** a separate SHA-pinned workflow runs Python `security-extended` analysis
  on PRs, main and weekly. `build-mode: none` needs no project/dependency execution;
  only this analysis job has `security-events: write`. It has no publishing credentials.
  CodeQL complements syntax-level lint with data-flow queries; neither proves absence
  of defects. No docs-only skip applies.
- **Dependabot:** weekly `uv` and `github-actions` updates are configured with bounded
  open PRs. `uv` covers the manifest and lock together; Actions covers immutable pins.
  This is update handling, not auto-merge, deployment or a promise to triage alerts.
  No repository alert/security-support setting was changed. Configuration becomes
  active through the default branch; no scheduled update run was forced.
- Workflow regressions enforce immutable action refs, discarded checkout credentials,
  no privileged PR trigger, least permissions, always-on security lint, no CodeQL build
  execution, and lock/action update coverage.

Primary configuration references checked during implementation:
[CodeQL workflow options](https://docs.github.com/en/code-security/reference/code-scanning/workflow-configuration-options),
[Dependabot ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories).

## Validation

Mock transports, pure parsers, temporary files and synthetic loopback servers only.
No test contacted a LAN controller. The focused correction run passed **309 tests**:

```text
uv run --frozen pytest -q tests/test_http_service.py tests/test_http_cli.py tests/test_scene_store.py tests/test_backups.py tests/test_bundles.py tests/test_groups.py tests/test_security_ci.py
```

Final local validation passed:

| Command | Actual result |
| --- | --- |
| `uv run --frozen pytest -n auto` | 3544 passed, 45 skipped (macOS, Python 3.13.2); platform/GNU-tool/container-dependent skips remain visible in pytest output. |
| CI Ruff check and format commands from `ci.yml` | PASS; 144 files formatted. |
| `uv run --frozen ruff check src --select S --ignore S101` | PASS. |
| `uv run --frozen mypy` | PASS; 59 source files. |
| `uv run --frozen python scripts/check_agent_setup.py` | PASS. |
| `uv run --frozen python scripts/check_lock.py` | PASS. |
| `uv run --frozen python scripts/check_private_identifiers.py` | PASS; rule checks only, no private denylist configured. |
| `uv run --frozen python scripts/check_distribution.py` | PASS; wheel/clean-install/setup/stdio/read-only profile/HTTP restart/uvx/hub-example checks; 29 runtime versions verified. |
| `git diff --check` | PASS. |

Independent review found the raw Uvicorn bind-error diagnostic after the initial candidate.
Correction round 1 adds a source-logger filter scoped to startup, removed in `finally`;
the mocked `create_server` regression proves refusal without opening a socket, value-free
stderr, retained OS errno and filter cleanup. The normal access/protocol paths are unchanged.

The existing scene tests still require known unsupported field names: a fixed allowlist
preserves those useful diagnostics while redacting arbitrary key content. The README
stays within its existing 200-line budget. The first focused run exposed a protocol-parity regression
in an overly broad error-body replacement; the final implementation preserves safe
JSON-RPC errors and the existing parity test now passes. No acceptance was weakened.

CodeQL completed on GitHub and reported **one open medium finding**, alert #1 above.
A green analysis workflow means analysis completed; it does not establish zero findings.
The documentation/follow-up correction passed the document-relevant tests (771 passed,
1 opt-in Docker test skipped), Ruff check/format and the Ruff S scan; runtime code is
unchanged, so the full-suite result above remains applicable.
The finding was reviewed as a genuine residual risk and filed in Backlog as #222; it was
not dismissed, hidden or excluded. No local CodeQL CLI analysis was run. Exact candidate
CI execution results are reported in the PR separately from this finding assessment.
Dependabot's scheduled run, real release/PyPI/MCPB attachment, container builds, hardware, hub and
LAN tests were not run locally for this change. Existing release tests inspect artifacts
and guards without publishing. See [SECURITY.md](../../SECURITY.md#practical-limits)
for user-facing residual risks.
