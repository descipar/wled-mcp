# Validation: releases, launch and visibility runbook

## Release 0.3.0 (milestone M2)

### Preparation

Repository changes only ([DEC-031](../DECISIONS.md#dec-031--release-scope-for-milestone-m2)); nothing
tagged, released, uploaded or published and no hardware or hub contacted. Version `0.3.0` in
`pyproject.toml`, `uv.lock` and both `server.json` fields; tool count 31 to 33
(`wled_get_live_snapshot` #150, `wled_explain_lighting` #30); CHANGELOG, README, ROADMAP and
PUBLISHING updated. Live evidence unchanged: [#150](m3-m6.md) (snapshot endpoint unavailable, HTTP 501)
and [#30](stage-3.md) (one read-only explanation call). Tag, GitHub release, PyPI upload and registry
publication are owner-gated, each on explicit instruction
([PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release)).

### Release and registry publication 2026-11-11

Recorded by the coordinator from its own commands and readbacks in the owner's session
([DEC-031](../DECISIONS.md#dec-031--release-scope-for-milestone-m2)).

- Annotated tag and GitHub release `v0.3.0` on the merge commit of PR #178 (CI green).
- Publishing the release started `publish.yml` (build and smoke test, owner approval of the `pypi`
  environment, publish): succeeded. PyPI wheel SHA-256
  `84050ec257b0c95222bf728b288d25b81862f97384e71d15da29da888276218f`, sdist
  `d1cc52e6c59b6b84703588705606257826da48f944a48278e347ff069bac1ac4`, identical to the verified
  `SHA256SUMS`; nothing yanked; `mcp-name` marker present; `requires_python` `<3.14,>=3.13`.
- `uvx --isolated --python 3.13 --from wled-mcp==0.3.0 wled-mcp --version` printed `wled-mcp 0.3.0`.
- Registry: `mcp-publisher` 1.8.9 (checksum equal, Sigstore bundle not verified), owner login, publish at the
  tagged commit; the registry lists 0.2.0 (active) and 0.3.0 (active, latest, published 2026-11-11).

Not done: hub deployment, MCPHub install test, any other listing.

## Release 0.4.0 (milestones M3 to M6 and all work merged since 0.3.0)

### Preparation

Repository changes only, on the owner's request for one release covering M3 to M6 and all work merged
since `v0.3.0` (2026-11-13). M3, M4 and M5 close without their own release
([DEC-032](../DECISIONS.md#dec-032--m3-closes-without-its-own-release),
[DEC-034](../DECISIONS.md#dec-034--m4-closes-without-its-own-release),
[DEC-036](../DECISIONS.md#dec-036--m5-closes-without-its-own-release)); each publication step needs the
owner's explicit instruction ([DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)); no
MCPHub reinstall ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)). Version
`0.4.0` in `pyproject.toml`, `uv.lock` and both `server.json` versions (the MCPB manifest takes it at
build time); tool count 33 to 37 (`wled_preview_layout` #29, `wled_start_signal`, `wled_cancel_signal`,
`wled_get_signal_status` #28; none removed or renamed); CHANGELOG with migration notes, README, ROADMAP
and the VALIDATION index updated.

### Completeness check

The 25 commits of `v0.3.0..main` were each assigned to a CHANGELOG entry or to "documentation only"; the
file-level check over `src`, `deploy`, `.github`, `scripts`, `pyproject.toml` and `uv.lock` (31 files)
found no package change without an entry, and missing entries were added. Left out: Dependabot pull
requests #224 to #229, M7 rooms (#183) and M8 (#199 to #204).

### Verified before publication (local, macOS, Python 3.13, this branch)

| Check | Result |
| --- | --- |
| `uv run --frozen pytest -n auto` | 3545 passed, 45 skipped (platform and GNU-tool skips), 8 subtests |
| `ruff check .`, `ruff format --check .`, `ruff check src --select S --ignore S101`, `mypy` | PASS |
| `check_lock.py`, `check_agent_setup.py`, `check_private_identifiers.py`, `check_traceability.py` | PASS |
| `scripts/check_distribution.py` | PASS: wheel, clean install, setup commands, stdio, read-only profile, HTTP restart, uvx, hub example; 29 runtime versions |
| `uv build`, `twine check --strict`, `deploy/build_mcpb.py --version 0.4.0` | built and PASSED (release hashes come from the tagged build) |

Not run: `check_distribution.py --release-ref` (needs a tag), bash-based workflow tests that skip on
macOS (CI runs them), Windows, a live check, Claude Desktop with the bundle, the GitHub-hosted workflow.
Hardware evidence of the included features is unchanged: signals ran twice on the test controller
([#28](stage-3.md)); layout preview and the MCPB bundle have none.

### Owner-gated steps after the merge

Each on the owner's explicit instruction at that time
([PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release), DEC-023, DEC-030): merge
(admin merge only on explicit instruction); annotated tag and GitHub release (starts `publish.yml`);
approval of the `pypi` environment after comparing the job summary; check of PyPI file names, hashes,
marker and `uvx ... --version`; check of the MCPB assets; pinned `mcp-publisher` login and publish at the
tagged commit with a registry readback; a deployment on the target is a separate instruction (no MCPHub
reinstall, DEC-037; [rollback checklist](hardware-checks.md#issue-25-live-rollback-checklist-for-the-deployed-target));
closing M6 and confirming M3 to M5 in GitHub (DEC-030).

### Release and registry publication 2026-11-13

Recorded by the coordinator from the main session's commands and readbacks, each step on the owner's
explicit instruction ("everything of the release", 2026-11-13;
[DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)).

- PR #231 admin-merged on the owner's instruction (CI green); annotated tag and GitHub release `v0.4.0`.
- `publish.yml`: all four jobs succeeded (build and smoke test, MCPB build, PyPI publish, attach MCPB);
  the `pypi` deployment was approved through the API after the hash comparison.
- Wheel SHA-256 `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3` and sdist
  `a47dacf52ecb09f86d5bfa6ed0445cee038d974d8b5e29aedb35b8a4ae265afc` equal an independent rebuild
  (macOS arm64) from a fresh clone of the tag; PyPI shows the same values and the `mcp-name` marker.
- `uvx --isolated --python 3.13 --from wled-mcp==0.4.0 wled-mcp --version` printed `wled-mcp 0.4.0`.
- MCPB (first bundle run, [#151](stage-2-release.md#first-release-run)): `wled-mcp-0.4.0.mcpb` (15006
  bytes) and `.sha256`, hash SHA-256 `a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf`
  equal to the build artifact; the job-summary hash was not read via the API; no Claude Desktop run.
- Registry: `mcp-publisher` 1.8.9 (checksum equal; no SLSA provenance found, `cosign` not installed);
  after the owner's login the publish succeeded and the registry lists 0.2.0, 0.3.0 and 0.4.0 (0.4.0
  active, latest, published 2026-11-13).

#### Closure state and what is still owner-gated

[DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release): the M6 closure condition
(a minor release and an adapted README) is met; M3 to M5 closed without own releases. Closing the
milestone in GitHub is left to the owner or the main session. Deployment of 0.4.0 followed on a separate
owner instruction (below); the rollback 0.4.0 to 0.3.0 was not run and stays pending.

## Release 0.4.1 (milestones M7 and M8 and all work merged since 0.4.0)

### Preparation

PR #274 (merge commit `b65196a4582c1df9d89c1e429c6e6db220725c31`), on the owner's request to finish M8
as release 0.4.1 instead of the provisional 0.5.0. The owner counts 0.4.1 as the
[DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release) release for M8
([DEC-040](../DECISIONS.md#dec-040--release-041-counts-as-the-dec-030-release-for-m8)); M7 closes
without its own release ([DEC-038](../DECISIONS.md#dec-038--m7-closes-without-its-own-release)).
Version `0.4.1` in `pyproject.toml`, `uv.lock` and both `server.json` versions; the `full` profile serves
41 tools instead of 37 (`wled_apply_room`, `wled_discover_devices`, `wled_add_device`,
`wled_set_discovery_ranges`); the CHANGELOG section says it is not a bugfix release and the migration rows
`/kind`, `/devices/mac` and `/discovery` name 0.4.1.

Verified before publication (local, macOS, Python 3.13): `pytest -n auto` 3894 passed, 47 skipped;
ruff, `ruff --select S`, mypy, `sync_agents --check`, `check_agent_setup`, `check_lock`,
`check_private_identifiers`, `check_traceability`, `tests/test_version_source.py`,
`tests/test_upgrade_compat.py` and `scripts/check_distribution.py` PASS; MCPB dry run built. An Opus
review of the head (CHANGES_REQUESTED on the first head, PASS after fixes) preceded the merge; CI was green.

### Release and registry publication 2026-11-21

Each step on the owner's explicit instruction
([DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)); recorded by the coordinator.

- Annotated tag `v0.4.1` on `b65196a4582c1df9d89c1e429c6e6db220725c31` and GitHub release `v0.4.1`
  (title only, not a draft or pre-release).
- `publish.yml` run 44953263941: all jobs succeeded (build and smoke test, MCPB build, PyPI publish,
  attach MCPB).
- PyPI files and SHA-256 (equal to the build artifacts; the `mcp-name` marker is in the description):
  `wled_mcp-0.4.1-py3-none-any.whl` `230e7cbb33d6aa4544618c85c56bf23fc4b12188c7cc180d744e42087dabf8d4`;
  `wled_mcp-0.4.1.tar.gz` `536673edb69788dff2c175098b6afabf25ddcc7054dfe6c35b1aff5d994d9053`.
- `uvx --no-cache --isolated --python 3.13 --from wled-mcp==0.4.1 wled-mcp --version` printed `0.4.1`.
- MCPB: `wled-mcp-0.4.1.mcpb` SHA-256
  `1706f1138377c78c0b3cb547391ce24d799599e5c3a0acb41f376f04d309bcd7` with its `.sha256` on the release;
  the hash equals the local dry run.
- Registry: `mcp-publisher` 1.8.11 (checksum verified); `io.github.descipar/wled-mcp` 0.4.1 is active and
  latest; 0.2.0, 0.3.0 and 0.4.0 stay listed.

### Limits

Not run: Claude Desktop with the bundle, Linux hosts or Docker host-network mode for discovery (one
network and one Docker Desktop version only; [validation/m7-m8.md](m7-m8.md#live-runs-2026-11-20)),
a deployment of 0.4.1 on the owner's target (a separate owner-gated step, DEC-026, DEC-037) and a
rollback run. Closing #204 and the M7/M8 milestones is left to the owner or the completion step.

## Release 0.5.0 (milestone M9 and all work merged since 0.4.1)

### Preparation

PR #303 (merge commit `c014afe683c44c2467d3f3e3f253fb2693b6ae25`), on the owner's request to prepare the
[DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release) release for M9 without further
Backlog items. Content: the simplified segment schema (#246, one canonical form per optional nullable
field, a breaking change in the [DEC-020](../DECISIONS.md#dec-020--support-and-version-policy) sense with its
migration rows), tool groups (#236), catalog resources (#258) and the carried nits (#301); #237 added only a
design note (ISSUE-237-DEC-001, design C as target, not implemented) and #290 was closed as not planned after
a measurement. The tool count stays 41. Version `0.5.0` in `pyproject.toml`, `uv.lock` and both `server.json`
versions; the README feature list is current for M9 and the "not yet released" markers are gone.

Verified before publication (CI and local, Python 3.13): full test suite 4094 passed, 47 skipped; ruff,
mypy, `sync_agents --check`, `check_traceability`, `check_private_identifiers`,
`tests/test_version_source.py`, `tests/test_upgrade_compat.py` and `scripts/check_distribution.py` on a
local `uv build` (clean install, stdio, HTTP, uvx) PASS. An independent Opus review of the first head
(PASS, no must-fix) was followed by three docs-only corrections that got a light check; CI was green on the
merged head `afddb4dc3d4e084fb2907d29ef0b7303497f68db`.

### Release and registry publication 2026-11-27

Each step on the owner's explicit instruction
([DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)); recorded by the main session.

- Annotated tag `v0.5.0` on `c014afe683c44c2467d3f3e3f253fb2693b6ae25` and GitHub release `v0.5.0`
  (title only, with the changelog section as body like 0.4.1; not a draft or pre-release).
- `publish.yml` run 46025302645: all jobs succeeded (build and smoke test, MCPB build, PyPI publish,
  attach MCPB); the owner approved the `pypi` deployment.
- PyPI files and SHA-256 (equal to the build log; the `mcp-name` marker is in the description; none yanked):
  `wled_mcp-0.5.0-py3-none-any.whl` `3f2e1513a1424382596652f08e188c513e9558a34475b5a75b4c328005342868`;
  `wled_mcp-0.5.0.tar.gz` `e38e75e3b71c03f7b70f42363e63c44e127825b04d5a96449a257a9251666cd6`.
- `uvx --no-cache --isolated --python 3.13 --from wled-mcp==0.5.0 wled-mcp --version` printed `0.5.0`.
- MCPB: `wled-mcp-0.5.0.mcpb` SHA-256
  `6ba0dad4434de3dfdf1ef9daf6efc17536c5e2384aca65663ee71e7420ae70bf` with its `.sha256` on the release; the
  downloaded file hashes to the same value.
- Registry: `mcp-publisher` 1.8.16 (`mcp-publisher_darwin_arm64.tar.gz` SHA-256
  `5193b2c55627027cbda652ae8577aa3221fcff9ad743a011f830e81f361fa061` equal to the release's checksum file; the
  newest release 1.8.17 was a few hours old and not used; the Sigstore bundle was not verified, `cosign` is
  not installed); after the owner's device-code login the publish succeeded and the registry lists 0.2.0,
  0.3.0, 0.4.0 and 0.4.1 (active) and 0.5.0 (active, latest, published 2026-11-27 15:32 UTC).

### Limits

Not run: Claude Desktop with the bundle, a real MCP client for tool groups and catalog resources (the
token figures are heuristics, no client measurement), a hardware check of M9 (no write path changed), a
deployment of 0.5.0 on the owner's target (a separate owner-gated step, DEC-026, DEC-037) and a rollback
run. Closing the M9 milestone is left to the owner.

## Launch report: published release 0.3.0

Evidence for [#25](https://github.com/descipar/wled-mcp/issues/25) (S2-LAUNCH-01, S2-LAUNCH-02,
acceptance items 2 to 4, and the live rollback of item 1 in section 3); decisions
[ISSUE-25-DEC-001, -002 and -003](../decisions/stage-2.md). Target: published release v0.3.0 (PyPI,
GitHub release, MCP Registry, 33 tools); 0.4.0 was published and deployed later the same day. Nothing was
published, tagged or submitted by this work; the deployed service was restarted twice for the one
authorized rollback 0.3.0 to 0.2.0 and back. New runs on 2026-11-13: macOS arm64, uv 0.11.7, Python
3.13.2, `mcp` 2.3.0, empty scratch directories, no GitHub credentials.

### 1. Clean install from PyPI

`uvx --isolated --no-cache --python 3.13 --from wled-mcp==0.3.0 wled-mcp --version` installs 29
packages and prints `wled-mcp 0.3.0`; `--help` lists the stdio default and the HTTP, profile, host and
token-file options. Not covered: Linux, Windows, Python other than 3.13.

### 2. Interoperability, one run per transport

PyPI package, real SDK client, one synthetic loopback device that answers only `GET /json/info` and
`/json/state` and refuses `POST`; HTTP service on `127.0.0.1` with explicit host and token file.

| Check | stdio | Streamable HTTP |
| --- | --- | --- |
| `initialize`, `tools/list` | ok, 33 tools | ok, 33 tools |
| `wled_list_devices` with `probe`, `wled_get_state`, `wled_get_service_status` | `ok` | `ok` |
| Request without credential | not applicable | HTTP 401 |

The loopback server saw 6 `GET` and 0 `POST`. Not covered: other MCP clients (MCPHub, Claude Desktop),
TLS, non-loopback bind, a write tool, the 2026-07-28 per-request protocol path. CI exercises both
transports on every run.

### 3. Upgrade and rollback evidence

- **Live updates of the deployed HTTP service:** second #12 run
  ([VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06)), the second release
  ([live check](hardware-checks.md)), 0.1.2 ([H07](hardware-checks.md)), 0.3.0 (read-only observation),
  0.4.0 (deployment record below).
- **Retained data:** `tests/test_upgrade_compat.py` and
  [versioning](../contract/versioning.md#upgrade-downgrade-and-rollback) (newer code reads older data).
- **Published releases, local synthetic run:** three stdio sessions on one inventory and data directory
  (0.2.0 saved a group and a scene, 0.3.0 listed both and saved a second pair, 0.2.0 again listed all);
  files byte-identical across the rollback reads, 0 `POST`. Closes the older-reads-newer-data gap for
  groups and scenes only; preset snapshots not covered.
- **Live rollback on the deployed target, once on 2026-11-13 (S2-COMPAT-03, live part):** authority
  [ISSUE-25-DEC-003](../decisions/stage-2.md) (this issue only), hub never reinstalled
  ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)). 0.3.0 to 0.2.0 after
  staging 0.2.0 on the target (DEC-026; staged wheel byte-identical to PyPI), backups of compose file,
  data directory (9 files, SHA-256 list) and hub settings; healthy at 42 s; read-only verification
  (version 0.2.0, 7 snapshots, 0 groups and scenes, firmware 16.0.1 equal to baseline, 6 read calls, 0
  failed, data checksums identical); compose file restored byte-identical, healthy within 33 s on 0.3.0.
  Limits: one rollback of one deployment, no data-format change between the releases, no write after the
  rollback (reading snapshots written by 0.3.0 untested). Corrections made to DEPLOYMENT.md: data
  directory backup needs root, a never-staged release is staged first.
- **0.4.0:** the upgrade succeeded (deployment record below); the rollback 0.4.0 to 0.3.0 was not run
  and stays pending.

### 4. Hardware and firmware observations

All hardware evidence is from one controller: WLED 16.0.1 (build 2606300), ESP32-C3, 133 LEDs, one RGB
segment; no other controller, firmware, RGBW, CCT, 2D or multi-bus setup was observed.

| Evidence | Release or build | What ran on the controller |
| --- | --- | --- |
| [Issue #11 live check](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06), [#12 runs 1 to 3](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06) | 0.1.x builds | HTTP and stdio via the hub: facts, reads, load, drain, master, effect, segments, layout, presets in slot 250, visible effect, transition |
| [Live check of the second release](hardware-checks.md) | second release | reads, master power and brightness, a 60 s effect run |
| [#134](hardware-checks.md) | 0.1.1 on the hub | group and scene, preset store, export, import, restore, one playlist, all restored |
| [#128](hardware-checks.md) | 0.3.0 source, stdio | five reads and a minimal write set under settings PIN, OTA lock and both |
| [#150](m3-m6.md) | candidate | one live snapshot call: endpoint unavailable (HTTP 501); no positive snapshot |
| [#30](stage-3.md) | `main` at PR #175 | one read-only explanation call |
| [#28](stage-3.md) | candidate, unreleased | temporary signal start, expiry restore, cancel with conflict; stdio only |
| [#25 H07](hardware-checks.md) | deployed 0.1.2 | offline entry on a non-routed address failed alone; the real controller was unaffected |
| Section 4a | 0.3.0 from PyPI, stdio | two reads, two writes with restoration |

Mock or loopback only: named zones (#27) and layout preview (#29, unreleased), effect and palette names
in segment writes (#149), served guidance (#147), multi-device scenes, tool profiles on hardware, CCT,
RGBW and 2D, restore onto an occupied slot, playlist import, restoring a playlist preset, a positive live
snapshot, discovery and enrollment (M8 not merged), the MCPB bundle, reboot or power-cycle persistence.
See [VALIDATION.md](../VALIDATION.md#known-limitations).

#### 4a. Published 0.3.0 on the selected test controller (2026-11-13)

Authorized by [ISSUE-25-DEC-002](../decisions/stage-2.md) (this issue only); controller not named, scratch
inventory outside the repository, `uvx ... wled-mcp==0.3.0`, stdio, profile `full`, fresh data directory.
Restorable state copied first (baseline: master off, brightness 47, no preset or playlist, segment 0 speed
128, effect 0). Calls: `wled_get_state`, `wled_list_presets`; `wled_set_state` brightness 60 and
`wled_patch_segments` speed 100, each dry run, applied, then back to baseline; every write `applied` /
`verified`, none failed or retried. Raw readback equals the baseline and `/presets.json` is identical; no
snapshot file was created. Shows the published artifact reads and writes a real WLED 16.0.1 over stdio;
not the broader #12 and #134 scope, no HTTP, no hub.

### 5. External routes, verified from outside the project

Unauthenticated `GET` requests on 2026-11-13: PyPI lists 0.1.2, 0.2.0 and 0.3.0 (hashes equal the 0.3.0
record above, none yanked, marker present); the MCP Registry lists 0.2.0 (active) and 0.3.0 (active,
latest) with one `pypi` package each and no `remotes`; the repository is public (Apache-2.0) with releases
v0.1.0 to v0.3.0 and no assets on v0.3.0; no container image is published
([#156](https://github.com/descipar/wled-mcp/issues/156), Backlog); MCPHub fresh install is waived
([ISSUE-24-DEC-005](../decisions/stage-2.md); finding in
[issue #24](stage-2-release.md#mcphub-registry-tab-observed-install-dialog-2026-11-10)). No other listing
exists or is planned ([ISSUE-24-DEC-003](../decisions/stage-2.md)).

### 6. Unresolved defects and limits

Open Backlog issues on 2026-11-13, none a blocker: #223, #222, #220, #217, #216, #215, #214, #213, #190,
#180, #162, #156, #138, #117; six Dependabot pull requests (#224 to #229). Behavior limits are in
[VALIDATION.md](../VALIDATION.md#known-limitations); the bounded source review ([#181](m3-m6.md)) is not
an audit.

### 7. Maintenance scope

Best effort ([CONTRIBUTING](../../CONTRIBUTING.md), [README support](../../README.md#support)); no
security support ([SECURITY.md](../../SECURITY.md), DEC-013); fixes for the latest release only
([CHANGELOG](../../CHANGELOG.md)); "supported" means covered by the
[compatibility matrix](../contract/compatibility.md). WLED 16.0.0+ is the target, 16.0.1 the only tested
firmware, 0.x releases may break with migration notes.

### 8. Tests not run

- Full suite, linters and distribution check were not re-run for this report (CI of the release commit is
  the evidence); documentation only.
- Linux, Windows, Python other than 3.13; clients other than the SDK client; MCPHub (waived), Claude
  Desktop, MCPB bundle, TLS, non-loopback bind.
- Upgrade and rollback of the next minor release (0.4.0 to 0.3.0).
- Hardware: any other controller, firmware or capability; reboot and power-cycle persistence; the
  mock-only items of section 4; the HTTP transport on hardware with the published package.
- Preset snapshots read by an older release after a newer one wrote them; no load, soak or fuzz testing.

## Deployment record: release 0.4.0 on the deployed target (2026-11-13)

One owner-authorized update of the deployed HTTP service from 0.3.0 to the published 0.4.0, run by the
coordinator session through the hub's SSH tool, following
[DEPLOYMENT.md](../DEPLOYMENT.md#http-service-update-rollback-recreation-removal) and the
[rollback checklist](hardware-checks.md#issue-25-live-rollback-checklist-for-the-deployed-target);
authority: owner instruction of 2026-11-13, this update only; the hub is never reinstalled
([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)). Hostnames, paths and
addresses omitted.

### Result

The update succeeded; no rollback was run. The rollback after this code-changing release (0.4.0 to 0.3.0)
was not exercised; its source (image and staged directory of 0.3.0) was kept. The earlier rollback
evidence (0.3.0 to 0.2.0 and back) is in the [launch report](#3-upgrade-and-rollback-evidence).

### Steps

Before: image `wled-mcp:0.3.0`, healthy, profile `full`, one device. Backups of the compose file, the hub
settings file and the data directory (archive and SHA-256 list of 9 files). Source checked: PyPI wheel
and sdist hashes equal the 2026-11-13 publication record above, tag `v0.4.0` at the recorded commit.
Staging (DEC-026): clean clone of the tag on the target, `uv sync --locked`, `check_distribution.py` PASS
(aarch64, 29 runtime versions), `deploy/stage_release.py`, `sha256sum -c` OK, staged wheel byte-identical
to the PyPI wheel. Image `wled-mcp:0.4.0` built locally, never pushed. Switch `image:` 0.3.0 to 0.4.0
with `up -d --no-deps wled-mcp`: healthy within 40 s.

### Verification on 0.4.0 (read-only against controllers)

Authenticated `ping` HTTP 200; `wled_get_service_status` version 0.4.0, streamable-http, profile `full`,
backups writable; the hub's tool list shows the new tools without any hub change; `tools/list` 37 tools
(33 in 0.3.0); existing data read (the device, 7 snapshots all `restorable`, 0 groups, 0 scenes) with an
identical data checksum list afterwards; `wled_get_state` firmware 16.0.1, master off, brightness 47,
segment 0 unchanged. Counters: 6 calls, 6 read, 0 control, 0 manage, 0 failed. No controller was written.

### Hub, left on the target, limits

The hub entry needed and received no change; no hub reinstall or fresh-install test (waiver
ISSUE-24-DEC-005). Staged directory and image of 0.4.0 are in use; 0.3.0, 0.2.0, 0.1.2 and the backups
stay. Limits: one update of one deployment, no data-format change between the releases, no write tool
exercised on 0.4.0 (signal and preview tools not run on hardware here; snapshots written by 0.4.0 not read
by 0.3.0), rollback 0.4.0 to 0.3.0 not run.

## Deployment record: release 0.4.1 on the deployed target (2026-11-21)

One owner-authorized update of the deployed HTTP service from 0.4.0 to the published 0.4.1, run by the
session through the hub's SSH tool, following
[DEPLOYMENT.md](../DEPLOYMENT.md#http-service-update-rollback-recreation-removal); authority: owner
instruction of 2026-11-21, this update only; the hub is never reinstalled
([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)). Hostnames, paths and
addresses omitted.

### Result

The update succeeded; no rollback was run. The rollback 0.4.1 to 0.4.0 was not exercised; its source
(image and staged directory of 0.4.0, compose backup) was kept. Note: 0.4.0 rejects the new optional
configuration keys `mac` and `[discovery]` at startup; the deployed configuration has neither.

### Steps

Before: image `wled-mcp:0.4.0`, healthy, profile `full`, one device. Backups of the compose file and a
SHA-256 list of the 9 data files. Source: tag `v0.4.1` at the release commit. Staging (DEC-026): clean
clone of the tag on the target, `uv sync --locked`, `check_distribution.py` PASS (aarch64, 29 runtime
versions), `deploy/stage_release.py`, `sha256sum -c` OK, staged wheel byte-identical to the PyPI wheel.
Image `wled-mcp:0.4.1` built locally, never pushed. Switch `image:` 0.4.0 to 0.4.1 with
`up -d --no-deps wled-mcp`: healthy within about 45 s. The build clone and its logs were removed afterwards.

### Verification on 0.4.1 (no controller contacted)

`wled_get_service_status` through the hub: version 0.4.1, streamable-http, profile `full`, backups
writable; the hub's tool list shows `wled_discover_devices`, `wled_add_device`,
`wled_set_discovery_ranges` and `wled_apply_room` without any hub change; the data checksum list is
identical afterwards. Counters: 0 calls of the new tools, no write to any controller.

### Hub, left on the target, limits

No hub change and no hub reinstall. Staged directory and image of 0.4.1 are in use; 0.4.0 and older
images, staged directories and the backups stay. The profile `full` serves the two `manage` tools
(configuration writes only, never a device write). Limits: one update of one deployment; no new tool
run through the hub; discovery was validated separately on 2026-11-20 ([record](m7-m8.md)).

## Issue #90 runbook: visibility change and `main` rules

Status: prepared, not executed. Sections 1 to 4 are owner-only actions in the repository settings;
no agent changes visibility, rulesets or settings. Decisions:
[DEC-019](../DECISIONS.md#dec-019--make-the-repository-public-before-the-release),
[DEC-023](../DECISIONS.md#dec-023--staged-first-public-release),
[DEC-024](../DECISIONS.md#dec-024--main-branch-rules-with-review-for-external-pull-requests).

Rulesets and the fork-approval setting are unavailable for the private repository (2026-11-08: rulesets
API HTTP 403, fork-approval API HTTP 422), so sections 2 to 4 follow section 1. UI labels follow the
GitHub documentation of that date; the read-back in section 5 is the authority.

### 0. Before the visibility change

The DEC-015 scan result is approved by the owner (recorded in #90); `main` is green and contains the
commit to publish; the owner has given the explicit instruction.

### 1. Make the repository public

Settings, General, "Danger Zone", "Change repository visibility", choose public and confirm (the
repository name has to be typed).

### 2. Require approval for workflow runs of outside pull requests

Settings, Actions, General, "Approval for running fork pull request workflows from contributors":
"Require approval for all external contributors", save.

### 3. Ruleset A: integrity of `main` (no bypass)

Settings, Rules, Rulesets, New branch ruleset: name `main-integrity`, enforcement Active, empty
bypass list, target the default branch. Rules: restrict deletions; block force pushes; require status
checks `checks (ubuntu-latest, 3.13)` and `checks (ubuntu-24.04-arm, 3.13)` (up-to-date branches
off).

### 4. Ruleset B: review of pull requests, owner bypass for merging (DEC-024)

New branch ruleset: name `main-review`, enforcement Active, bypass "Repository admin" role set to
"For pull requests only", target the default branch. Rule: require a pull request with 1 required
approval; Code Owners, stale-approval dismissal and most-recent-push approval off.

Expected: an external pull request cannot run workflows before the owner approves them and cannot
merge without one approving review and green checks. A pull request of the owner or of an agent under
the owner's account shows a bypass option for the review requirement; ruleset A still applies.

### 5. Read-back by the agent (read-only)

After the owner reports sections 1 to 4 as done, the agent runs these GET requests with the owner's
authenticated `gh`, never a mutating one, and records the result in #90 without secrets.

```bash
gh api repos/descipar/wled-mcp --jq '{visibility, private}'
# expect: visibility "public", private false
gh api repos/descipar/wled-mcp/actions/permissions/fork-pr-contributor-approval
# expect: policy "all_external_contributors" (check the returned field name)
gh api repos/descipar/wled-mcp/rulesets --jq '.[] | {id, name, enforcement, target}'
# expect: main-integrity and main-review, both "active", target "branch"
gh api repos/descipar/wled-mcp/rulesets/<id> \
  --jq '{name, enforcement, bypass_actors, conditions, rules: [.rules[] | {type, parameters}]}'
# main-integrity: bypass_actors [], deletion, non_fast_forward, required_status_checks with the
#   two contexts and strict_required_status_checks_policy false
# main-review: one admin bypass actor with bypass_mode "pull_request", rule pull_request with
#   required_approving_review_count 1
```

### 6. After the first merge under the new rules

The first agent-made merge shows whether `gh pr merge --squash --match-head-commit <sha>` needs
`--admin` for the review bypass; only then are `agents/coordinator.md` (regenerated adapters) and
DEC-022 item 4 updated. An outside pull request is not simulated by an agent; the owner may open a
test pull request from a second account or fork to observe the approval prompt.
