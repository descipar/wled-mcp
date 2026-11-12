# Discovery and enrollment (DISC-01 to DISC-14, #198 to #204)

Contract for milestone M8. Nothing here is implemented yet: the statements describe the
target behavior of issues #199 to #204, and every statement about current behavior
elsewhere in the documentation stays true until the owning implementation PR changes it.
The tools below are not registered in the released server.

Decisions: [DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment) is the
owner decision (confirmed part). [ISSUE-198-DEC-001](../decisions/issue-198.md) records the
technical proposals; every value or rule marked **TP-n** below is such a proposal, not a
human decision, and the owner can override it. Both transports (stdio and Streamable HTTP)
share these operations and schemas. The contract names no concrete addresses (DEC-005); range
examples use placeholders such as `<private-network>/24`.

## Requirements

"Confirmed" means derived from the owner answers recorded in DEC-035; "proposed" means the
detail is a technical proposal.

| ID | Statement | Basis | Owner issue |
| --- | --- | --- | --- |
| DISC-01 | Discovery runs only on explicit invocation (CLI `discover`, tool `wled_discover_devices`), never at startup or implicitly, and writes nothing. | confirmed | #200, #199 |
| DISC-02 | Methods are mDNS (`_wled._tcp`, `_http._tcp` fallback verified through `/json/info`, several rounds) and unicast `GET /json/info` over configured ranges. A controller is identified by the `/json/info` content, never by port. | confirmed | #199 |
| DISC-03 | Results merge by MAC. Controllers already in the inventory are `known`; a known controller at another address is `address_changed` and is never rewritten. | confirmed | #199, #200 |
| DISC-04 | The coverage report lists methods run, ranges covered, timeouts and the mDNS no-answer reason. `none_found_complete` only when every attempted method completed; otherwise `none_found_incomplete` or `not_looked`. A run that could not look never reports that nothing was found. | confirmed; schema proposed | #199, #200 |
| DISC-05 | Hard server-side caps (RFC 1918 only, no loopback, link-local or public addresses, at most a /24 per range, few ranges, bounded timeouts, concurrency and size) that no parameter, configuration key or environment variable overrides; the startup validator and the probe re-check them. | confirmed; numbers proposed | #199, #202 |
| DISC-06 | Without configured ranges `wled_discover_devices` runs mDNS only and returns proposed ranges derived from inventory addresses; proposals are never probed until stored. | confirmed | #200 |
| DISC-07 | `wled_set_discovery_ranges` replaces the stored range list through the inventory writer, validates against the caps, rejects with fixed reason codes, is a `manage`-class configuration write hidden by the `read-only` and `control` profiles; hand editing stays possible. | confirmed; details proposed | #202 |
| DISC-08 | `wled_add_device` verifies the address with `GET /json/info`, rejects a duplicate ID, address or MAC, writes the entry and returns the exact entry. It is a configuration write (`manage`) and never writes to the device. | confirmed; details proposed | #203 |
| DISC-09 | The inventory writer is atomic, backed up, validated by the startup validator and serialized against concurrent writers (also the CLI); a file or directory that is not writable yields `STORAGE_FAILED`. | confirmed; details proposed | #201 |
| DISC-10 | Inventory changes by these tools take effect by in-process reload: running requests finish on the old inventory; an invalid result keeps the working inventory and reports the error; profile and cap changes still need a restart. | confirmed; reload scope proposed | #201 |
| DISC-11 | Nothing is enrolled or stored without a confirmed MCP-client call of a configuration-write tool; there is no interactive approval inside the plugin; stderr diagnostics omit secrets and installation addresses. | confirmed | #200, #202, #203 |
| DISC-12 | Standard library only, no extra service, the same code in the `uvx` package and the container image (OPS-01); works over stdio and HTTP. | confirmed | #199 to #203 |
| DISC-13 | Tests use mocks and fake sockets; ordinary CI never contacts a LAN device or opens a real multicast or unicast probe; new tests also pass on Windows (DEC-033). | confirmed | #199 to #203 |
| DISC-14 | Evidence: one authorized read-only discovery run per deployment mode (stdio on the host, HTTP in a container, including a case where mDNS finds nothing and the unicast probe does) and one authorized enrollment on the test controller that changes only the inventory; documentation, README and the minor release are prepared; publication stays owner-gated. | confirmed | #204 |

