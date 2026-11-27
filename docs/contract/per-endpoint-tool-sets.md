# Per-endpoint tool sets over HTTP (design note, #237)

**Status: proposed design for [#237](https://github.com/descipar/wled-mcp/issues/237), not
implemented; no behavior changes.** The recommendation is a proposal
([ISSUE-237-DEC-001](../decisions/m7-m8.md#issue-237-decisions), status PROPOSED) until the owner
accepts, changes or rejects it. Names, paths and tokens below are synthetic.

## Problem and non-goals

Tool groups and profiles ([profiles.md](profiles.md), #236, ISSUE-236-DEC-001) select one tool set
per process. Several callers of one HTTP service (for example a voice assistant, a coding agent and
an administration session) may need different sets, with a real boundary and without several
writing processes. The issue asks four questions: how to map a set to an endpoint and
authenticate it (Q1), which alternatives exist and what they cost (Q2), how status, redaction and
guidance behave per path (Q3), and what to recommend (Q4).

Non-goals: tenancy (same devices, inventory, stores, Host/Origin allowlists), runtime reload,
per-tool selection, per-credential scopes on one path, any change to stdio, any code in this
change. This note does not change
[diagnostics.md](diagnostics.md#credential-rotation-and-tenancy); its statement that groups which
must not share reach need two services stays true, because endpoints share devices and stores.

## Design (Q1)

Code references are to the merged `main` at 9ca1bcd.

### Configuration

- The process policy (`--profile`, `[access]`, `--tool-groups`) stays the ceiling and defines the
  default path `/mcp` exactly as today (`http_config.ENDPOINT_PATH`, `AccessPolicy` in
  `access.py`).
- Optional named endpoints, in the configuration file only (restart to apply, as for profiles; no
  environment variable and no option for secrets):

  ```toml
  [[http.endpoints]]
  name = "voice"                       # [a-z0-9-], 1..32, unique
  profile = "control"                  # optional, inherits the process value
  tool_groups = ["presets"]            # optional, inherits the process value; core is always on
  token_file = "/run/secrets/voice"    # absolute path, never an inline secret
  ```

- The path is derived as `/mcp/<name>` (exact match, no trailing slash; `/mcp` is reserved for the
  default endpoint; at most 8 endpoints). Absent keys inherit the process value.

### Never widen

- Effective endpoint policy is the intersection with the process policy: endpoint profile classes
  within the process profile classes, endpoint groups within the process groups. An endpoint
  profile above the process profile is a startup error (exit 2, message names the position, never
  a value) rather than a silent clamp, so a misconfiguration is visible. The same holds for a group
  outside the process groups.
- Device ceilings (`caps`, `max_class`) stay process-wide; G2 applies the lower of the endpoint
  profile and the cap.
- Each endpoint gets its own registry: `create_server(operations, AccessPolicy(profile=effective,
  caps=same, groups=effective), resources.monitor)` per endpoint, over the same `Resources` and
  `ServiceMonitor` (today `cli.serve_http` builds one `Resources` and one server). Device locks
  (`Resources.locks`, process-local `anyio.Lock`), catalog cache and stores are therefore shared,
  which is the main advantage over several instances.
- A tool absent from an endpoint's registry fails exactly like an unknown name
  (`server.py`: `registry.get(...)` is `None`, `MCPError -32602 "Unknown tool"`) before any I/O.
  Dispatch must use the endpoint's own server object, so the registry cannot be reached from another
  path.
- G3 (`CURRENT_TOOL_CLASS` and the write engines) keeps the process-wide policy, which is equal to
  or wider than any endpoint and so never the weaker layer. Contract limit G1 (the registration
  filter is process-wide) becomes endpoint-wide on HTTP; that is a new contract surface.

### Authentication

- Host and Origin allowlists stay process-wide on the one listener and are checked first,
  unchanged. Per-endpoint overrides are rejected: same authority and listener, more surface.
- Every endpoint has its own bearer credential; the default path keeps `WLED_MCP_HTTP_TOKEN` or
  `--http-token-file`. A credential is valid only on its own path. Credentials must be pairwise
  different (equal digests are a startup error that never echoes a value). A token shared across
  paths would be convenience, not a boundary, because its holder could call the widest path; it is
  not offered. A narrow credential never opens `/mcp`.
- Guard order stays Host, Origin, bearer, path, method (`http_service.AccessGuard._check`, which
  today compares one `HTTPServiceSettings.token_digest`). A credential counts as authenticated
  only on its own path. Rule when at least one endpoint is configured (with none, today's
  behavior is kept byte-identical):
  - Under the `/mcp` prefix (`/mcp` and `/mcp/...`): a request is accepted only if the presented
    credential's digest equals the digest of the endpoint whose path it is (constant-time
    `hmac.compare_digest`, as `_bearer_ok`). Every other case gets the same 401 with the same body
    and headers as a wrong or missing credential: another endpoint's valid credential, the
    default credential on `/mcp/<x>`, a narrow credential on `/mcp`, and any credential on a
    path that names no endpoint. Status code and body therefore reveal neither which endpoint
    names exist nor anything about wider paths. Today an authenticated request on a wrong path gets
    404; under the prefix that changes to 401 once endpoints exist, and the default credential on
    an unknown `/mcp/<x>` is 401 as well, to stay uniform.
  - Outside the `/mcp` prefix: unchanged. A missing or wrong credential gets 401; a credential that
    is valid for some endpoint gets 404. This reveals nothing about endpoint names, because
    these paths cannot match any endpoint.
  - Timing: the digest comparison does fixed work (compare against every endpoint digest without
    early exit); this is hardening, the contract rests on the uniform status code.
  - After a path match and valid credential, method handling is as today (405 for non-POST).
- Rotation stays restart-based, one credential per endpoint, independently.
- stdio is unchanged: one process, one caller. Per-client sets there are separate processes with
  `--profile` and `--tool-groups`.

### Implementation risks (unverified, need a spike)

- The SDK app for each server owns a session-manager lifespan (`http_service.py` builds the app with
  `stateless_http=True` and serves with `lifespan="on"`), so several sub-apps need composed
  lifespans. Not verified.
- Stateless JSON setup per endpoint; schema caches are per server (about 1 ms per model, expected
  negligible, not measured here).

## Alternatives with maintenance cost (Q2)

| Alternative | What it is | Cost and limits |
| --- | --- | --- |
| A. Several instances with #236 | One service per set, each with its own `--profile`/`--tool-groups`, port, Host allowlist, token | Zero code. N containers, ports, tokens, allowlists and hub entries updated in lockstep; each instance probes devices itself (more load on small controllers); evidence (`last_control`) and status counters are per process. [DEPLOYMENT.md](../DEPLOYMENT.md) forbids two independently writing instances because device locks are process-local, so only one writing instance plus read-only instances is within the rules. Two stdio hub entries are separate processes with the same limit. |
| B. Hub-side tool selection | The hub hides tools from its list | Depends on the hub; this repository documents no such hub feature (unverified for the deployed hub build). It hides names in the hub list but does not constrain the service: the service still serves everything on the shared token, direct access sees all, and a call to a hidden name is the hub's concern. The served instructions still name all tools, so guidance and the token saving are partial. Ownership is outside this repository. |
| C. Per-endpoint paths in one service (this design) | Section above | Shared locks, stores and one process and config. Cost: a new config table; per-endpoint credential and digest handling in the access guard (security-sensitive, full-depth review including a cross-path credential test matrix); a per-endpoint server graph; status, monitor and evidence changes; docs; parity tests. Relative effort: medium, concentrated in one guard change. |

## Status, redaction and guidance per path (Q3)

- Status: `wled_get_service_status` is in group `core`, so every path has it. It reports the
  endpoint's effective `access.profile` and `access.tool_groups` and per-device `effective_class`
  (lower of endpoint profile and cap), plus an additive field `access.endpoint` (name, `default`
  for `/mcp`) present only when at least one endpoint is configured, so a deployment without
  endpoints is byte-identical. It never discloses other endpoints' names, paths, credentials or
  policies, nor the wider process profile. Call counters (`ServiceMonitor.call_counts`, process-wide
  today) are reported per calling endpoint only, so a narrow caller does not see other callers'
  activity. Device observations (last observed outcome per device) stay shared; they are
  device-level facts.
- Evidence: `LastControlStore` entries carry the tool name (`operation`), which
  `wled_explain_lighting` returns (`explain.py: _last_control_observation`). With shared evidence an
  endpoint without the `layout` group could read `wled_replace_layout`, which conflicts with the
  intent of ISSUE-236-DEC-001 item 5 (that item covers served texts, not tool results). Recommended: keep the store shared (evidence about a device is useful
  whoever changed it) and, for a tool not in the reading endpoint's registry, return the class-level
  label ("another tool, class control") instead of the name. Open point.
- Redaction otherwise unchanged: credentials, Host/Origin values and URLs are never logged. The call
  log line gains the endpoint name (not a secret); the startup event lists endpoints with profile
  and tool groups; `config validate` and `doctor` report endpoint names, profile, groups and token
  file presence only (the path is not echoed, per [cli.md](cli.md)); `doctor --export` carries names
  only.
- Guidance: `guidance.build_instructions(registry)` already composes from the registered set, so each
  endpoint's server gets instructions for its own set. The static prompt `change_lighting_safely`
  names no tool and is identical everywhere.

## Recommendation and migration (Q4)

Recommendation (proposed): adopt C, the per-endpoint design. Implement the design as one follow-up issue in M9 or Backlog,
only after the owner accepts. Rationale: the main use case needs more than one writer, which several
instances cannot do within the documented rule, and a hub-side filter is no enforcement; the cost is
bounded (one config table, one guard change, per-endpoint server construction).

Alternative for the owner: defer, and document A (several instances) as the supported pattern, with the single-writer rule,
until a concrete need appears. Trade-off: no code and no new security surface,
but at most one writing instance, lockstep upkeep of N entries, and per-process evidence and status.

Not recommended: a shared token across paths, per-endpoint Host/Origin, runtime reload, per-tool
selection, per-credential scopes on one path.

Migration: with no endpoints configured behavior is byte-identical (same `/mcp`, token, `tools/list`,
instructions and status shape); the default path never changes. An older server rejects the new key as
an unsupported field (exit 2, fail-closed, as for access keys; see `config.py` and
[versioning.md](versioning.md#migration-notes)), so a downgrade needs the old configuration. Clients of
a new endpoint re-list tools after a restart, as for groups. A release note is needed (`0.x` minor,
additive key per DEC-020).

Cost reference: [profiles.md](profiles.md#token-cost) (core 8 tools 3168 tokens against about 17975
for all groups in `full`; core plus presets 7199 in `full`, 3965 in `control`); not re-measured here.

Follow-up implementation issues to propose after acceptance (not created here): (1) configuration,
guard, per-endpoint server and tests including cross-path credential cases (another endpoint's credential, the default credential on an unknown `/mcp/<x>`, a narrow credential on `/mcp`, any credential on an unknown path: all the same 401); (2) status, monitor and
evidence per endpoint, and docs.

## Open points for the owner and the spike

1. Adopt C, defer with A as the supported pattern, or reject.
2. Startup error versus clamp for an endpoint above the process ceiling (error proposed).
3. Evidence naming: class-level label for tools outside the reading endpoint (proposed) versus
   per-endpoint stores.
4. Maximum endpoint count (8 proposed) and name rules.
5. Spike: composed SDK lifespans, per-endpoint server construction cost, and the constant-time
   guard shape; none of these is verified yet.
6. Hub-side selection (B in Q2) was not verified for the deployed hub build.
