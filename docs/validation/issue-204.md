# Issue #204 validation: M8 documentation, live runs and release preparation

Requirements: DISC-14 (evidence and release preparation), DISC-T08 (live part: the discovery half
here; the single enrollment was met in
[issue-203.md](issue-203.md#live-enrollment-2026-11-19-two-attempts)), DISC-05 (hard caps), DISC-01
(no implicit discovery), DISC-12 (stdio and HTTP share the code). Contract:
[contract/discovery.md](../contract/discovery.md). Decisions:
[DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment),
[DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release), DEC-028.

Status: **the documentation is done and the three live discovery runs ran once on 2026-11-20**
([results](#live-runs-2026-11-20)). All passed their main criterion; the stricter variants of run 3
were not run. Nothing was written to any device and no inventory changed. The release preparation is
open and owner-gated.

## Acceptance table

| Deployment mode | Criterion | Status |
| --- | --- | --- |
| stdio on the host | Read-only discovery run: mDNS plus unicast of a configured range, inventory unchanged, nothing written to a device (DISC-14, DISC-T08) | met 2026-11-20 ([run 1](#run-1-result)); earlier partial mDNS evidence in [issue-200.md](issue-200.md) |
| HTTP in a container | Read-only discovery run from the container: mDNS reported honestly, unicast reach of a configured /24 proved (DISC-14, DISC-T08) | met 2026-11-20 ([run 2](#run-2-and-3-result)) |
| HTTP in a container | The case where mDNS finds nothing and the unicast probe does (DISC-14) | met 2026-11-20 by the same call ([run 3](#run-2-and-3-result)); the mDNS-only and unicast-only variants were not run |
| Both | Single enrollment on the test controller that changes only the inventory | met over stdio ([issue-203.md](issue-203.md)); not repeated in the container, by design of DISC-14 |
| Docs | README, deployment guide, quickstart, tool contract, coverage, migration notes, changelog describe M8 accurately and mark it "not yet released" | done in this change |

Mocked evidence for engine, tools and writer: [issue-200.md](issue-200.md),
[issue-203.md](issue-203.md) and DISC-T01 to DISC-T07 of the contract.

## Common rules for all live runs

Each run needs its own explicit owner authorization naming the run, the selected test controller and
the number of calls; it is used once and expires.

- Target addressed only by its inventory host name resolved at run time; no IP, MAC or private host
  name is written to any file, issue or PR (DEC-005, `scripts/check_private_identifiers.py`).
- A temporary inventory outside git (`schema_version = 1`, `devices = []` or the one selected
  controller) with the range in a hand-written `[discovery]` table, so no tool writes; hash recorded
  before and after, unchanged.
- Reach: mDNS up to 3 rounds in a 6 s window, one read-only `GET /json/info` to every announced
  private host on port 80; unicast one `GET /json/info` per host of each configured RFC 1918 range
  (at most /24, at most 4 ranges) under the [hard caps](../contract/discovery.md#hard-caps). No device
  write, no inventory change; only `tools/list` and `wled_discover_devices` are called.
- Single flight, stderr and logs free of addresses, MACs and ranges; a failed call is recorded, not
  repeated blindly. Offline checks first (`tests/test_discovery_tools.py`, `test_tool_contract.py`,
  `test_access_profiles.py`, `test_tool_budget.py`); build from the merged head of `main`.

Run 1 (stdio on the host) calls `wled_discover_devices` with `{}` once. Run 2 (HTTP in a container on
Docker Desktop, default bridge network, own project, own credential, deployed service untouched) does
the same and proves unicast reach of the /24, not mDNS. Run 3 is the same container evaluated
against the case "mDNS finds nothing, unicast does" (optionally with `methods` limited to `mdns`
then `unicast`). A container that cannot reach the range is recorded as `no reach from the
container`, a network finding, not a pass.

## Live runs (2026-11-20)

Authorization: [ISSUE-204-DEC-001](../decisions/issue-204.md), one run per row, used once and
expired. Build: merged head of `main` (`950e113`), clean checkout; the container image was staged
with `deploy/stage_release.py --non-release`, built locally and removed. Temporary inventory with
the selected controller and its /24 as the one range; access profile `read-only`; both runs listed
20 tools. Counts and statuses only.

### Run 1 result

stdio on the host, one `wled_discover_devices` call with `{}` (covers mDNS and the range). `ok` true,
17.6 s.

- mDNS `completed`: 3 rounds, 13 responders, 2 answers verified, 9 rejected.
- Unicast `completed`: 254 of 254 hosts probed, deadline not reached; 2 answered as WLED, 44 as
  something else, 21 refused, 187 timed out.
- 2 candidates, both found by mDNS and unicast: the selected controller `known` and a second WLED
  controller of the same /24 as `new`. `complete` true, `candidates_found`, `caps` as documented.
- Inventory hash unchanged, no backup or lock file, stderr 0 bytes, no write tool served.

### Run 2 and 3 result

HTTP in a container (Docker Desktop 29, default bridge), one authenticated call with `{}`. `ok` true,
16.6 s.

- mDNS `completed` with `no_answers`: 3 rounds, 0 responders.
- Unicast `completed`: 254 of 254 probed; 2 answered as WLED, 44 as something else, 23 refused, 185
  timed out. The same 2 candidates, found by unicast only; selected controller `known`.
- `complete` true, `candidates_found`, same envelope shape as over stdio. The container reached the
  LAN range although mDNS saw nothing (the DISC-14 case); a finding for this Docker Desktop setup only.
- Container log 221 bytes (listen line, a warning that the backups location was read-only); no
  address, MAC, range or credential. Inventory hash unchanged; everything removed afterwards.

Not run, by design of the authorization: the mDNS-only call showing `none_found_incomplete` in the
container and the unicast-only call (the envelope rule is covered by mocks only). Run 1 also reached
the second controller of the same /24 through the range scan, as stated; a run limited to one device
is impossible with the current tool ([#265](https://github.com/descipar/wled-mcp/issues/265)).

## Release preparation

All items are owner-gated and none is done by this change; version, changelog sections and tags are
untouched (README says "not yet released" until a release exists).

Scope of the minor release (0.5.0 is provisional, DEC-030): M8 (#198 to #204) plus other unreleased
work (M7 rooms #183, DEC-038; M3/M4 waivers DEC-032, DEC-034), i.e. whatever the Unreleased section
of [CHANGELOG.md](../../CHANGELOG.md) holds at the release commit.

- [x] Live runs 1 to 3 recorded with the actual outcomes (2026-11-20).
- [ ] Merge state: #198 to #204 merged, CI green on the release commit, README and deployment guide
  re-read for obsolete "not yet released" wording.
- [ ] Choose the release number and fix the provisional number in the migration-notes rows
  (`/kind`, `/devices/mac`, `/discovery`) and contract/discovery.md.
- [ ] CHANGELOG: Unreleased becomes a dated section.
- [ ] Version bump in `pyproject.toml` and the lock; `tests/test_version_source.py` and
  `tests/test_upgrade_compat.py` pass.
- [ ] Tag, GitHub release with the MCPB bundle.
- [ ] PyPI upload and official MCP Registry publication ([PUBLISHING.md](../PUBLISHING.md)).
- [ ] README updated for the released state (DEC-030) and the M8 row of [ROADMAP.md](../ROADMAP.md).
- [ ] Staging and deployment on the owner's machine stays a separate owner-gated step
  ([DEPLOYMENT.md](../DEPLOYMENT.md), DEC-026).

## Known limits

One run each, one network, one Docker Desktop version class, not a matrix. A /24 unicast run sends up
to 254 read-only requests to LAN hosts (the authorization must say so). A Linux host with a bridge or
`network_mode: host` can behave differently and is not covered. The mDNS verification reaches every
announced private host, so a run limited to one device is not possible.
