# Discovery and enrollment (DISC-01 to DISC-14, #198 to #204)

Contract for milestone M8. The shared engine (`src/wled_mcp/discovery_engine.py`), the CLI `discover`, the inventory
writer with in-process reload, `wled_discover_devices`, `wled_set_discovery_ranges` (with `[discovery].ranges` and the
hard caps) and `wled_add_device` (with `devices[].mac`) are implemented and released (see the changelog). Evidence:
mocked tests plus the live runs of [validation/m7-m8.md](../validation/m7-m8.md) and
[validation/m7-m8.md](../validation/m7-m8.md).

Decisions: [DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment) is the owner decision (confirmed
part). [ISSUE-198-DEC-001](../decisions/m7-m8.md) records the technical proposals; every value or rule marked
**TP-n** is such a proposal, not a human decision, and the owner can override it. Both transports share these operations
and schemas. The contract names no concrete addresses (DEC-005); examples use `<private-network>/24`.

## Requirements

"Confirmed" means derived from the owner answers in DEC-035; "proposed" means a technical proposal.

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

All three return the common envelope (TOOL-CONTRACT "Results and errors"); new error codes are additive
(ISSUE-130-DEC-001). None takes a `device_id`, so the device ceiling (G2) does not apply, and none writes to a device,
so G3 is not involved.

| Tool | Class | readOnly / destructive / idempotent / openWorld | Reachable in |
| --- | --- | --- | --- |
| `wled_discover_devices` | `read` | true / false / true / true | every profile |
| `wled_set_discovery_ranges` | `manage` | false / true / true / false | `full` |
| `wled_add_device` | `manage` | false / false / false / true | `full` |

**TP-1, TP-2.** Annotations as in the table; "Tools at a glance" hints are `read-only`, `destructive` (the stored list
is replaced) and `write`. Class `manage` is a local persistent artifact (the inventory file, profiles.md), so no class
or profile is added. The `control` and `read-only` profiles do not register the two write tools (G1, `-32602 Unknown
tool`), which is how an operator disables them; `wled_discover_devices` is `read` (sockets only) and cannot be hidden
while keeping other read tools (accepted limitation). `dry_run` on the write tools validates and reads only (no file
write, no reload) and stays `manage` (TD-20-2).

## `wled_discover_devices`

Request (**TP-12** for the bounds). `methods`: optional subset of `["mdns","unicast"]`, default both. `timeout_seconds`:
optional, 1 to 30, lowers the deadline only. `max_candidates`: optional, 1 to 64, lowers the cap only. There is no
range, host, port, interface or cap parameter: ranges come only from the stored configuration, and the hard caps win
over any parameter. Unknown fields are rejected.

Result `data` (envelope `device_id` null, `application` `not_attempted`, `verification` `not_requested`; `conclusion` is
the first key):

- `candidates[]`: `address` (IPv4), `base_url` (`http://<address>`), `suggested_id` (slug, unique within the inventory
  and the list), `suggested_name`, `mac` (**TP-9**: returned in candidates only, an explicit exception to the MAC
  removal of `wled_get_state`, because identity is the purpose; lowercase 12 hex digits), `firmware_version`, `product`,
  `found_by` (subset of `mdns`, `unicast`), `status` (`new`, `known`, `address_changed`), `known_device_id` for known
  ones, `configured_address` (host of the configured `base_url`) for `address_changed`, and `alternate_addresses` (at
  most 4) when one MAC answered from several addresses.
