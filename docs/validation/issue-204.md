# Issue #204 validation: M8 documentation, live runs and release preparation

Requirements: DISC-14 (evidence and release preparation), DISC-T08 (live part: the discovery
half is open here; the single enrollment was met in
[issue-203.md](issue-203.md#live-enrollment-2026-11-19-two-attempts)), DISC-05 (hard caps),
DISC-01 (no implicit discovery), DISC-12 (stdio and HTTP share the code). Contract:
[contract/discovery.md](../contract/discovery.md). Decisions:
[DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment),
[DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release),
DEC-028 (pragmatic delivery).

Status of this record: **the documentation is done; every live run below is pending owner
authorization and none has been run.** Nothing here was contacted, written or deployed. The
three M8 tools (#200, #202, #203) are merged with mocked evidence, the enrollment ran live once
(#203), the discovery in stdio ran live partially (#200, mDNS only); the unicast probe and the
container deployment have no live evidence yet.

## Acceptance table

| Deployment mode | Criterion | Status |
| --- | --- | --- |
| stdio on the host | Read-only discovery run: mDNS plus unicast of a configured range, inventory unchanged, nothing written to a device (DISC-14, DISC-T08) | pending owner authorization (mDNS half: partial evidence in [issue-200.md](issue-200.md)) |
| HTTP in a container | Read-only discovery run from the container: mDNS reported honestly, unicast reach of a configured /24 proved (DISC-14, DISC-T08) | pending owner authorization |
| HTTP in a container | The case where mDNS finds nothing and the unicast probe does (DISC-14) | pending owner authorization |
| Both | Single enrollment on the test controller that changes only the inventory | met over stdio ([issue-203.md](issue-203.md)); not repeated in the container, by design of DISC-14 (one enrollment) |
| Docs | README, deployment guide, quickstart, tool contract, coverage, migration notes, changelog describe M8 accurately and mark it "not yet released" | done in this change |

Until the pending rows are run, the README and the deployment guide state that container
discovery is mock-covered only. Mocked evidence for the engine, tools and writer is listed in
[issue-200.md](issue-200.md), [issue-203.md](issue-203.md) and DISC-T01 to DISC-T07 of the
contract.

## Common rules for all live runs

Each run needs its own explicit owner authorization naming the run, the selected test
controller and the number of calls (including a repeat after a failure); an authorization is
used once and expires (the #200 and #203 records are the precedent).

- Target: the selected test controller, addressed only by its inventory host name, resolved at
  run time (one DNS lookup, an RFC 1918 IPv4 result). Do not reuse a remembered address. No IP,
  MAC or private host name is written to any file, issue or PR; output that enters
  `docs/validation/` contains counts and statuses only (DEC-005,
  `scripts/check_private_identifiers.py`).
- Inventory: a temporary inventory outside git (at least `schema_version = 1` and `devices = []`,
  or one device entry for the selected controller); the real local-only inventory is never passed
  to the server. Record its hash before and after: it must be unchanged by every discovery run
  (discovery writes nothing). `wled_set_discovery_ranges` is not called in a read-only run;
  the range is set by writing the `[discovery]` table into the temporary file before the server
  starts (the hand-edit path of the contract), so that no tool writes.
- Reach, stated so the authorization is informed:
  - mDNS: up to 3 query rounds in a 6 s window; **every announced private host** on port 80
    receives one read-only `GET /json/info` (other WLED controllers on the LAN may appear as
    `new` candidates, as in the #200 run).
  - Unicast: one read-only `GET /json/info` to port 80 of each host of each configured
    RFC 1918 range, at most a /24 per range (up to 254 hosts), at most 4 ranges, with the hard
    caps of [contract/discovery.md](../contract/discovery.md#hard-caps) (1.5 s per host, at most 32
    sockets in flight, probe deadline 20 s, call deadline 30 s, response at most 64 KiB, no
    redirects, GET only).
  - Nothing is written to any device; no inventory change; no other tool than `tools/list` and
    `wled_discover_devices` is called.
- Bounds: single flight (`DISCOVERY_BUSY` for a concurrent call), a 5 s gap between probe-phase
  starts, call logs and stderr free of addresses, MACs and ranges (expected stderr: empty or
  fixed lines only). A failed call is recorded and not repeated blindly.
- Offline checks first: `uv run --frozen pytest tests/test_discovery_tools.py
  tests/test_tool_contract.py tests/test_access_profiles.py tests/test_tool_budget.py`.
- Build from the merged head of `main` (or the release candidate commit) and record its SHA.

## Run 1: stdio on the host

Purpose: prove the unicast probe over stdio on the host, in addition to the partial mDNS
evidence of #200.

1. Temporary inventory with one device (the selected controller, `base_url` the resolved
   IPv4 literal so that it can be `known`) and `[discovery] ranges = ["<its /24>"]` computed
   at run time from the resolved address; nothing else.
2. Start the server over stdio on the host (as `scripts/hw_read_only_probe.py` does). Call
   `tools/list`, then `wled_discover_devices` with `{}` once.
3. Expected: `ok` true; mDNS `completed` (or an honest `no_answers` or
   `multicast_unavailable`); unicast `completed` with the configured range and
   every host of the range probed (its size minus network and broadcast addresses), no
   `deadline_reached`; the selected controller listed as `known` (matched by address or MAC)
   and found by `unicast`; `complete` true and a conclusion of `candidates_found`; `caps` equal
   to the documented numbers.
4. Verify: inventory hash unchanged, no `.bak` or lock file, stderr free of address, MAC and
   range, no write request to any device.
5. Record counts and statuses only; delete the scratch output.

## Run 2: HTTP in a container

Purpose: prove that discovery works over Streamable HTTP in the container and measure what the
container sees.

Facts for the run: the container runs on Docker Desktop on macOS with the default bridge
network, so containers live in a virtual machine and a container on the bridge normally sees no
mDNS. The image is built from the HTTP Dockerfile as described in
[DEPLOYMENT.md](../DEPLOYMENT.md) (clean checkout of the commit, built on the machine that
runs it, DEC-026); the HTTP service needs its own credential and Host/Origin allowlist as
documented. The temporary inventory directory is mounted writable as a directory (read-only in
this run is also acceptable, because no tool writes). What is to be proved is the unicast reach of a
configured /24 from the container, not that mDNS works.

1. Same temporary inventory as run 1, mounted for the container; a temporary bearer credential
   file outside git. Bring the service up in a project of its own; do not touch the deployed
   `wled-mcp-http` service.
2. Authenticated `tools/list`, then one `wled_discover_devices` call with `{}`.
3. Expected: `ok` true; mDNS reported honestly (`no_answers` or `multicast_unavailable` is the
   expected outcome; any other result is recorded as observed); unicast `completed` for the
   configured range with the controller found; no claim of `none_found_complete` when a method
   could not look; the same envelope as over stdio.
4. Verify as in run 1, plus: container logs free of address, MAC, range and credential.
5. Tear down the temporary service, credential and inventory; record the image reference
   (commit) and the Docker Desktop version class only.

If the container cannot reach the LAN range, the result is recorded as `no reach from the
container`, together with the coverage the tool reported; that is a finding about the
network, not a pass.

## Run 3: mDNS finds nothing, unicast does

Purpose: DISC-14's required case. It is the same container run, evaluated against a stricter
expectation, and can be one call sequence with run 2 if the owner authorizes both.

1. In the container of run 2, call `wled_discover_devices` with `{"methods": ["mdns"]}`:
   expected a completed mDNS phase with no candidates and a conclusion of
   `none_found_incomplete` (never `none_found_complete`), because unicast did not run.
   Wait at least 5 s only if a probe phase ran before; an mDNS-only call has no gap.
2. Then call `{"methods": ["unicast"]}` with the range that contains the selected controller:
   expected the controller found by `unicast` with `known` or `new`, conclusion
   `candidates_found`, `complete` as the coverage states.
3. Pass criterion: mDNS found nothing (or only what the container could see, recorded) and the
   unicast call found the test controller; otherwise record which part failed.
4. Verify and clean up as in run 2. One extra request count: step 1 makes the mDNS verification
   reads for every announced host (none expected in the container); step 2 is the unicast reach
   of run 2.

## Release preparation

All items are owner-gated. None is done by this change; the version in `pyproject.toml`, the
changelog sections and tags are untouched (the README says "not yet released" until a release
exists).

Scope of the minor release (0.5.0 is provisional, DEC-030): M8 (#198 to #204) plus the other
unreleased work that earlier waivers push into the next minor release (M7 rooms, #183,
DEC-038; the M3 and M4 waivers DEC-032 and DEC-034 are noted in the changelog and ROADMAP,
which say whether that work already shipped). The exact set is whatever the Unreleased
section of [CHANGELOG.md](../../CHANGELOG.md) holds at the release commit.

Checklist, each step only on the owner's explicit instruction:

- [ ] Live runs 1 to 3 above recorded in this file with the actual outcomes, or the owner
  explicitly accepts the release without them (then the acceptance table says so).
- [ ] Merge state: all of #198 to #204 merged, CI green on the release commit, README and
  deployment guide re-read for "not yet released" wording that the release makes obsolete.
- [ ] Choose the release number (0.5.0 provisional) and correct the provisional release
  number in the migration-notes rows (`/kind`, `/devices/mac`, `/discovery`) and in
  contract/discovery.md if it differs.
- [ ] CHANGELOG: turn Unreleased into a dated section; no empty Unreleased claims.
- [ ] Version bump in `pyproject.toml` and the lock; the version-source test
  (`tests/test_version_source.py`) and `tests/test_upgrade_compat.py` pass.
- [ ] Tag, GitHub release with the MCPB bundle.
- [ ] PyPI upload and official MCP Registry publication, as for earlier releases
  ([PUBLISHING.md](../PUBLISHING.md)).
- [ ] README updated for the released state (the "not yet released" markers removed), as
  DEC-030 requires, and the milestone M8 row of [ROADMAP.md](../ROADMAP.md) updated.
- [ ] Staging and deployment of the released version on the owner's machine stays a separate
  owner-gated step ([DEPLOYMENT.md](../DEPLOYMENT.md), DEC-026).

## Known limits

- Docs only: no code, test or network activity in this change.
- A /24 unicast run sends up to 254 read-only requests to LAN hosts; the owner authorization
  must say so.
- Docker Desktop on macOS is one environment; a Linux host with a bridge network or
  `network_mode: host` can behave differently and is not covered.
- The server's mDNS verification reaches every announced private host (see the #200 record);
  a run limited to one device is not possible with the current tool.
