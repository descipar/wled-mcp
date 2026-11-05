# Issue #14 decisions

Recorded 2026-11-05. Read with [DECISIONS.md](../DECISIONS.md). Only ISSUE-14-DEC-001
carries human authority. ISSUE-14-DEC-002 to -005 are agent technical designs that
refine the documented contract; none is a human-confirmed decision and a human may
veto any of them at review.

## ISSUE-14-DEC-001 — Scoped implementation authority

- Status: active for the #14 candidate; merge approval remains separate.
- Authority/source: actual human request to implement #14 with the defined workflow
  (DEC-001) in the project conversation on 2026-11-05; no chat permalink available.
- Scope: implementation, tests, documentation, independent review and a reviewable
  PR. No merge, deployment, physical-device or LAN action, publication, license
  selection or image/registry release.
- Supersession: none. Ends ISSUE-3-DEC-003's staging "HTTP fails before listening
  until #14" for this candidate only.
- Propagation: coordinator supplied scope and DEC-001-003/005-007 to the implementer.

## ISSUE-14-DEC-002 — Access pipeline

- Status: active agent technical design, pending review/human merge.
- Authority/source: agent design checked against SDK 2.3.0, starlette 1.10.0 and
  uvicorn 0.54.0 behavior observed with loopback spikes; contract text
  [TOOL-CONTRACT.md](../TOOL-CONTRACT.md#transport-access-and-lifecycle).
- Scope: Streamable HTTP request admission.
- Decision: an own pure-ASGI guard is the outermost layer and answers, from headers
  only, in this order: Host (exact allowlist, one header) 403; Origin (exact
  allowlist when present, also without credentials) 403; bearer credential 401 with
  `WWW-Authenticate: Bearer` and a fixed body; path other than `/mcp` 404; method
  other than POST 405 `Allow: POST`; then the SDK stateless JSON app with a 256 KiB
  body limit. The SDK's own Host/Origin validation stays configured with the same
  lists as defense in depth, but the guard owns the status codes (the SDK would
  answer 421 for Host). `X-Forwarded-*`/`Forwarded` are never trusted. The guard logs
  one fixed-class line per rejection and never header values.
- Rationale: the SDK checks run after any auth and would let a stateless GET open an
  SSE stream, contradicting the contract's "no server-initiated streams".
- Affected: MCP-03, T18/T20; `http_service.py`, TOOL-CONTRACT wording.
- Supersedes: none.

## ISSUE-14-DEC-003 — Credential and configuration rules

- Status: active agent technical design, pending review/human merge.
- Scope: HTTP startup configuration only; stdio is unaffected.
- Decision: exactly one bearer source (`WLED_MCP_HTTP_TOKEN` or `--http-token-file`);
  32 to 512 printable ASCII characters, no whitespace; a file is absolute, regular,
  at most 1 KiB, read once at startup (rotation is a restart), one trailing newline
  stripped. Comparison is constant-time over SHA-256 digests. Authorization must be a
  single header, `Bearer` scheme (case-insensitive) and one space. No lockout or rate
  limiting in v1. Path fixed at `/mcp`; no host/port environment variables. Defaults
  127.0.0.1:8000 with allowed hosts `127.0.0.1:8000` and `localhost:8000`; any other
  host or port needs an explicit `--allowed-host`, which replaces the defaults.
  Allowlist grammar: exact `host[:port]` (IPv6 bracketed) and `scheme://host[:port]`,
  no wildcard/path/userinfo, case-insensitive, at most 16 entries of 255 characters.
  HTTP-only options together with stdio, option abbreviations and a token CLI value
  fail with exit 2 and a fixed message.
- Rationale: fail closed; a silently ignored security option or a leaked length is a
  trap. Affected: MCP-03, OPS-03, T20; `http_config.py`, `cli.py`.
- Supersedes: none.

## ISSUE-14-DEC-004 — Lifecycle

- Status: active agent technical design, pending review/human merge.
- Scope: HTTP process lifecycle and disconnect handling.
- Decision: stateless JSON, one worker, no sessions/event store/server streams; a
  stale `Mcp-Session-Id` is ignored and DELETE is 405. One process-owned resource
  graph, closed once after the listener drained. The service owns SIGINT/SIGTERM
  (SIGBREAK on Windows) and neutralizes uvicorn's re-raise of the captured signal, so
  a graceful stop exits 0; a second SIGINT forces exit and leaves interrupted writes
  uncertain. Graceful drain timeout is the configured operation timeout rounded up
  plus 2 s (maximum 122 s). No unauthenticated health route; liveness is a TCP
  connect or an authenticated `ping`/`tools/list` POST. Observed: uvicorn and SDK
  2.3.0 keep a dispatched handler running when the client disconnects on both the
  legacy and the 2026-07-28 request paths, so no extra shield was added.
- Deviation from the packet: resources close after `serve()` returns instead of in
  the ASGI lifespan, because signal ownership removed the re-raise problem.
- Rationale: MCP-04 and the contract. Affected: MCP-04, REL-02, OPS-05, T21.
- Supersedes: none.

## ISSUE-14-DEC-005 — Evidence scope

- Status: active; limits what this candidate may claim.
- Authority/source: ISSUE-4-DEC-005 (actual HTTP T19 belongs to #14).
- Decision: the HTTP evidence is mock and loopback software evidence for T18-T21.
  It is not deployment, hub integration, resource measurement or hardware evidence
  (#10/#11, H02/H03). Resource measurements stay pending. Session expiry is vacuous by
  design and is evidenced by the stale-ID and no-session tests. Windows signal
  delivery is not exercised by the subprocess tests (documented skip).
- Supersedes: none.
