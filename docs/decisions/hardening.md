# Decisions: hardening and fixes (issues #48 to #98)

## Issue #48 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

### ISSUE-48-DEC-001 — Shared #6/#7 handling of firmware segment limits

- ID: ISSUE-48-DEC-001
- Status: active for issue #48 delivery; the human merge decision remains separate.
- Authority: human decision. Source: answers in the issue-48 workflow session, 2026-11-05, to
  questions D-48-1, D-48-1a, D-48-1b (each the recommended option); no permalink.
- Scope: `wled_patch_segments` (#6) and `wled_replace_layout` (#7). Not a project default; master
  `wled_set_state` is not changed by this entry.
- Decision (option B, 1a: 32 UTF-8 bytes, 1b: reject), identical for both tools:
  - Before any write (and in dry run) reject with `VALIDATION_ERROR`: segment names over 32 UTF-8
    bytes or containing U+0000; `grouping` outside 1-255 and `spacing` outside 0-255; `on=true` with
    `brightness=0`; `brightness=0` with omitted `on` on a segment that is currently on.
  - A positive `brightness` with omitted `on` on a segment that is currently off is compensated: the
    resolved `on=false` is sent with `bri`, shown as targeted compensation, and the resolved `on` is
    verified whenever `bri` is sent.
  - The 32-byte name limit applies to every device (the firmware buffer is a build option).
- Conditions: pinned v0.15.1 source (profile 0, ISSUE-6-DEC-002); hardware confirmation stays with #12.
- Supersedes: for #7, the name limit, absent 255 bounds and `bri` sending rule of
  [ISSUE-7-DEC-006](stage-1.md#issue-7-dec-006--align-7-with-6-limits-and-bri-handling).
  ISSUE-7-DEC-007 stays in force and now also applies to #6. For #6 it tightens the character-based
  name limit and unbounded grouping/spacing.
- Affected: SEG-01, SEG-03 to SEG-05, CTRL-01 (segment part), T04-T08.

## Issue #52 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

### ISSUE-52-DEC-001 — Master power is preserved when only brightness is sent

- ID: ISSUE-52-DEC-001
- Status: active for issue #52 only.
- Authority: delegated decision; the owner delegated the #52/#53 decisions to the coordinator
  ("decide as much as possible yourself", 2026-11-05, no permalink). Based on the requirements
  packet (D1-D8) and the pinned v0.15.1 source; no hardware observation.
- Scope: master part of `wled_set_state`; segment tools follow
  [ISSUE-48-DEC-001](hardening.md) as a model only.
- Decision:
  - D1: positive `brightness` with omitted `on` on an off master sends `{"on": false, "bri": X}`;
    the master stays off with X remembered.
  - D2: `plan.targeted_compensation` is always present: `[]` or `[{"on": false}]`; `plan.on` stays
    `null`, `plan.resolved.on` is `false`; dry run shows the same with zero writes.
  - D3: every master write verifies the resolved `on`; a power flip is `VERIFICATION_MISMATCH`.
  - D4: a state without a boolean master `on` is already `INVALID_RESPONSE` before planning.
  - D5: `tt` unchanged; transition effect stays unverified (#12).
  - D6: existing master rejections (`on=true` with `brightness=0`; `brightness=0` without `on=false`
    on an on master) unchanged.
  - D7: `wled_set_state` has no segment fields; the compensating `on=false` leaves segment power alone.
  - D8: an external power change between read and write remains a documented residual risk.
- Conditions: profile 0 (pinned source); revisit with #12 hardware evidence.
- Affected: CTRL-01, T04, `patches.py`, TOOL-CONTRACT. Supersedes: no recorded decision.

## Issue #53 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

### ISSUE-53-DEC-001 — Precise socket guard for the listener-free stdio test

- ID: ISSUE-53-DEC-001
- Status: active for issue #53 only.
- Authority: delegated decision; the owner delegated #52/#53 to the coordinator ("decide as much as
  possible yourself", 2026-11-05, no permalink). Based on Windows 11 / CPython 3.13.2 diagnostics:
  the only socket events during a default stdio start are a loopback bind to port 0 and the matching
  connect by `socket._fallback_socketpair` (asyncio self-pipe); none come from `wled_mcp` or the SDK.
- Scope: `tests/test_http_cli.py` stdio no-listener check. No product change, no skip or `xfail`.
- Decision: fix the test, not the product. During a default stdio run only operations whose direct
  caller is `socket._fallback_socketpair` are allowed: a loopback bind to port 0, that function's own
  `listen()`, and a loopback connect. Every other bind, listen, connect, sendto, sendmsg or
  getaddrinfo is a violation. `listen()` is recorded by wrapping `socket.socket.listen` in the probe
  subprocess (no audit event exists). Negative controls prove the guard catches a real listener, a
  wildcard bind, an unbound `listen()`, an asyncio server, a foreign loopback connect and a UDP send,
  without leaving an externally reachable listener open.
- Conditions: CPython internals may change in other versions; supported-version CI must stay green.
- Affected: MCP-03/OPS-05 (C14-08/09), tests/test_http_cli.py. Supersedes: none.

## Issue #55 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

### ISSUE-55-DEC-001 — Deterministic deadline/retry test with controlled time

- ID: ISSUE-55-DEC-001
- Status: active for issue #55 only.
- Authority: technical decision by the coordinator within the owner's instruction to implement #55
  (2026-11-05, no permalink); the #52/#53 delegation is not reused. No product behavior changes.
- Source: #55 packet with Windows 11 / CPython 3.13.2 diagnostics: `anyio.sleep(0.04)` took up to
  54.8 ms (timer step about 15.6 ms), exhausting the 50 ms deadline before the retry; the client
  behaved correctly (REL-01, ISSUE-4-DEC-003).
- Scope: `tests/test_inventory_client.py` deadline/retry tests only.
- Decision: replace the wall-clock sleep with controlled time (advance `anyio.current_time` in the
  mocked handler) and assert per-attempt budgets from `request.extensions["timeout"]["read"]` against
  a 5 s deadline: first attempt 4.9 s gives one retry with the remaining 0.1 s; 1 s per attempt still
  gives two calls; 5.1 s gives no retry. Keep one real-hang test proving the shared remainder cancels
  the retry. No VALIDATION.md change (parallel #10 work); evidence goes in the PR.
- Conditions: test-only; a minimum read budget or Windows deadline overshoot are separate questions.
- Affected: REL-01 evidence. Supersedes: none.

## Issue #61 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

### ISSUE-61-DEC-001 — Accept underscores in `base_url` host labels

- ID: ISSUE-61-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #61 only.
- Authority/source: human decision, owner answer 2026-11-06 choosing issue option A
  ("Unterstrich erlauben", English: "allow underscore") over option B; no permalink.
- Scope: `base_url` host validation in `src/wled_mcp/config.py`, tests and inventory docs.
- Decision: an underscore is accepted in DNS host labels of a device `base_url`. Everything else
  stays fail-closed: userinfo, query, fragment, path, whitespace and percent-encoding remain
  rejected; IP-literal handling unchanged; no discovery or name scanning. A rejected inventory
  names the offending device entry without echoing secrets.
- Conditions: label rules beyond the underscore are technical proposals (DEC-002).

### ISSUE-61-DEC-002 — Host label rules and device-locating error message

- ID: ISSUE-61-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #61 only; technical proposals TD-61-1 to TD-61-9 accepted by the
  coordinator, not a human decision; the owner may veto at review.
- Decision:
  - TD-61-1 to TD-61-6: label characters `[A-Za-z0-9_-]`, ASCII only, at most 253 characters,
    each label 1–63 characters starting and ending with a letter or digit (underscore-only
    labels rejected); no special rule for last or single labels; IP-literal, IPv6, case and
    normalization handling unchanged.
  - TD-61-7: the diagnostic locates entries only from the validation error location, as
    `devices[<zero-based index>]` plus the field (`id`, `name`, `base_url`; unknown key reported
    as unsupported field without its name); at most five locators; never value, URL, host or
    exception text. Non-device errors keep the generic message.
  - TD-61-8: the device id is not shown. TD-61-9: probe script and `--allowed-host` out of scope.
- Conditions: revisit if an HTTP library upgrade starts IDNA-encoding ASCII hosts (guarded by a
  client-level test). Refines DEC-001.

## Issue #62 decisions

Read with [DECISIONS.md](../DECISIONS.md) (shared DEC-009). Recorded 2026-11-06.

### ISSUE-62-DEC-001 — Technical defaults for the public-ready baseline

- ID: ISSUE-62-DEC-001
- Status: active for issue #62 only.
- Authority: technical proposals TD-62-1 to TD-62-12 by the requirements agent, accepted by the
  coordinator; not a human decision (the owner may veto at merge review, notably the AGENTS.md
  language rule and `.lan`/`.local` as private suffixes). Source: packet, 2026-11-06.
- Decision:
  - A stdlib-only `scripts/check_private_identifiers.py` scans all tracked text files as its own
    CI step: private, link-local and shared IPv4, IPv6 link-local/unique-local, home/user paths,
    router-local DNS suffixes, MAC addresses outside the documentation range, personal-looking
    e-mail addresses. Loopback and documentation ranges are allowed.
  - A tracked allowlist (path, value, reason; stale entries fail) and an optional untracked
    denylist (`WLED_MCP_PRIVATE_DENYLIST` or `runtime/private-denylist.txt`); matches are never printed.
  - Neutral roles: "owner" in decision records, "maintainer" in workflow docs, "operator" in
    deployment/validation docs; "project conversation" becomes "coordinator session". German owner
    quotes stay verbatim. AGENTS.md language rule: discuss in the maintainer's language, commit English.
  - A wording check with negative controls guards against installation-specific framing.
  - Status/agent index moves from README.md to `docs/PROJECT.md`; README installs from a locally
    built wheel and the example files; nothing is published.
  - `pyproject.toml` gets neutral description, keywords and URLs; no authors, no license.
  - The remaining owner-decision checklist goes to `docs/STAGE-2.md`. One PR, three ordered commits.
- Affected: DEC-005, DEC-009, S2-PUBLIC-01/02 (preparatory); #62, #23. Supersedes: none.

## Issue #66 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

### ISSUE-66-DEC-001 — WLED 16 `bs` key in state presets

- ID: ISSUE-66-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #66 only.
- Authority/source: technical determination by the requirements agent (TD-66-1 to TD-66-5),
  accepted by the coordinator; not a human decision, the owner may veto at review. Implementation
  authority: owner instruction "#66 nach workflow umsetzen" (English: "implement #66 per
  workflow"), 2026-11-06 (DEC-001). Evidence: read-only review of WLED source tag `v16.0.1`
  ([SOURCES.md](../SOURCES.md#issue-66-wled-16-preset-evidence)).
- Scope: preset classification, save verification and save-result warning of the preset tools.
- Decision:
  - Determination: top-level `bs` is the global blending (transition) style, read by
    `deserializeState`, masked to 5 bits, only consumed by rendering, not persisted to
    configuration, not synced, not a preset, playlist or control action; light state like
    `transition`, safe in a `state` preset.
  - TD-66-1 `bs` joins the `state` allowlist; the observable-field rule (one of `on`, `bri`,
    `seg`) is unchanged, so `bs` alone is not a state preset; no value or type check.
  - TD-66-2 `bs` is a compared master field on save, only when present in the live state read
    before the save.
  - TD-66-3 A save whose stored entry does not classify as `state` adds one warning naming only
    the unexpected top-level key names; outcome unchanged, no corrective write or retry.
  - TD-66-4 Activation (`{"ps": id}`, control keys, playlist rules, verification) is unchanged;
    `bs` is not verified on activation.
  - TD-66-5 The stateful test fake stores `bs` only when its live state has it; the default fake
    stays 0.15-shaped.
- Conditions: evidenced for the v16.0.1 source only (not hardware); 0.15.x unaffected; other 16.x
  revisions and forks not reviewed; other new top-level keys stay `unknown`. Amends the `state`
  allowlist of SOURCES.md "Issue-9 preset evidence"; does not supersede ISSUE-9-DEC-001. A
  hardware re-check of save then activate on a WLED 16 controller is pending (#12 follow-up) and
  needs its own authorization.

## Issue #74 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

### ISSUE-74-DEC-001 — Reject invalid IPv4-like hosts and map client URL errors

- ID: ISSUE-74-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #74 only.
- Authority/source: human decision, owner instruction 2026-11-06, "#74 nach Workflow, beide
  Optionen" (English: "#74 per workflow, both options"); no permalink.
- Scope: `base_url` host validation in `src/wled_mcp/config.py` and the client's handling of
  client-side URL errors.
- Decision: both options. (A) Inventory validation rejects all-numeric dotted hosts that are not
  valid IPv4, failing closed at startup and naming the device entry as in #61. (B) Client-side
  URL errors such as `InvalidURL` map to a safe domain error. Diagnostics never echo the URL or
  host; no discovery or name scanning.
- Conditions: exact host shapes and error code are technical proposals (DEC-002). Amends
  ISSUE-61-DEC-001's "IP-literal handling unchanged" for #74 only.

### ISSUE-74-DEC-002 — Numeric-host rule, error code and test scope

- ID: ISSUE-74-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #74 only; technical proposals TD-74-1 to TD-74-6 accepted by the
  coordinator, not a human decision; the owner may veto at review.
- Decision:
  - TD-74-1: if the last host label is all decimal digits or `0x` plus hex digits, the host must
    be a canonical dotted-quad IPv4 (four parts, 0–255, no leading zeros), else rejected with a
    fixed message (short, hex and integer forms like `1.2.3`, `0x7f.1`, `2130706433` would
    otherwise resolve to another address).
  - TD-74-2: client-side `InvalidURL` maps to `CONFIG_ERROR` with a fixed message, no retry.
  - TD-74-3: a write with such a URL ends as not attempted; nothing is sent.
  - TD-74-4: tests assert startup and client errors suppress the original exception (#61 note).
  - TD-74-5/6: documentation as in the packet; `--allowed-host`, the probe script, IPv6 and valid
    special addresses stay out of scope.
- Conditions: for #74 overrides TD-61-5's "IP-literal handling unchanged"; refines DEC-001.
  Tests must stub connections as well as name resolution.

## Issue #94 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

### ISSUE-94-DEC-001 — Unplanned features and upload exclusion scope

- ID: ISSUE-94-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #94 and the coverage list it creates.
- Authority/source: human decision, owner answer in the coordinator session, 2026-11-07, to the
  packet questions D-94-1 and N-3: "ja, merge #96 und alles nach empfehlung" (English: "yes,
  merge #96 and everything as recommended"); no permalink.
- Scope: status vocabulary and figures of `docs/WLED-COVERAGE.md`; reading of the ADV-02
  exclusion in ISSUE-13-DEC-001 for the list.
- Decision:
  - D-94-1 option A: a fifth status `unplanned` for WLED features with neither an owning issue
    nor an exclusion decision. Unplanned rows count in both denominators (overall and planned
    scope); the status decides nothing about future scope.
  - N-3: the exclusion of filesystem uploads (ADV-02, ISSUE-13-DEC-001) also covers uploading
    custom palette and ledmap files; those rows are `excluded` with a link to ISSUE-13-DEC-001.
- Conditions: a later issue or decision that plans or excludes a feature changes its row. Amends
  the four-status rule of the #94 issue text.

### ISSUE-94-DEC-002 — Technical defaults for the coverage list

- ID: ISSUE-94-DEC-002
- Recorded date: 2026-11-07
- Status: active for issue #94; technical proposal (TD-94-1 to TD-94-13) accepted by the
  coordinator, not a human decision.
- Decision: the list lives in `docs/WLED-COVERAGE.md`; rows derive from WLED's own interfaces at
  the pinned source (docs/SOURCES.md) with stable row IDs; a feature delivered by a CLI command
  counts like one delivered by an MCP tool; tools without a WLED feature are listed separately
  and not counted; figures are S = supported + 0.5 x partial over all rows (overall) and over
  non-excluded rows (planned scope), generated by `scripts/check_coverage.py --update` and
  checked by a static test; feature PRs update the affected rows.
- Conditions: may be refined with a recorded rationale.

## Issue #98 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

### ISSUE-98-DEC-001 — Expected tool-contract helper design

- ID: ISSUE-98-DEC-001
- Status: active for issue #98 and every later tool-adding issue.
- Authority: technical proposal TD-98-1 to TD-98-9 accepted by the coordinator, 2026-11-07; not a
  human decision.
- Scope: plan step (b) of docs/STAGE-2-PARALLEL-PLAN.md.
- Decision: the expected tool contract lives in `tests/tool_contract.py` (standard library only, not
  shipped). It lists every tool in registry order with its class (`read`, `control`, `manage` per
  ISSUE-20-DEC-001) and a destructive flag, and derives per-profile expectations. Tests and
  `scripts/check_distribution.py` compare the real registry and served `tools/list` against it in both
  directions. A PR that adds a tool adds it there with its class.
- Conditions: until a later decision; #20 adds `wled_get_service_status` and enforces profiles.
- Affected: #98; #17-#20 packets. Supersedes / superseded by: none.