## Acceptance scenarios

| ID | Scenario | Evidence |
| --- | --- | --- |
| DISC-T01 | Identification by `/json/info` content, not by port: non-WLED answers on port 80, malformed, oversized and redirecting responses are never candidates. | mocked |
| DISC-T02 | Deduplication by MAC across methods and addresses; `known` and `address_changed`; the inventory is unchanged by discovery. | mocked |
| DISC-T03 | Each hard cap: public, loopback and link-local ranges, a /23, a fifth range, host bits set, and a hostile hand-edited file at startup and at probe time. | mocked |
| DISC-T04 | Coverage-report precedence, one case per rule: no usable socket gives `not_looked`; mDNS completed with no answers and unicast skipped gives `none_found_incomplete` with `complete` false; a deadline that leaves hosts `not_probed` gives `none_found_incomplete`; all hosts probed with some `timed_out` and every method `completed` gives `none_found_complete`. | mocked |
| DISC-T05 | Range proposal derivation (mixed private, public and DNS hosts, more than the maximum number of ranges) and "never probes proposals". | mocked |
| DISC-T06 | Writer and reload: atomic replace, concurrent writers including the CLI, rollback on an invalid result, unwritable file or directory, an in-flight request keeps the old inventory, a hand edit after startup refuses with `INVENTORY_CONFLICT` `file_changed`, an `[access]` mismatch refuses the reload. | mocked |
| DISC-T07 | Tool gating: profile registration filter, `Unknown tool`, annotations, class equal to `tests/tool_contract.py`, identical stdio and HTTP descriptors. | mocked |
| DISC-T08 | Live (authorized only, #200, #203, #204): read-only discovery runs in both deployment modes and the single enrollment, each restoring the inventory afterwards. | hardware, separate evidence |

## Tools

All three tools return the common envelope (TOOL-CONTRACT "Results and errors"); new error
codes are additive (ISSUE-130-DEC-001). None takes a `device_id`, so the device ceiling
(G2) does not apply, and none writes to a device, so G3 is not involved.

| Tool | Class | readOnly / destructive / idempotent / openWorld | Reachable in |
| --- | --- | --- | --- |
| `wled_discover_devices` | `read` | true / false / true / true | every profile |
| `wled_set_discovery_ranges` | `manage` | false / true / true / false | `full` |
| `wled_add_device` | `manage` | false / false / false / true | `full` |

**TP-1** (annotations as in the table; "Tools at a glance" hints `read-only`, `destructive`
because the stored list is replaced, and `write`).

**TP-2** (class `manage`). `manage` means device storage or a local persistent artifact
(profiles.md); the inventory file is a local persistent artifact, so no class or profile is
added. The `control` and `read-only` profiles do not register the two write tools
(registration filter G1, `-32602 Unknown tool`), which is how an operator disables them.
`wled_discover_devices` is `read`: it opens sockets but mutates no live, storage or file
state. There is no profile below `read-only`, so an operator cannot hide
`wled_discover_devices` while keeping the other read tools; this is an accepted, documented
limitation (a new class or profile would break the three-profile model).

`dry_run` on the two write tools validates and reads only: no file write, no reload. The
dry run of a `manage` tool stays `manage` (TD-20-2).

## `wled_discover_devices`

Request (**TP-12** for the bounds). `methods`: optional subset of `["mdns","unicast"]`,
default both. `timeout_seconds`: optional, 1 to 30, lowers the deadline only. `max_candidates`:
optional, 1 to 64, lowers the cap only. There is no range, host, port, interface or cap
parameter: ranges come only from the stored configuration, and the hard caps below win over
any parameter. Unknown fields are rejected.

Result `data` (envelope `device_id` null, `application` `not_attempted`, `verification`
`not_requested`):

- `candidates[]`: `address` (IPv4), `base_url` (`http://<address>`), `suggested_id` (slug,
  unique within the inventory and the list), `suggested_name`, `mac` (**TP-9**: returned in
  candidates only, an explicit exception to the rule that `wled_get_state` removes the MAC,
  because identity is the purpose; lowercase 12 hex digits), `firmware_version`, `product`,
  `found_by` (subset of `mdns`, `unicast`), `status` (`new`, `known`, `address_changed`),
  `known_device_id` for known ones, `configured_address` (host of the configured `base_url`)
  for `address_changed`, and `alternate_addresses` (at most 4) when one MAC answered from
  several addresses.
- `coverage`: the report, always present (see [Coverage report](#coverage-report)).
- `proposed_ranges[]`: each `{cidr, derived_from_device_ids}` (see
  [Range proposals](#range-proposals)). It is a list, not an executable call: the client's
  confirmation of `wled_set_discovery_ranges` shows the exact ranges.
- `warnings[]`.

A candidate is listed only after `GET /json/info` returned a JSON object that passes the
WLED identity check (the fields and values read in the pinned WLED source, recorded in
docs/SOURCES.md by #199); never by port alone. mDNS answers, the `_http._tcp` fallback in
particular, are verified through `/json/info` too. Results merge by MAC across methods and
addresses.

Errors: `VALIDATION_ERROR` (bad parameter), `DISCOVERY_BUSY` (**TP-3**: one run at a time per
process; a second concurrent call fails fast and probes nothing), `CONFIG_ERROR` (stored
ranges invalid; defensive, startup validation normally prevents it). A method that could not
run is not an error: the call returns `ok=true` and the coverage report says so, including the
case where no method could run (`conclusion` `not_looked`). Local socket failures never become
`UNREACHABLE`, which is per device.

## `wled_set_discovery_ranges`

Request: `ranges` (array of 0 to 4 strings; replace semantics, not merge, so the confirmation
shows the final list; an empty array clears the list and discovery then runs mDNS only) and
`dry_run` (default false). Each string is an IPv4 CIDR `a.b.c.d/p`, validated strictly
(**TP-12**): host bits must be zero (no silent normalization), prefix 24 to 30, no whitespace (a /31 or /32 is rejected as `prefix_too_long`).

Rejections come back as `VALIDATION_ERROR` with `data.rejected[]` = `{index, reason}`; the
reasons are fixed: `not_ipv4_cidr`, `not_network_address`, `not_private` (outside 10/8,
172.16/12 and 192.168/16, which also covers public, 100.64/10, multicast and reserved
space), `loopback`, `link_local`, `too_broad`, `prefix_too_long`, `overlap`, `duplicate`. A list of more than 4 entries is rejected by the schema (array maximum), so there is no per-entry reason for it. Values are
not echoed in `error.message` (fixed text) or in `data.rejected`; the client already holds
them.

Result `data`: `ranges_before`, `ranges_after`, `changed`, `written` (false for a dry run or
a no-op), `reloaded`, `backup` (boolean: the previous file was kept) and `caps`. An identical
list writes nothing. Errors: `VALIDATION_ERROR`, `INVENTORY_CONFLICT` (`file_changed`, see
[Reload semantics](#reload-semantics)), `STORAGE_FAILED` (file or directory not
writable, writer failure; nothing changed, `application` `not_applied`) and
`INVENTORY_RELOAD_FAILED` (**TP-3**: the written candidate failed the startup validator or the
reload; the previous file is restored and the working inventory kept, `application`
`not_applied`, or `unknown` if the restore also failed).

## `wled_add_device`

Request: `base_url` (required; **TP-5**: `http://` plus an RFC 1918 IPv4 literal and an
optional port 1 to 65535; no path, query or credentials; DNS names and public addresses are
not accepted by the tool and stay a manual or CLI path), `device_id` (optional, 1 to 64
characters, the inventory ID rules; default the suggested slug), `name` (optional, 1 to 64
characters, no control characters), `expected_mac` (optional, from the candidate; a different
MAC reported by `/json/info` gives `VALIDATION_ERROR` with `data.reason` `mac_mismatch`) and
`dry_run`. The tool takes no candidate object (a client could forge one); it re-verifies.

Flow: validate the request; verify with one `GET /json/info` (the same identity check, the
timeout and size limits of the hard caps, no redirects, no proxy, GET only); conflict checks;
build the entry; write; reload. The result `data` has `entry` (`id`, `name`, `base_url`, `mac`:
exactly what was written), `verified` (`firmware_version`, `product`), `inventory_size`,
`reloaded` and `written`. The envelope `device_id` is the new ID on success and null on
failure (**TP-6**). The tool never POSTs, never touches the device beyond the one read and
never sets `max_class`.

Errors: `VALIDATION_ERROR` (bad fields, `mac_mismatch`, address outside the policy),
`UNREACHABLE`, `TIMEOUT`, `INVALID_RESPONSE`, `NOT_WLED` (**TP-3**: the answer is not a WLED
`/json/info`; nothing written), `INVENTORY_CONFLICT` (**TP-3**: `data.conflict` is `id`,
`base_url`, `mac` or `file_changed`, with `data.known_device_id` (omitted for `file_changed`); nothing written; an existing entry is never
overwritten), `STORAGE_FAILED` and `INVENTORY_RELOAD_FAILED`. A duplicate is an equal
normalized `base_url` (the rule of `config add-device`, TD-16-3) or an equal MAC of an entry
that has a stored `mac`. A timeout of the verification read is `not_applied`: nothing was
written and a repeat is safe.

## Hard caps

Server constants in code, shown read-only in `coverage.caps`. No parameter, environment
variable or configuration key raises them; a lower tool value is allowed. The values are
**TP-4**.

- Address space: IPv4 only; 10/8, 172.16/12 and 192.168/16 only. Loopback,
  169.254/16 link-local, 100.64/10, multicast, broadcast and the network and broadcast
  addresses of a range are never probed. The check is on the numeric address after parsing:
  no hostname, no DNS, no redirect target, no `http://user@` form.
- At most a /24 per range (prefix 24 or longer) and at most 4 ranges (1016 hosts per run at
  most).
- Per host: one `GET /json/info` on TCP port 80 only; 1.5 s connect plus read in total; a
  response body of at most 64 KiB; the JSON depth and node bounds of `client.py`; no
  redirects, no proxy environment, no connection reuse across hosts; a fixed `User-Agent`.
- At most 32 sockets in flight; probe-phase deadline 20 s; whole-call deadline 30 s. mDNS: 3
  query rounds 1 s apart, a listening window of 6 s in total, the datagram, record and name
  bounds of `discovery.py`. Candidate cap 64 (as in the CLI).
- Single flight (`DISCOVERY_BUSY`) and a minimum gap of 5 s between probe-phase starts per
  process, which bounds repeated agent scans; the call returns `DISCOVERY_BUSY` with
  `retry_after_seconds`. The gap does not apply to an mDNS-only run.
- The range list is re-validated against the caps at probe time (defence in depth), so a
  hand-edited file that passed an older validator cannot widen the scan.

Operators may set the ranges by hand in the same `[discovery]` table. The startup validator
applies the same caps: an over-broad range stops startup with exit code 2 and a positional
message (`discovery.ranges[i]: invalid`), with no value echoed, like `access.profile: invalid`.

## Range proposals

**TP-7.** For each inventory device whose `base_url` host is an RFC 1918 IPv4 literal, the
containing /24 is taken; duplicates are merged and the result is sorted ascending. DNS hosts
are not resolved: they are counted in `coverage.unproposed_devices` with reason
`host_not_ipv4_literal`, non-private literals with reason `not_private`. If more than 4
ranges result, the first 4 are returned and `proposed_ranges_omitted` gives the rest.
`proposed_ranges` excludes ranges already configured, so it also shows uncovered /24s next to
a configured list. A proposal is never probed, in the same call or a later one, until a
`wled_set_discovery_ranges` call stores it. Without configured ranges `unicast` is skipped
with reason `no_ranges_configured`.

## Known controllers and a changed address

**TP-9.** A candidate is known when its address equals the host of a configured `base_url`,
or its MAC equals the stored `mac` of a configured entry, or, for entries without a stored
MAC, the MAC read by one extra `GET /json/info` of that configured device inside the run
(only configured URLs, the same size and timeout caps, at most 16 devices, counted in
`coverage.known_devices_checked`). Devices that did not answer are counted in
`known_devices_unmatched`, so `address_changed` is claimed only on a MAC match.

`address_changed`: the MAC matches configured entry X but the address differs from X's host.
The candidate gets `status` `address_changed`, `known_device_id` X and `configured_address`.
The inventory is not modified by discovery, by `wled_add_device` (which answers
`INVENTORY_CONFLICT` with `conflict` `mac`) or by any other tool; the operator edits the file.
An update tool is out of scope for M8 (owner answer 5 of DEC-035).

## Coverage report

`data.coverage` is always present, also when `candidates` is empty (**TP-8**).

- `schema` 1. `conclusion`: `candidates_found`, `none_found_complete`, `none_found_incomplete`
  or `not_looked`. `complete` is a top-level boolean that is true exactly when both
  `mdns` and `unicast` were requested and ran with status `completed` and no range host is
  `not_probed`. A method skipped for any reason, including `unicast` skipped for
  `no_ranges_configured`, makes it false; so does a `partial` or `failed` method. It does not
  depend on whether candidates were found. A method's own `status` describes that method only.
- `methods[]`: `{method, requested, status, reason?}` with `method` `mdns` or `unicast`,
  `status` `completed`, `partial`, `skipped` or `failed`, and fixed `reason` codes
  `no_ranges_configured`, `not_requested`, `multicast_unavailable` (the socket cannot open or
  send; a container on a bridge network is the usual cause and the report says so),
  `no_answers` (queries were sent and nobody answered, which separates "heard nothing" from
  "could not listen"), `deadline_reached`, `cap_reached` and `internal_error`.
- `mdns`, only for a method that ran: `{rounds_sent, window_seconds, services_queried[],
  responders, answers_verified, answers_rejected}`.
- `unicast`: `{ranges[], deadline_reached}` with, per range, `{cidr, hosts_total,
  hosts_probed, answered_wled, answered_other, refused, timed_out, not_probed}`.
- `known_devices_checked`, `known_devices_unmatched`, `proposed_ranges_omitted`,
  `unproposed_devices`, `caps` (the numeric hard caps) and `limits[]`: fixed English sentences
  (multicast stays in the local network segment and does not cross VLANs; a controller with an
  empty mDNS name does not announce itself; a probe reaches only configured ranges; hosts that
  did not answer in time are unknown, not absent).

Rule (DISC-04), evaluated in this order:

1. A method that was requested and could not run (socket failure, `internal_error`) counts as
   attempted-but-`failed`. If no requested method ran at all (all `failed` or `skipped`, or
   none requested), `conclusion` is `not_looked` and `complete` is false.
2. Otherwise, with candidates found, `conclusion` is `candidates_found`; `complete` follows
   the definition above.
3. Otherwise, with no candidates, `none_found_complete` requires exactly the condition of
   `complete`: both methods were requested and ran `completed`, and no range host is
   `not_probed`. A run with only one method, or with `unicast` skipped (for example mDNS
   `completed` with zero answers and `no_ranges_configured`), is never exhaustive: it is
   `none_found_incomplete` with `complete` false, and `limits` says so. A host that was probed and did not answer
   within its timeout counts as `timed_out`, is unknown and does not block
   `none_found_complete`; a host left unprobed because a deadline or cap ended the run does
   block it. Any other combination is `none_found_incomplete`.

The text `content` block of the tool result repeats `conclusion` first. The rule that a run
which could not look never reports that nothing was found is an owner requirement stated with
the M8 issue text on 2026-11-12 and recorded in DEC-035.

## Configuration

**TP-11.** The inventory TOML gains the optional table `[discovery]` with `ranges =
["<private-network>/24"]` (an array of 0 to 4 strings). `schema_version` stays 1 (additive, like
`[access]`). An unknown key in the table gives `discovery: unsupported field` (positional, no
echo). Root keys and `[discovery]` come before the first `[[devices]]`, as for `[access]`
(profiles.md), and the writer emits them in that order. A device gains the optional `mac`
(12 lowercase hex digits, no separators; a colon-separated form is normalized when read). It
is written by `wled_add_device`, used only to match a controller whose address changed and
never to route a request. An older build rejects the unknown keys at startup with exit code 2;
a downgrade uses the configuration kept for that version. The migration-notes rows in
versioning.md for `/discovery` and `/devices/mac` are added by #202 and #203 when the release
version is known.

## Reload semantics

**TP-10** (contract text for #201).

- Only changes made by these tools apply in-process. The reload replaces the device list and
  the discovery ranges and nothing else.
- `[access]` profile and per-device `max_class` of the loaded file must equal those of the
  running process, because the tool registry is built once. A mismatch makes the reload fail
  with `INVENTORY_RELOAD_FAILED` and the file is not replaced; changing profile or caps still
  needs a restart (profiles.md).
- Requests running at the swap complete against the old inventory (an immutable snapshot);
  new requests see the new one. New device IDs get their lock lazily. Per-device state (catalog
  cache, signals) is keyed by ID and unaffected for unchanged entries. These tools never remove
  an ID.
- The writer's base is the file on disk, not the loaded snapshot: it re-reads the file under
  the lock and compares it with the content the running process loaded or last wrote. If they
  differ (a hand edit or another process's write after startup), the call refuses with
  `INVENTORY_CONFLICT` and `data.conflict` `file_changed`, writes nothing and tells the
  operator to run `wled-mcp config validate` and restart. The same refusal applies when the
  `[access]` profile or a `max_class` in the file on disk differs from the running process
  (`INVENTORY_RELOAD_FAILED` when only the post-write reload detects it).
- Hand edits are not picked up: there is no file watching and no signal-triggered reload;
  `wled-mcp config validate` plus a restart remains for them.
- The writer holds the cross-process lock, so `wled-mcp config add-device` (another process)
  and the tools cannot interleave. It keeps the previous file as a backup (location decided by
  #201) and fails with `STORAGE_FAILED` if the file or its directory is not writable. A
  read-only bind mount of a single file cannot be replaced atomically: mount the configuration
  directory, not the file.

## Security and privacy

- Result text and logs never contain secrets. stderr diagnostics name counts and codes, never
  the addresses of an installation. Tool results do contain candidate addresses and MACs
  because that is the product; they go to the MCP client the caller already trusts. Committed
  documentation and examples use generic ranges only (DEC-005).
- `wled_add_device` accepts any port on a private host, so repeated confirmed calls can tell open from closed ports there. That is acceptable under the client's confirmation of a `manage` call and is limited by the single-GET, size and timeout bounds. The discovery probe itself uses port 80 only.
- Probing sends no credentials, never POSTs and never reads another path.
- A discovery or enrollment call is not retried automatically. After `STORAGE_FAILED` the file
  is unchanged.

## Transports and containers

Stdio and HTTP use the same operations and schemas. mDNS from a container on a bridge network
usually hears nothing; the report states `multicast_unavailable` or `no_answers` with the
limit text. Unicast probing works from a container to its routed network, which is the stated
reason for the probe in DEC-035 item 3. The write tools need a writable configuration
directory (`STORAGE_FAILED` otherwise).

## Related

- [DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment),
  [ISSUE-198-DEC-001](../decisions/issue-198.md).
- [cli.md](cli.md): the `wled-mcp discover` and `config` commands; the shared engine replaces
  the CLI engine in #199.
- [profiles.md](profiles.md): classes, profiles and the registration filter.
- [DEPLOYMENT.md](../DEPLOYMENT.md): inventory changes and the released `discover` behavior.
