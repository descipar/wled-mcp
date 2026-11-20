# Launch report: published release 0.3.0

Evidence for [#25](https://github.com/descipar/wled-mcp/issues/25) (S2-LAUNCH-01, S2-LAUNCH-02,
acceptance items 2 to 4, and the live rollback of item 1 in section 3). Decisions:
[ISSUE-25-DEC-001, -002 and -003](../decisions/issue-25.md).

**Target.** Published release **v0.3.0** (PyPI, GitHub release, MCP Registry, 33 tools). M3 to M6 work
is merged but unreleased ([CHANGELOG](../../CHANGELOG.md#unreleased), 37 tools). Release 0.4.0 was
published and deployed later the same day ([deploy-0.4.0.md](deploy-0.4.0.md)); its rollback was not
run. Nothing was published, tagged, released or submitted by this work; the deployed service was
restarted twice for the one authorized rollback 0.3.0 to 0.2.0 and back.

Environment of the new runs (2026-11-13, empty scratch directories, no GitHub credentials, `python -I`):
macOS 27.2.1 arm64, uv 0.11.7, Python 3.13.2, `mcp` 2.3.0. Scripts are not part of the repository.

## 1. Clean install from PyPI

| Check | Result |
| --- | --- |
| `uvx --isolated --no-cache --python 3.13 --from wled-mcp==0.3.0 wled-mcp --version`, empty cache | installs 29 packages, prints `wled-mcp 0.3.0`, exit 0 |
| Installed metadata | `wled-mcp` 0.3.0, `mcp` 2.3.0, Python 3.13.2 |
| `wled-mcp --help` | stdio default; `--transport streamable-http`, `--profile`, `--allowed-host`, `--http-token-file` listed |

Repeats [release-m2.md](release-m2.md#release-and-registry-publication-2026-11-11) from a clean
cache. Not covered: Linux, Windows, Python other than 3.13 (package requires `>=3.13,<3.14`).

## 2. Interoperability, one run per transport

PyPI package, real SDK client (legacy protocol mode), one synthetic device on a loopback server that
answers only `GET /json/info` and `/json/state` and refuses `POST`. HTTP service on `127.0.0.1`
with an explicit `--allowed-host` and token file ([DEPLOYMENT.md](../DEPLOYMENT.md#streamable-http-service-configuration)).

| Check | stdio | Streamable HTTP |
| --- | --- | --- |
| `initialize`, `tools/list` | ok, 33 tools | ok, 33 tools |
| `wled_list_devices` with `probe` | `ok` | `ok` |
| `wled_get_state` | `ok`, `application` not attempted | same |
| `wled_get_service_status` | `ok` | `ok` |
| Request without credential | not applicable | HTTP 401 |

The loopback server saw 6 `GET` and 0 `POST`. The authenticated `ping` snippet of DEPLOYMENT.md
returned HTTP 200 with an empty result. Not covered: other MCP clients (MCPHub, Claude Desktop),
TLS, non-loopback bind, a write tool, the 2026-07-28 per-request protocol path. CI exercises both
transports on every run (`tests/test_acceptance_parity.py`).

## 3. Upgrade and rollback evidence

- **Live updates of the deployed HTTP service:** second #12 run
  ([VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06)), the second
  release in [live-check-2026-11-08.md](live-check-2026-11-08.md), 0.1.2 ([issue-25.md](issue-25.md)),
  0.3.0 (read-only observation), 0.4.0 ([deploy-0.4.0.md](deploy-0.4.0.md)).
- **Retained data, newer code reads older data:** `tests/test_upgrade_compat.py`
  ([issue-21.md](issue-21.md), [versioning](../contract/versioning.md#upgrade-downgrade-and-rollback)).
- **Published releases, local synthetic run:** three stdio sessions on one inventory and data
  directory: 0.2.0 saved a group and a scene, 0.3.0 listed both and saved a second pair, 0.2.0 again
  listed both groups and both scenes. Files byte-identical across the rollback session's reads; 0
  `POST`. `config validate` and `doctor` exist on 0.1.2, 0.2.0 and 0.3.0. This closes, for groups and
  scenes only, the "older server reading newer data" gap of versioning.md; presets snapshots were not
  covered and 0.3.0 changed no data format.
- **Live rollback on the deployed target, run once on 2026-11-13 (S2-COMPAT-03, live part).**
  Authority: [ISSUE-25-DEC-003](../decisions/issue-25.md) (this issue only); the hub itself is never
  reinstalled ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).
  - Before: HTTP service on image `wled-mcp:0.3.0`, healthy, profile `full`, one device. The 0.2.0
    release was not staged and had to be staged first.
  - Backups: `compose.yaml`, the whole data directory (archive plus SHA-256 list of 9 files, needs
    root) and the hub settings file.
  - Staging 0.2.0 on the target (DEC-026): clean clone of tag `v0.2.0`, `uv sync --locked`,
    `check_distribution.py` PASS (aarch64, Python 3.13.5), `deploy/stage_release.py`,
    `sha256sum -c` OK. The staged wheel is byte-identical to the PyPI 0.2.0 wheel
    ([issue-24.md](issue-24.md)). Image `wled-mcp:0.2.0` built locally, never pushed.
  - Rollback: `image:` 0.3.0 to 0.2.0, `docker compose up -d --no-deps wled-mcp`; healthy at 42 s.
  - Verification on 0.2.0: authenticated `ping` HTTP 200; through the hub `wled_get_service_status`
    version 0.2.0, `wled_list_devices`, 7 existing snapshots, 0 groups, 0 scenes; `wled_get_state`
    read firmware 16.0.1 equal to the baseline. Counters: 6 calls, all read, 0 failed. No controller
    was written; the data checksum list was identical.
  - Restore: `compose.yaml` restored byte-identical, healthy within 33 s, version 0.3.0, data
    checksums identical.
  - Hub: entry and configuration file unchanged; no hub fresh-install test (waiver ISSUE-24-DEC-005).
  - Left on the target: staged directory and image of 0.2.0 (rollback source), backup files.
  - DEPLOYMENT.md corrections: data directory backup needs root; a never-staged release is staged
    first; the stale tool list note says the hub entry needed no change and the cached tool list was
    not observed.
  - Limits: one rollback of one deployment, no data-format change between the releases, no write
    after the rollback (so reading snapshots written by 0.3.0 is untested).
- **0.4.0:** the upgrade from 0.3.0 succeeded ([deploy-0.4.0.md](deploy-0.4.0.md)); the rollback 0.4.0
  to 0.3.0 was **not** run and stays pending.

## 4. Hardware and firmware observations

All hardware evidence is from **one controller: WLED 16.0.1 (build 2606300), ESP32-C3, 133 LEDs, one
RGB segment**; no other controller, firmware, RGBW, CCT, 2D or multi-bus setup was observed.

| Evidence | Release or build | What ran on the controller |
| --- | --- | --- |
| [Issue #11 live check](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06), [#12 runs 1 to 3](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06) | 0.1.x builds | HTTP and stdio via the hub: facts, reads, load, drain, master, effect, segments, layout, presets in slot 250, visible effect, transition |
| [Live check of the second release](live-check-2026-11-08.md) | second release | reads, master power and brightness, a 60 s effect run |
| [#134](issue-134.md) | 0.1.1 on the hub | group and scene, preset store, export, import, restore, one playlist, all restored |
| [#128](issue-128.md) | 0.3.0 source, stdio | five reads and a minimal write set under settings PIN, OTA lock and both |
| [#150](issue-150.md) | candidate | one live snapshot call: endpoint unavailable (HTTP 501); no positive snapshot |
| [#30](issue-30.md) | `main` at PR #175 | one read-only explanation call |
| [#28](issue-28.md) | candidate, **unreleased** | temporary signal start, expiry restore, cancel with conflict; stdio only |
| [#25 H07](issue-25.md) | deployed 0.1.2 | offline entry on a non-routed address failed alone; the real controller was unaffected |
| **Section 4a** | **0.3.0 from PyPI, stdio** | two reads, two writes with restoration |

Mock or loopback only: named zones (#27) and layout preview (#29, unreleased), effect and palette
names in segment writes (#149), served guidance (#147), multi-device scenes, tool profiles on
hardware, CCT, RGBW and 2D, restore onto an occupied slot, playlist import, restoring a playlist
preset, a positive live snapshot, discovery and enrollment (M8 not merged), the MCPB bundle,
reboot or power-cycle persistence. See [VALIDATION.md](../VALIDATION.md#known-limitations).

### 4a. Published 0.3.0 on the selected test controller (2026-11-13)

Authorized by [ISSUE-25-DEC-002](../decisions/issue-25.md) (this issue only); the controller is not
named. A scratch inventory outside the repository was used; a read-only `GET /json/info` confirmed
firmware 16.0.1, ESP32-C3, 133 LEDs. `uvx --isolated --python 3.13 --from wled-mcp==0.3.0`, stdio,
profile `full`, fresh data directory.

1. Restorable state first: read-only copies of `/json/state` and `/presets.json`. Baseline: master
   off, brightness 47, no preset or playlist, segment 0 speed 128, effect 0; the script stops
   otherwise.
2. Calls: `wled_get_state`, `wled_list_presets`; `wled_set_state` brightness 60 (dry run, applied,
   back to 47); `wled_patch_segments` speed 100 on segment 0 (dry run, applied, back to 128). Every
   write returned `applied` / `verified`; none failed or was retried. Master stayed off.
3. Restoration proof: raw readback of `on`, `bri`, `transition`, `ps`, `pl`, `mainseg` and per
   segment `start`, `stop`, `on`, `bri`, `col`, `fx`, `sx`, `ix`, `pal` equals the baseline;
   `/presets.json` identical; no snapshot file created.

Shows the published artifact reads and writes a real WLED 16.0.1 over stdio with readback
verification; not the broader #12 and #134 scope, no HTTP, no hub.

## 5. External routes, verified from outside the project

Unauthenticated `GET` requests to public endpoints on 2026-11-13.

| Route | Observation |
| --- | --- |
| PyPI `wled-mcp` | releases 0.1.2, 0.2.0, 0.3.0; 0.3.0 wheel and sdist hashes equal [release-m2.md](release-m2.md); none yanked; `requires_python` `<3.14,>=3.13`; description carries `mcp-name: io.github.descipar/wled-mcp` |
| MCP Registry | search returns 0.2.0 (active) and 0.3.0 (active, latest, published 2026-11-11); one `pypi` package each, no `remotes` |
| GitHub | repository public, Apache-2.0; releases v0.1.0 to v0.3.0 published; annotated tag `v0.3.0` resolves to the commit recorded in release-m2.md; the release has no assets (MCPB bundle comes later) |
| Container image | **not published** ([#156](https://github.com/descipar/wled-mcp/issues/156), Backlog); HTTP deployments build locally |
| MCPHub fresh install | **waived** ([ISSUE-24-DEC-005](../decisions/issue-24.md)); finding in [issue-24.md](issue-24.md#mcphub-registry-tab-observed-install-dialog-2026-11-10) |

No other listing exists or is planned ([ISSUE-24-DEC-003](../decisions/issue-24.md)).

## 6. Unresolved defects and limits

Open Backlog issues on 2026-11-13, none a blocker: #223, #222, #220, #217, #216, #215, #214, #213,
#190, #180, #162, #156, #138, #117; six Dependabot pull requests (#224 to #229). Behavior limits are
in [VALIDATION.md](../VALIDATION.md#known-limitations). The bounded source review is
[issue-181.md](issue-181.md), not an audit.

## 7. Maintenance scope

Best effort ([CONTRIBUTING](../../CONTRIBUTING.md), [README support](../../README.md#support)); no
security support ([SECURITY.md](../../SECURITY.md), DEC-013); fixes for the latest release only
([CHANGELOG](../../CHANGELOG.md)); "supported" means covered by the
[compatibility matrix](../contract/compatibility.md). WLED 16.0.0+ is the target, 16.0.1 the only
tested firmware, 0.x releases may break with migration notes.

## 8. Tests not run

- Full suite, linters and distribution check were not re-run for this report (CI of the release
  commit is the evidence, [release-m2.md](release-m2.md)); documentation only.
- Linux, Windows, Python other than 3.13; clients other than the SDK client; MCPHub (waived),
  Claude Desktop, MCPB bundle, TLS, non-loopback bind.
- Upgrade and rollback of the next minor release (0.4.0 to 0.3.0).
- Hardware: any other controller, firmware or capability; reboot and power-cycle persistence; the
  mock-only items of section 4; the HTTP transport on hardware with the published package.
- Preset snapshots read by an older release after a newer one wrote them.
- No load, soak or fuzz testing of the published package.
