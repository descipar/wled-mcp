# Issue #181: bounded source security review

One pass over five selected areas on 2026-11-13, from `origin/main` commit
`bab46c94b0049c9c07387217677be16fe3bf424f`. Not an exhaustive audit, penetration test, dependency
incident investigation or security guarantee. Scope was bounded under DEC-028 (packet
SEC181-01 to -09); no hardware or operational acceptance was added. Severity is a qualitative
estimate under the trusted-network/operator-owned-files threat model, not a CVSS score.

## Findings and decisions

| Area | Finding | Severity | Decision |
| --- | --- | --- | --- |
| HTTP endpoint (`http_config.py`, `http_service.py`, `server.py`) | Token required even on loopback, constant-time SHA-256 credential comparison, exact Host/Origin allowlists before body/tool execution, loopback default, forwarded headers off. The SDK's legacy protocol-validation errors could quote raw input. | Low: the SDK reflected the caller's own input to the same authenticated caller | Fix the adapter error boundary: bounded error-body parsing, fixed transport error text, no SDK error data; preserve HTTP status, JSON-RPC code/ID and fixed server errors. Sentinel tests cover both protocol paths. Hub authorization is separate; direct-access limits documented. |
| Inputs and outbound requests (`config.py`, `client.py`, `discovery.py`, models, parsers) | Credential-free HTTP(S) root URLs, fixed enum endpoints, no redirects or environment proxy, TLS verification on, bounded deadlines/bytes/JSON nodes/depth, strict typed arguments; CLI mDNS has datagram/record/name/candidate/deadline caps and never probes or enrolls. | Informational: configuration/DNS stays trusted | Keep the limits; document that URL validation is not an outbound firewall. M8 enrollment, unicast probing and range-write tools were **not implemented** at this baseline; the RFC 1918/DISC-05 caps were future requirements. No discovery or LAN probe ran. |
| Discovery interface exposure | CodeQL [alert #1](https://github.com/descipar/wled-mcp/security/code-scanning/1) (`py/bind-socket-all-network-interfaces`, `discovery.py:517`): explicit CLI mDNS binds an ephemeral UDP reply socket to all IPv4 interfaces and accepts untrusted packets during the 0.5 to 10 s window; caps apply, the socket closes in `finally`, nothing is probed or written. | Medium: genuine residual exposure | Alert kept open and trusted-network use documented; [#222](https://github.com/descipar/wled-mcp/issues/222) (Backlog) defines cross-platform interface selection (loopback would break discovery). No suppression, dismissal or workflow exclusion. This is an agent technical assessment, not human risk acceptance. |
| Files (`backups.py`, `scene_store.py`, `formats.py`, `bundles.py`, `groups.py`, `scenes.py`, `zones.py`) | Fixed ID-derived paths, bounded reads, strict imports, exclusive temp files, atomic promotion, 0600/0700 on POSIX. Snapshot root symlinks were followed (leaf links rejected; a #8 contract default, not an owner decision); definition counting continued past its directory cap and could use an incomplete count. | Low: local filesystem redirection (needs prior write access to the data directory); Low: local capacity limit | Fix snapshot root checks before read/create (migration note in CHANGELOG.md, TOOL-CONTRACT.md updated) and refuse new definitions when a capped count cannot prove capacity; regressions cover both. Parent-path replacement races need platform-aware storage work: [#220](https://github.com/descipar/wled-mcp/issues/220) (Backlog); keep storage operator-owned and private meanwhile. |
| Secrets and diagnostics (`diagnostics.py`, `cli.py`, `server.py`, store/parser errors) | stdout belongs to MCP; exceptions reduced to fixed classes; read models omit address/MAC. HTTP startup printed the bind address, Uvicorn logged raw bind exceptions, unknown keys in definition/bundle errors were echoed. | Low: diagnostic disclosure | Value-free startup notice on stderr, Uvicorn warning/error text and traceback filtered during startup (severity and bounded errno kept), unknown keys redacted (nested bundle keys, catalog keys, shared group/scene/zone helpers). Names, IDs, presets, candidates and JSON-RPC IDs are product content, not scrubbed; users must not embed secrets in them. |
| Release/CI (`ci.yml`, `publish.yml`, `deploy/build_mcpb.py`) | CI action tags were movable and checkout credentials persisted. Publication already had SHA pins, no persisted token, read-only build jobs, OIDC only in the `pypi` environment job, contents-write only in the dependent asset job. | Low: avoidable CI supply-chain exposure; residual build trust | Pin CI actions and disable persisted checkout credentials. Builds reach the internet on hosted runners with no publish/OIDC/write token (not a network sandbox). Read-only API inspection confirmed `pypi` required-reviewer protection (self-review prevention off); a live setting observation, not a YAML guarantee. No settings changed, no release job ran. |

Each follow-up (#220, #222) has exactly one milestone (Backlog) and no stage prefix/label. No exploit
details or installation data included; no advisories, disclosure or announcements were made (the
owner decides). DEC-013 is unchanged: no security support, private channel or response commitment.

## Automated analysis and dependency handling

- Ruff S rules: an independent `security-lint` CI job scans `src` on every PR/main run with
  `--select S --ignore S101`; narrow documented source-site exceptions, no broad baseline.
- CodeQL: separate SHA-pinned workflow, Python `security-extended`, PRs, main and weekly,
  `build-mode: none`; only this job has `security-events: write`. Neither tool proves absence of
  defects.
- Dependabot: monthly grouped `uv` and `github-actions` updates with bounded open PRs; no
  auto-merge, no alert triage promise, no repository setting changed, no scheduled run forced.
- Workflow regression tests enforce immutable action refs, discarded checkout credentials, no
  privileged PR trigger, least permissions, always-on security lint, no CodeQL build execution and
  update coverage.

## Validation

Mock transports, pure parsers, temporary files and synthetic loopback only; no LAN controller was
contacted. Focused correction run: 309 tests passed (HTTP service/CLI, scene store, backups,
bundles, groups, `tests/test_security_ci.py`).

| Command | Actual result |
| --- | --- |
| `uv run --frozen pytest -n auto` | 3544 passed, 45 skipped (macOS, Python 3.13.2) |
| CI Ruff check/format; `ruff check src --select S --ignore S101`; strict mypy (59 files) | PASS |
| agent setup, lock, private identifiers (no denylist configured), `git diff --check` | PASS |
| `scripts/check_distribution.py` | PASS (29 runtime versions verified) |

Independent review found a raw Uvicorn bind-error diagnostic after the first candidate; correction
round 1 added a startup-scoped log filter removed in `finally`, with a mocked `create_server`
regression. The first focused run also exposed a protocol-parity regression in an overly broad
error-body replacement, fixed by preserving safe JSON-RPC errors. No acceptance was weakened.

CodeQL completed on GitHub with **one open medium finding**, alert #1 (a green workflow does not
mean zero findings); it was filed as #222, not dismissed or excluded. The documentation correction
passed the document-relevant tests (771 passed, 1 opt-in Docker skipped), Ruff and the S scan;
runtime code is unchanged. No local CodeQL CLI run. Not run locally: Dependabot's scheduled run,
real release/PyPI/MCPB attachment, container builds, hardware, hub and LAN tests. See
[SECURITY.md](../../SECURITY.md#practical-limits) for user-facing residual risks.