- `coverage`: always present ([Coverage report](#coverage-report)).
- `proposed_ranges[]`: each `{cidr, derived_from_device_ids}` ([Range proposals](#range-proposals)). A list, not an
  executable call: the client's confirmation of `wled_set_discovery_ranges` shows the exact ranges.

Warnings of the run (for example a reached candidate cap) are the envelope field `warnings`; `data` has no `warnings`
key (ISSUE-200-DEC-001).

A candidate is listed only after `GET /json/info` returned a JSON object that passes the WLED identity check (fields and
values read in the pinned WLED source, docs/SOURCES.md); never by port alone. mDNS answers, the `_http._tcp` fallback in
particular, are verified the same way.

Errors: `VALIDATION_ERROR` (bad parameter), `DISCOVERY_BUSY` (**TP-3**: one run at a time per process; a second
concurrent call fails fast and probes nothing), `CONFIG_ERROR` (stored ranges invalid; defensive). A method that could
not run is not an error: the call returns `ok=true` and the coverage report says so, including the case where no method
could run (`conclusion` `not_looked`). Local socket failures never become `UNREACHABLE`, which is per device.

## `wled_set_discovery_ranges`

Request: `ranges` (array of 0 to 4 strings; replace semantics, not merge, so the confirmation shows the final list; an
empty array clears the list and discovery then runs mDNS only) and `dry_run` (default false). Each string is an IPv4
CIDR `a.b.c.d/p`, validated strictly (**TP-12**): host bits zero (no silent normalization), prefix 24 to 30, no
whitespace (a /31 or /32 is `prefix_too_long`). Syntax is dotted-quad in ASCII: netmask or hostmask notation,
whitespace, zero-padded octets or prefix and non-ASCII digits are `not_ipv4_cidr` (ISSUE-202-DEC-001, TP-202-2).

Rejections come back as `VALIDATION_ERROR` with `data.rejected[]` = `{index, reason}` in ascending index order; each
entry gets the first failing reason in this fixed order: `not_ipv4_cidr`, `not_network_address`, `not_private` (outside
10/8, 172.16/12 and 192.168/16, which also covers public, 100.64/10, multicast and reserved space), `loopback`,
`link_local`, `too_broad`, `prefix_too_long`, `overlap`, `duplicate` (both compare with earlier entries that passed).
More than 4 entries are rejected by the schema (array maximum), without a per-entry reason. Values are not echoed in
`error.message` or `data.rejected`.

Result `data`: `ranges_before`, `ranges_after`, `changed`, `written` (false for a dry run or a no-op), `reloaded`,
`backup` (boolean: the previous file was kept) and `caps`. An identical list writes nothing. Success is `application`
`not_attempted`, `verification` `not_requested`, `device_id` null (a local file artifact, like `wled_save_group`).
Errors: `VALIDATION_ERROR`, `INVENTORY_CONFLICT` (`file_changed`, see [Reload semantics](#reload-semantics)),
`STORAGE_FAILED` (nothing changed, `not_applied`) and `INVENTORY_RELOAD_FAILED` (**TP-3**: the written candidate failed
the startup validator or the reload; the previous file is restored and the working inventory kept, `not_applied`, or
`unknown` if the restore also failed).

Implementation (#202): caps and range checker in `src/wled_mcp/discovery_caps.py`, shared by startup validator, tool and
probe. A `dry_run` is snapshot based (TP-202-5): it compares with `Resources.discovery_ranges`, takes no lock and reads
no file, so a real call may still answer `INVENTORY_CONFLICT`. A real call writes through the shared `InventoryWriter`:
the `[discovery]` table is replaced as a whole (comments inside it dropped), inserted before the first `[[devices]]`
when absent; all other bytes and the line ending are kept. If the parsed result differs from the request (for example a
hand-written dotted key or inline table), the edit refuses with `INVENTORY_RELOAD_FAILED` stage `validation` and writes
nothing. Startup locators: `discovery.ranges[i]: invalid`, `discovery.ranges: invalid` (not an array or more than 4
entries), `discovery: unsupported field`, `discovery: invalid`. `STORAGE_FAILED` `data.reason`: `not_writable` (missing
or unwritable directory, lock file not creatable), `unreadable` (missing, non-regular or unreadable file), `locked`,
`backup_failed`, `write_failed`.

## `wled_add_device`

Request: `base_url` (required; **TP-5**: `http://` plus an RFC 1918 IPv4 literal and an optional port 1 to 65535; no
path, query or credentials; DNS names and public addresses stay a manual or CLI path), `device_id` (optional, 1 to 64
characters, the inventory ID rules), `name` (optional, 1 to 64 characters, no control characters), `expected_mac`
(optional, from the candidate; a different MAC reported by `/json/info` gives `VALIDATION_ERROR` with `data.reason`
`mac_mismatch`) and `dry_run`. The tool takes no candidate object (a client could forge one); it re-verifies.

Flow: validate; verify with one `GET /json/info` (the same identity check, the timeout and size limits of the hard caps,
no redirects, no proxy, GET only); conflict checks; build the entry; write; reload. The result `data` has `entry` (`id`,
`name`, `base_url`, `mac`: exactly what was written), `verified` (`firmware_version`, `product`), `inventory_size`,
`reloaded` and `written`. The envelope `device_id` is the new ID on success and null on failure (**TP-6**). The tool
never POSTs, never touches the device beyond the one read and never sets `max_class`.

Rules ([ISSUE-203-DEC-001](../decisions/m7-m8.md)):

- The stored `base_url` is canonical: `http://<ip>` (port 80 omitted, no trailing slash) or `http://<ip>:<port>`. A bad
  address is `VALIDATION_ERROR` with `data.field` `base_url` and a fixed `data.reason` (`invalid_url`,
  `not_ipv4_literal`, `not_private`), never the value; no name is ever resolved (**TP-203-1**).
- The read maps `other` (not WLED, redirect, non-200, oversize, malformed) to `NOT_WLED`, `refused` to `UNREACHABLE`,
  `timeout` to `TIMEOUT` and an unexpected transport error to `INVALID_RESPONSE` (**TP-203-2**).
- Duplicate ID and address are refused before any request, the MAC after the read; all three are rechecked in the
  writer's locked edit, in the order `id`, `base_url`, `mac` (**TP-203-3**).
- Success is `application` `not_attempted` and `verification` `not_requested`; failures after the read are
  `not_applied`, request validation and pre-read conflicts `not_attempted` (**TP-203-4**).
- Without `device_id` and `name` the entry uses the controller's reported name (not the generic `WLED`), else
  `wled-<last 6 of MAC>`, made unique against the current IDs (**TP-203-5**).
- `dry_run` reads once, checks the same conflicts, returns the would-be entry with `written` and `reloaded` false and
  touches no file.
- Host names are added by hand; an entry added by host name and the same controller added later by IP is caught only
  when the earlier entry stores a `mac` (backlog #264, #265).

Errors: `VALIDATION_ERROR` (bad fields, `mac_mismatch`, address outside the policy), `UNREACHABLE`, `TIMEOUT`,
`INVALID_RESPONSE`, `NOT_WLED` (**TP-3**: nothing written), `INVENTORY_CONFLICT` (**TP-3**: `data.conflict` is `id`,
`base_url`, `mac` or `file_changed`, with `data.known_device_id` (omitted for `file_changed`); nothing written; an
existing entry is never overwritten), `STORAGE_FAILED` and `INVENTORY_RELOAD_FAILED`. A duplicate is an equal normalized
`base_url` (the rule of `config add-device`, TD-16-3) or an equal MAC of an entry with a stored `mac`. A timeout of the
verification read is `not_applied`: nothing was written and a repeat is safe.

## Hard caps

Server constants in code, shown read-only in `coverage.caps`. No parameter, environment variable or configuration key
raises them; a lower tool value is allowed. The values are **TP-4**.

- Address space: IPv4 only; 10/8, 172.16/12 and 192.168/16 only. Loopback, 169.254/16 link-local, 100.64/10, multicast,
  broadcast and the network and broadcast addresses of a range are never probed. The check is on the numeric address
  after parsing: no hostname, no DNS, no redirect target, no `http://user@` form.
- At most a /24 per range (prefix 24 or longer) and at most 4 ranges (1016 hosts per run).
- Per host: one `GET /json/info` on TCP port 80 only; 1.5 s connect plus read in total; a body of at most 64 KiB; the
  JSON depth and node bounds of `client.py`; no redirects, no proxy environment, no connection reuse across hosts; a
  fixed `User-Agent`.
- At most 32 sockets in flight; probe-phase deadline 20 s; whole-call deadline 30 s. mDNS: 3 query rounds 1 s apart, a
  listening window of 6 s in total, the datagram, record and name bounds of `discovery.py`. Candidate cap 64 (as in the
  CLI).
- Single flight (`DISCOVERY_BUSY`) and a minimum gap of 5 s between probe-phase starts per process; the call returns
  `DISCOVERY_BUSY` with `retry_after_seconds`. The gap does not apply to an mDNS-only run.
- The range list is re-validated at probe time (defence in depth), so a hand-edited file that passed an older validator
  cannot widen the scan.

Operators may set the ranges by hand in the same `[discovery]` table. The startup validator applies the same caps: an
over-broad range stops startup with exit code 2 and a positional message (`discovery.ranges[i]: invalid`), with no value
echoed.

## Range proposals

**TP-7.** For each inventory device whose `base_url` host is an RFC 1918 IPv4 literal, the containing /24 is taken;
duplicates are merged and the result is sorted ascending. DNS hosts are not resolved: they are counted in
`coverage.unproposed_devices` with reason `host_not_ipv4_literal`, non-private literals with reason `not_private`. If
more than 4 ranges result, the first 4 are returned and `proposed_ranges_omitted` gives the rest. `proposed_ranges`
excludes ranges already configured. A proposal is never probed, in the same call or a later one, until a
`wled_set_discovery_ranges` call stores it. Without configured ranges `unicast` is skipped with reason
`no_ranges_configured`.

## Known controllers and a changed address

**TP-9.** A candidate is known when its address equals the host of a configured `base_url`, or its MAC equals the stored
`mac` of a configured entry, or, for entries without a stored MAC, the MAC read by one extra `GET /json/info` of that
configured device inside the run (only configured URLs, the same size and timeout caps, at most 16 devices, counted in
`coverage.known_devices_checked`). Devices that did not answer are counted in `known_devices_unmatched`, so
`address_changed` is claimed only on a MAC match. Known devices matched by address are not read again; a stored MAC that
differs from the controller at the configured address does not block `known` (the address wins).

`address_changed`: the MAC matches configured entry X but the address differs from X's host. The candidate gets `status`
`address_changed`, `known_device_id` X and `configured_address`. The inventory is not modified by discovery, by
`wled_add_device` (which answers `INVENTORY_CONFLICT` with `conflict` `mac`) or by any other tool; the operator edits
the file. An update tool is out of scope for M8 (owner answer 5 of DEC-035).

## Coverage report

`data.coverage` is always present, also when `candidates` is empty (**TP-8**).

- `schema` 1. `conclusion`: `candidates_found`, `none_found_complete`, `none_found_incomplete` or `not_looked`.
  `complete` is a top-level boolean, true exactly when both `mdns` and `unicast` were requested and ran with status
  `completed` and no range host is `not_probed`. A method skipped for any reason (including `no_ranges_configured`),
  `partial` or `failed` makes it false. It does not depend on whether candidates were found.
- `methods[]`: `{method, requested, status, reason?}` with `method` `mdns` or `unicast`, `status` `completed`,
  `partial`, `skipped` or `failed`, and fixed `reason` codes `no_ranges_configured`, `not_requested`,
  `multicast_unavailable` (the socket cannot open or send; a container on a bridge network is the usual cause),
  `no_answers` (queries sent, nobody answered: "heard nothing" versus "could not listen"), `deadline_reached`,
  `cap_reached` and `internal_error`.
- `mdns`, only for a method that ran: `{rounds_sent, window_seconds, services_queried[], responders, answers_verified,
  answers_rejected}`. The mDNS verification target is every announced RFC 1918 IPv4 address with announced port 80;
  other answers count in `answers_rejected` and are never probed. The mDNS instance bound (64 `_wled._tcp` and 64
  `_http._tcp`) or the candidate cap makes a method `partial` with `cap_reached` and adds a `warnings` entry.
- `unicast`: `{ranges[], deadline_reached}` with, per range, `{cidr, hosts_total, hosts_probed, answered_wled,
  answered_other, refused, timed_out, not_probed}`. `/json/info` outcomes: `wled` (identity check passed), `other` (not
  WLED, redirect or non-200, oversize, malformed), `refused`, `timeout` (no usable answer, including no route). An
  unexpected transport exception counts as probed, makes the method `partial` with `internal_error` and does not stop
  the run.
- `known_devices_checked`, `known_devices_unmatched`, `proposed_ranges_omitted`, `unproposed_devices` (a list of
  `{reason, count}`), `caps` and `limits[]`: fixed English sentences (multicast stays in the local network segment and
  does not cross VLANs; a controller with an empty mDNS name does not announce itself; a probe reaches only configured
  ranges; hosts that did not answer in time are unknown, not absent).

Rule (DISC-04), evaluated in this order:

1. A requested method that could not run counts as attempted-but-`failed`. If no requested method ran at all (all
   `failed` or `skipped`, or none requested), `conclusion` is `not_looked` and `complete` is false.
2. Otherwise, with candidates found, `conclusion` is `candidates_found`.
3. Otherwise `none_found_complete` requires exactly the condition of `complete`. A run with only one method, or with
   `unicast` skipped, is never exhaustive: `none_found_incomplete` with `complete` false, and `limits` says so. A host
   that was probed and did not answer within its timeout counts as `timed_out`, is unknown and does not block
   `none_found_complete`; a host left unprobed because a deadline or cap ended the run does. Any other combination is
   `none_found_incomplete`.

`conclusion` is the first key of `data` (and in `coverage`) so a client reading only the start of the text block sees it
first (ISSUE-200-DEC-001). That a run which could not look never reports that nothing was found is an owner requirement
of 2026-11-12 (DEC-035).

## Configuration

**TP-11.** The inventory TOML gains the optional table `[discovery]` with `ranges = ["<private-network>/24"]` (0 to 4
strings). `schema_version` stays 1 (additive, like `[access]`). An unknown key gives `discovery: unsupported field`
(positional, no echo). Root keys and `[discovery]` come before the first `[[devices]]`, as for `[access]` (profiles.md),
and the writer emits them in that order. A device gains the optional `mac` (12 lowercase hex digits, no separators; a
colon-separated form is normalized when read), written by `wled_add_device`, used only to match a controller whose
address changed and never to route a request. An older build rejects the unknown keys at startup with exit code 2; a
downgrade uses the configuration kept for that version. The migration-notes rows in versioning.md for `/discovery` and
`/devices/mac` (and the rooms row `/kind`) name the release that first carried them.

## Reload semantics

**TP-10** (contract text for #201).

- Only changes made by these tools apply in-process. The reload replaces the device list and the discovery ranges and
  nothing else.
- `[access]` profile and per-device `max_class` of the loaded file must equal those of the running process, because the
  tool registry is built once. A mismatch makes the reload fail with `INVENTORY_RELOAD_FAILED` and the file is not
  replaced; changing profile or caps needs a restart (profiles.md).
- Requests running at the swap complete against the old inventory (an immutable snapshot); new requests see the new one.
  New device IDs get their lock lazily. Per-device state (catalog cache, signals) is keyed by ID and unaffected for
  unchanged entries. These tools never remove an ID.
- The writer's base is the file on disk, not the loaded snapshot: it re-reads the file under the lock and compares it
  with the content the process loaded or last wrote. If they differ (a hand edit or another process's write after
  startup), the call refuses with `INVENTORY_CONFLICT` and `data.conflict` `file_changed`, writes nothing and tells the
  operator to run `wled-mcp config validate` and restart. The same refusal applies when the `[access]` profile or a
  `max_class` in the file on disk differs from the running process (`INVENTORY_RELOAD_FAILED` when only the post-write
  reload detects it).
- Hand edits are not picked up: no file watching and no signal-triggered reload.
- The writer holds the cross-process lock, so `wled-mcp config add-device` and the tools cannot interleave. It keeps the
  previous file as a backup and fails with `STORAGE_FAILED` if the file or its directory is not writable. A read-only
  bind mount of a single file cannot be replaced atomically: mount the configuration directory, not the file.
- **Backup (TP-201-1).** One generation: `<config filename>.bak` next to the configuration, same mode, replaced by every
  successful write and by `config add-device` and `config init --force`. It is written atomically before the replace; a
  backup failure is `STORAGE_FAILED` (`data.reason` `backup_failed`) and the file is unchanged. An unchanged candidate
  writes nothing and makes no backup. The per-device preset snapshots under `<data-dir>/backups` are a separate store.
- **Lock (TP-201-2).** The sibling file `.<config filename>.lock`, never deleted, holds an OS-level exclusive lock
  (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows) plus an in-process lock. The wait is bounded (5 s); a timeout is
  `STORAGE_FAILED` with `data.reason` `locked` and the CLI's `CONFIG_LOCKED`. The OS drops the lock when its holder
  exits, so a crash leaves no stale lock.
- **Baseline and error fields (TP-201-3, TP-201-4).** The baseline of `file_changed` is the SHA-256 of the bytes loaded
  at startup, advanced by each own successful write; without a baseline every write is a conflict. `STORAGE_FAILED`
  `data.reason` is `locked`, `not_writable`, `unreadable`, `backup_failed` or `write_failed`; `INVENTORY_RELOAD_FAILED`
  `data.stage` is `validation` (candidate invalid or would drop a configured ID), `access` (profile or a `max_class`
  would change) or `reload` (apply failed after the replace; the previous bytes are restored, `unknown` if that restore
  also failed). The candidate is validated before the file is replaced. The profile is compared with the profile of the
  loaded file (a `serve --profile` option can differ from it), the caps with the running policy. Failure data is fixed
  text; it never holds a path or a file value.

## Security, transports and engine

- Result text and logs never contain secrets. stderr diagnostics name counts and codes, never the addresses of an
  installation; tool results contain candidate addresses and MACs (the product) and go to the MCP client the caller
  already trusts. Committed documentation uses generic ranges only (DEC-005).
- `wled_add_device` accepts any port on a private host, so repeated confirmed calls can tell open from closed ports
  there; acceptable under the client's confirmation of a `manage` call and limited by the single-GET, size and timeout
  bounds. The discovery probe uses port 80 only.
- Probing sends no credentials, never POSTs and never reads another path. A discovery or enrollment call is not retried
  automatically; after `STORAGE_FAILED` the file is unchanged.
- Stdio and HTTP use the same operations. mDNS from a container on a bridge network usually hears nothing
  (`multicast_unavailable` or `no_answers`); unicast probing works from a container to its routed network (DEC-035 item
  3). The write tools need a writable configuration directory.
- `wled_mcp.discovery_engine.run_discovery(methods, ranges, known, timeout, max_candidates, transport, opener, clock)`
  is the single entry point for the CLI and, through a worker thread, the tool; it reads no configuration and never
  writes. `wled_mcp.discovery_tools` reads `Resources.discovery_ranges` and the inventory per call, passes only
  configured ranges (never a proposal) and adds `proposed_ranges`, `coverage.proposed_ranges_omitted` and
  `coverage.unproposed_devices`. A process-wide guard allows one run at a time and a 5 s gap between probe-phase starts
  (only with `unicast` requested and ranges stored); a refused call is `DISCOVERY_BUSY` with `data.retry_after_seconds`
  (whole seconds, 1 to 30) and `read_retryable` true. A cancelled client call does not stop the worker before its own
  deadline (at most 30 s); the guard stays held until it ends. Evidence:
  [validation/m7-m8.md](../validation/m7-m8.md).

Related: [DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment),
[ISSUE-198-DEC-001](../decisions/m7-m8.md), [cli.md](cli.md), [profiles.md](profiles.md),
[DEPLOYMENT.md](../DEPLOYMENT.md).
