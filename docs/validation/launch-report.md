# Launch report: published release 0.3.0

Evidence for [#25](https://github.com/descipar/wled-mcp/issues/25) (S2-LAUNCH-01, S2-LAUNCH-02,
acceptance items 2 to 4 of the issue body; the live rollback is item 1 and is **not** part of this
report). Decisions: [ISSUE-25-DEC-001, -002 and -003](../decisions/issue-25.md).

**Target.** This report covers the published release **v0.3.0** (PyPI, GitHub release and MCP
Registry). The work of milestones M3 to M6 is merged on `main` but **unreleased**
([CHANGELOG](../../CHANGELOG.md#unreleased): 37 tools against the 33 of 0.3.0). The upgrade and
rollback evidence for the next minor release is pending the owner's release and rollback
authorization; nothing in this report claims it. Nothing was published, tagged, released,
submitted or deployed by this work, and the deployed service was not touched.

Environment of all new runs: macOS 27.2.1 (arm64), uv 0.11.7, Python 3.13.2, MCP SDK client
`mcp` 2.3.0 (resolved with the package), run on 2026-11-13 between 09:30 and 09:40 UTC from empty
scratch directories outside the repository, with `GH_TOKEN` and `GITHUB_TOKEN` unset (no GitHub
credentials) and Python run with `-I` for every script. The scripts live in the session scratch
area and are not part of the repository.

## 1. Clean install from PyPI

| Check | Result |
| --- | --- |
| `uvx --isolated --no-cache --python 3.13 --from wled-mcp==0.3.0 wled-mcp --version` with a fresh, empty uv cache directory | downloads and installs 29 packages, prints `wled-mcp 0.3.0`, exit 0 |
| Installed metadata (`python -I`, same environment) | `wled-mcp` 0.3.0, `mcp` 2.3.0, Python 3.13.2 |
| `wled-mcp --help` | stdio default; `--transport streamable-http`, `--profile`, `--allowed-host`, `--http-token-file` listed |

This repeats the install check of [release-m2.md](release-m2.md#release-and-registry-publication-2026-11-11)
from a clean cache (`--no-cache`, empty cache directory). It does not
cover Linux, Windows or any Python other than 3.13 (the package requires `>=3.13,<3.14`).

## 2. Interoperability, one run per transport

The package under test is the one from PyPI (`uvx --isolated --from wled-mcp==0.3.0`), started by
the client for stdio and as a separate process for HTTP. The client is the real SDK client (`Client`
with `StdioServerParameters` and with `streamable_http_client`, protocol mode `legacy`). The
inventory is synthetic: one device whose `base_url` points to a throw-away loopback server that
answers only `GET /json/info` and `GET /json/state` and refuses `POST` (no LAN device involved).

| Check | stdio | Streamable HTTP |
| --- | --- | --- |
| `initialize`, `tools/list` | ok, 33 tools | ok, 33 tools |
| `wled_list_devices` with `probe` | `ok` | `ok` |
| `wled_get_state` of the synthetic device | `ok`, `application` not attempted | same |
| `wled_get_service_status` | `ok` | `ok` |
| Request without credential (HTTP only) | not applicable | HTTP 401 |

The loopback server saw 6 `GET` requests (`/json/info`, `/json/state`) and 0 `POST`. The HTTP
service ran with `--host 127.0.0.1`, an explicit `--allowed-host` and a token file, as in
[DEPLOYMENT.md](../DEPLOYMENT.md#streamable-http-service-configuration). Not covered: any other
MCP client (MCPHub, Claude Desktop), TLS, a non-loopback bind, a write tool, and the 2026-07-28
per-request protocol path. The same two transports are exercised against the source tree on every
CI run by `tests/test_acceptance_parity.py`.

The authenticated `ping` snippet of DEPLOYMENT.md was also run once against this local service
(Host `wled-mcp:<port>`, token read from the file): HTTP 200 and `{"jsonrpc":"2.0","id":1,"result":{}}`.

## 3. Upgrade and rollback evidence

Existing evidence is linked, not repeated.

- **Live updates of the deployed HTTP service:** to a newer build in the second #12 run
  ([VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06)) and to the
  second release in [live-check-2026-11-08.md](live-check-2026-11-08.md); the service ran release
  0.1.2 on 2026-11-11 ([issue-25.md](issue-25.md)) and runs 0.3.0 now (read-only observation below).
- **Retained data, newer code reads older data:** `tests/test_upgrade_compat.py`
  ([issue-21.md](issue-21.md), [versioning](../contract/versioning.md#upgrade-downgrade-and-rollback)).
- **New in this report, published releases, local synthetic run (not the deployed service):** one
  inventory and one data directory were used by three stdio sessions in turn: release 0.2.0 saved a
  group and a scene; release 0.3.0 listed both (upgrade read), read a state and saved a second
  group and scene; release 0.2.0 again (rollback) started on the same files, listed the device,
  read a state and listed **both** groups and **both** scenes, including those written by 0.3.0.
  The files were byte-identical before and after the rollback session's reads (SHA-256 prefixes
  compared) and the loopback controller received 0 `POST`. `config validate` and `doctor`
  exist and run on 0.1.2, 0.2.0 and 0.3.0, so the checks of the rollback procedure are available
  on every candidate rollback target. This closes, for groups and scenes, the gap that
  [versioning.md](../contract/versioning.md#upgrade-downgrade-and-rollback) states ("an older
  server reading newer data is not run"). It says nothing about presets snapshots (no device
  write was made in that run), and 0.3.0 changed no data format, so it does not predict a release
  that changes one.
- **Live rollback on the deployed target:** **not run in this PR.** Authorizations relayed from
  the owner on 2026-11-13 are recorded in [ISSUE-25-DEC-003](../decisions/issue-25.md): restart and
  rollback of the deployed service and changes to the wled-mcp entry on the hub, with a hub-entry
  backup first and restoration afterwards. The first attempt had no access path (the hub's MCP
  endpoint refused the connection); after the owner reconnected it, only **read-only** inspection was
  done through the hub's SSH tool and the hub's service-status tool: the deployed service runs
  release 0.3.0 (service uptime about 1.9 h at 09:5x UTC, access profile `full`, one configured
  device, `unknown` readiness and 0 calls since start, backups writable). The target keeps the
  staged release directories of 0.3.0 and **0.1.2**, but only the image `wled-mcp:0.3.0`; the
  image of 0.1.2 was removed and release 0.2.0 was never staged. A rollback therefore means
  rebuilding the 0.1.2 image from its retained, checksummed directory (the documented path), which
  jumps two releases, or staging 0.2.0 on the target first. The owner then chose to roll back to 0.2.0
  (staged on the target first; the hub itself is never reinstalled, [DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).
  The run could not start: on the next attempt (2026-11-13, later the same day) every call through the
  hub's SSH and service-status tools failed with a name-resolution error for the target host
  (`getaddrinfo ENOTFOUND`) although both had answered shortly before, so the target is unreachable
  from this session now and no further read, staging or restart was possible. The hub entry was not
  touched (the owner has not answered whether it may be changed). Nothing was
  changed, restarted or built. Issue item 1 stays open; the prepared checklist is
  [issue-25-rollback-plan.md](issue-25-rollback-plan.md). No MCPHub fresh-install test was run; the
  waiver (ISSUE-24-DEC-005) stands.
- **Pending for the next minor release:** upgrade of the deployed service from 0.3.0 and the
  rollback after that release, on the owner's release and rollback authorization.

## 4. Hardware and firmware observations

All hardware evidence was recorded on **one controller: WLED 16.0.1 (build 2606300), ESP32-C3, 133
LEDs, one RGB segment**; no other controller, firmware version, RGBW, CCT, 2D or multi-bus setup
was ever observed. CI fixtures are not field testing. The table lists what ran on hardware, with the
release or build it ran on; everything else is mock or loopback evidence only.

| Evidence | Release or build | What ran on the controller |
| --- | --- | --- |
| [Issue #11 live deployment check](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06), [#12 runs 1 to 3](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06) | 0.1.x builds | HTTP and stdio via the hub: device facts, reads, load, drain, master state, one effect, segments and layout, presets in slot 250, visible effect, speed and brightness transition |
| [Live check of the second release](live-check-2026-11-08.md) | second release | reads, master power and brightness, a 60 s effect run |
| [#134](issue-134.md) | 0.1.1 on the hub | group and scene, preset store, export, import, restore, one playlist, all restored |
| [#128](issue-128.md) | 0.3.0 source tree, stdio | five reads and a minimal write set under settings PIN, OTA lock and both |
| [#150](issue-150.md) | candidate of #150 | one live snapshot call: endpoint unavailable (HTTP 501); no positive snapshot observed |
| [#30](issue-30.md) | `main` at PR #175 | one read-only explanation call |
| [#28](issue-28.md) | candidate of #28, **unreleased** | temporary signal start, expiry restore, cancel with conflict; stdio only |
| [#25 H07](issue-25.md) | deployed 0.1.2 | offline entry on a non-routed address: that entry failed alone, the real controller was unaffected |
| **This report, section 4a** | **0.3.0 from PyPI, stdio** | two reads, two writes with restoration (below) |

Mock or loopback evidence only (no hardware run): named zones (#27) and the layout preview (#29,
both unreleased), effect and palette names in segment writes (#149), served guidance (#147),
multi-device scenes, tool profiles on hardware, CCT, RGBW and 2D, restore onto an occupied slot,
playlist import, restoring a playlist preset, a positive live snapshot, discovery and enrollment
(unreleased, milestone M8 is not merged), the MCPB bundle and reboot or power-cycle persistence. The
README and [VALIDATION.md](../VALIDATION.md#known-limitations) state the same limits.

### 4a. Published 0.3.0 on the selected test controller (2026-11-13)

Authorized by [ISSUE-25-DEC-002](../decisions/issue-25.md) (scope of this issue only). The
controller is not named here. The local inventory file named in the owner's reference was not
present in this worktree, so a scratch inventory outside the repository was used with the address
from that reference; a read-only `GET /json/info` first confirmed firmware 16.0.1 (build 2606300),
ESP32-C3 and 133 LEDs, matching the controller described there. Package: `uvx --isolated --python
3.13 --from wled-mcp==0.3.0`, stdio, access profile `full`, fresh data directory.

1. **Restorable state first.** Read-only copies of `GET /json/state` and `GET /presets.json`, kept in
   the scratch area. Baseline: master off, brightness 47, no preset or playlist, segment 0 speed 128,
   effect 0. The script was written to stop if this baseline was not met.
2. **Calls** (everything else was blocked by the plan): `wled_get_state`, `wled_list_presets`;
   `wled_set_state` brightness 60 as dry run, then applied, then 47 again; `wled_patch_segments`
   speed 100 on segment 0 as dry run, then applied, then 128 again. Every write returned
   `applied` / `verified`; none failed and none was retried. The master stayed off, so no light was
   emitted.
3. **Restoration proof.** A raw readback after the run: `on`, `bri`, `transition`, `ps`, `pl`,
   `mainseg` and, per segment, `start`, `stop`, `on`, `bri`, `col`, `fx`, `sx`, `ix`, `pal` equal the
   baseline copy; `/presets.json` is identical to the baseline copy. No snapshot file was created
   (no preset write).

This shows that the published artifact reads and writes a real WLED 16.0.1 controller over stdio
with readback verification. It does not repeat the broader #12 and #134 scope, uses no HTTP
transport and no hub.

## 5. External routes, verified from outside the project

Checked on 2026-11-13 around 09:33 UTC with unauthenticated `GET` requests to public endpoints
(no credentials; not read through the project's tooling).

| Route | Observation |
| --- | --- |
| PyPI `wled-mcp` | releases 0.1.2, 0.2.0, 0.3.0; 0.3.0 serves `wled_mcp-0.3.0-py3-none-any.whl` (SHA-256 `84050ec2...6218f`) and `wled_mcp-0.3.0.tar.gz` (`d1cc52e6...ac4`), equal to the values recorded in [release-m2.md](release-m2.md); neither file yanked; `requires_python` `<3.14,>=3.13`; the description carries `mcp-name: io.github.descipar/wled-mcp`; project page answers 200 |
| MCP Registry | `GET /v0.1/servers?search=io.github.descipar/wled-mcp` returns 0.2.0 (active, not latest) and 0.3.0 (active, latest, published 2026-11-11T10:02:17Z); one `pypi` package each, no `remotes` |
| GitHub | repository public, license Apache-2.0; releases v0.1.0 to v0.3.0 published (none draft or prerelease); tag `v0.3.0` is an annotated tag that resolves to commit `64615a89d83d96f8ed4643f7c3419899f1fdbac0`, the commit recorded in release-m2.md; the v0.3.0 release has no attached assets (the MCPB bundle is built from the next release on) |
| Container image | **not published** ([#156](https://github.com/descipar/wled-mcp/issues/156), open, Backlog); HTTP deployments build the image locally from the staged release directory |
| MCPHub fresh install | **waived** by the owner ([ISSUE-24-DEC-005](../decisions/issue-24.md)); the registry-tab finding is in [issue-24.md](issue-24.md#mcphub-registry-tab-observed-install-dialog-2026-11-10) |

No other listing exists or is planned ([ISSUE-24-DEC-003](../decisions/issue-24.md)).

## 6. Unresolved defects and limits

Open Backlog issues on 2026-11-13, none a blocker for the published release: #223
(redaction of caller arguments in error messages), #222 (interface selection for bounded mDNS
discovery), #220 (local storage hardening against concurrent directory replacement), #217 and #216
(test guard for network access), #215 and #214 (probe script redaction and file mode), #213
(distribution check with a space in the checkout path, Windows), #190 (layout preview note), #180
(#30 follow-ups), #162 (documentation-only CI gate), #156 (container image), #138 (snapshot delete
tool), #117 (bundle import planning bound). Six Dependabot pull requests (#224 to #229) are open.
Known behavior limits are in [VALIDATION.md](../VALIDATION.md#known-limitations): no device
authentication, one writer per controller, stdio host stops do not drain, preset operations on WLED
16 affect the live output, four snapshots of #134 remain on the deployed service's data directory.
The bounded source review is in [issue-181.md](issue-181.md) and is not an audit.

## 7. Maintenance scope

Best effort, no commitment to answer, review or merge ([CONTRIBUTING](../../CONTRIBUTING.md), [README
support](../../README.md#support)); no security support ([SECURITY.md](../../SECURITY.md), DEC-013);
fixes for the latest release only ([CHANGELOG](../../CHANGELOG.md)); "supported" means covered by the
checks of the [compatibility matrix](../contract/compatibility.md), nothing more. WLED 16.0.0 and
later is the target, 16.0.1 is the only tested firmware, 0.x releases of the project may carry
breaking changes with migration notes.

## 8. Tests not run

- The full test suite, linters and the distribution check were not re-run for this report; the CI
  of the release commit is the evidence ([release-m2.md](release-m2.md)). This change is
  documentation only.
- Linux, Windows and Python versions other than 3.13 for the clean install of 0.3.0.
- Any client other than the SDK client; MCPHub (waived), Claude Desktop and the MCPB bundle
  (unreleased, never installed by the project), HTTP over TLS or a non-loopback bind.
- The live rollback and any restart of the deployed service (item 1 of the issue); upgrade and
  rollback of the next minor release.
- Hardware: any controller, firmware or capability other than the one above; reboot and
  power-cycle persistence; the items listed as mock-only in section 4; the HTTP transport on
  hardware with the published package (the deployed service runs 0.3.0 per the read-only observation of 2026-11-13; its last recorded hardware use was on 0.1.2).
- Preset snapshots read by an older release after a newer release wrote them (groups and scenes
  only were tested in section 3).
- No load, soak or fuzz testing of the published package.
