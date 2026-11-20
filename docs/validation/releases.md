# Validation: releases, launch and visibility runbook

## Release 0.3.0 (milestone M2)

### Preparation

Scope: repository changes only ([DEC-031](../DECISIONS.md#dec-031--release-scope-for-milestone-m2)).
Nothing was tagged, released, uploaded or published in this step; no hardware or hub was contacted.

- Version `0.3.0` in `pyproject.toml` (single source), `uv.lock` (project entry) and both
  `server.json` version fields.
- Tool count 31 to 33 (tool contract table and `tests/tool_contract.py`): `wled_get_live_snapshot`
  (#150) and `wled_explain_lighting` (#30).
- CHANGELOG 0.3.0 section, README capability entry and limits, ROADMAP M2 row, PUBLISHING note.
- Live evidence unchanged: [#150](m3-m6.md) (snapshot endpoint unavailable, HTTP 501) and
  [#30](stage-3.md) (one read-only explanation call).
- Owner-gated steps, each on explicit instruction: tag, GitHub release, PyPI upload, registry
  publication ([PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release)).

### Release and registry publication 2026-11-11

Recorded by the coordinator from its own commands and readbacks in the owner's session
([DEC-031](../DECISIONS.md#dec-031--release-scope-for-milestone-m2)).

- **Tag and release:** annotated tag `v0.3.0` and GitHub release `v0.3.0` on merge commit
  `64615a89d83d96f8ed4643f7c3419899f1fdbac0` of PR #178 (main, CI green), on the owner's instruction.
- **PyPI upload:** publishing the release started `publish.yml` (run 42999302357); build and smoke-test
  succeeded, the `pypi` environment approval was given by the owner's account in the GitHub UI, the
  publish job succeeded. The coordinator had not announced that the release also starts the upload; the
  owner's later instruction covered the remaining steps. PyPI wheel SHA-256
  `84050ec257b0c95222bf728b288d25b81862f97384e71d15da29da888276218f`, sdist
  `d1cc52e6c59b6b84703588705606257826da48f944a48278e347ff069bac1ac4`, identical to the verified
  `SHA256SUMS`; nothing yanked.
- **Marker:** PyPI `info.description` contains `mcp-name: io.github.descipar/wled-mcp`;
  `requires_python` `<3.14,>=3.13`.
- **Install check:** `uvx --isolated --python 3.13 --from wled-mcp==0.3.0 wled-mcp --version` printed
  `wled-mcp 0.3.0`.
- **Registry publish:** `mcp-publisher` 1.8.9 (SHA-256 equal to the published checksum line; Sigstore
  bundle not verified) downloaded into an empty scratch directory; the owner ran `mcp-publisher login
  github`; `publish` at the tagged commit printed "Successfully published io.github.descipar/wled-mcp
  version 0.3.0".
- **Readback:** the registry search returns 0.2.0 (active, not latest) and 0.3.0 (active, latest,
  `publishedAt` 2026-11-11T10:02:17Z).

Not done: no hub deployment, no MCPHub install test, no other listing. No private address or device name
is part of the release files or notes.

## Release 0.4.0 (milestones M3 to M6 and all work merged since 0.3.0)

### Preparation

Scope: repository changes only. The owner asked for the 0.4.0 release pull request covering the
unreleased work of M3 to M6 and **all** work merged since `v0.3.0` (coordinator session, 2026-11-13;
paraphrased). M3, M4 and M5 close without their own release
([DEC-032](../DECISIONS.md#dec-032--m3-closes-without-its-own-release),
[DEC-034](../DECISIONS.md#dec-034--m4-closes-without-its-own-release),
[DEC-036](../DECISIONS.md#dec-036--m5-closes-without-its-own-release)). The instruction covers
preparation only; each publication step needs the owner's explicit instruction
([DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)). The preparation tagged, released,
uploaded and published nothing, contacted no hardware, hub or target, and involves no MCPHub reinstall
([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).

Changes in the pull request:

- Version `0.4.0` in `pyproject.toml` (single source), `uv.lock` (project entry only) and both
  `server.json` versions; the MCPB manifest takes it from `pyproject.toml` at build time. Synthetic
  release-candidate versions in `tests/test_mcpb_bundle.py` changed to a 1.2.3 form (the version-literal
  test forbids the real version outside the allowlist).
- Tool count 33 to 37: `wled_preview_layout` (#29), `wled_start_signal`, `wled_cancel_signal`,
  `wled_get_signal_status` (#28); none removed or renamed, no breaking change.
- CHANGELOG 0.4.0 section with migration notes (symlinked snapshot root #181, fixed HTTP transport
  error bodies, HTTP startup line without host and port, definition-directory scan cap).
- README, ROADMAP rows M3 to M6 and the VALIDATION index updated.

### Completeness check

`git log v0.3.0..origin/main` at `df5c0d8` lists 25 commits, each assigned by hand to a CHANGELOG entry
or to "documentation only, no package effect". The file-level check over `src`, `deploy`, `.github`,
`scripts`, `pyproject.toml`, `uv.lock` (31 files) found no package change without an entry. Entries
added in this PR because they were missing: #181 details, #191, #193, #194, #218, #128, #25 and the
status of #198. The M8 documents describe behavior that does not exist in `src`; the package serves 37
tools.

Left out (not merged): Dependabot pull requests #224 to #229, M7 rooms (#183), M8 (#199 to #204) and
every other feature branch.

### Verified before publication (local, macOS, Python 3.13, this branch)

| Check | Result |
| --- | --- |
| `uv run --frozen pytest -n auto` | 3545 passed, 45 skipped (platform and GNU-tool skips), 8 subtests |
| `ruff check .`, `ruff format --check .`, `ruff check src --select S --ignore S101`, `mypy` | PASS (291 files; 59 source files) |
| `check_lock.py`, `check_agent_setup.py`, `check_private_identifiers.py`, `check_traceability.py` | PASS |
| `scripts/check_distribution.py` | PASS: wheel, clean install, setup commands, stdio, read-only profile, HTTP restart, uvx, hub example; 29 runtime versions |
| `uv build --no-build-isolation --offline --no-create-gitignore`, `twine check --strict` | built and PASSED; local wheel SHA-256 `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3` (release hashes come from the tagged build) |
| `deploy/build_mcpb.py --version 0.4.0` | built `wled-mcp-0.4.0.mcpb` (SHA-256 `a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf`) |

Not run: `check_distribution.py --release-ref` (needs a tag), bash-based workflow tests that skip on
macOS (CI runs them), Windows, a live check, Claude Desktop with the bundle, the GitHub-hosted
workflow. Hardware evidence of the included features is unchanged: signals ran twice on the test
controller ([#28](stage-3.md)); layout preview and the MCPB bundle have none.

### Owner-gated steps after the merge

Each on the owner's explicit instruction at that time; merging does not authorize the next
([PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release), DEC-023, DEC-030):

1. Merge the PR (admin merge only on explicit instruction; not docs-only).
2. Dependabot pull requests are not part of the release.
3. Annotated tag `v0.4.0` on the merge commit and the GitHub release (starts `publish.yml`).
4. Approve the `pypi` environment deployment after comparing the job summary.
5. Check PyPI file names and SHA-256, the `mcp-name` marker and `uvx ... --version`.
6. Check the MCPB assets of the first bundle run (hash equal to the job summary; the bundle jobs do not
   gate PyPI).
7. Pinned `mcp-publisher`, login, publish at the tagged commit, read the registry back.
8. A deployment of the new version on the target is a separate instruction (no MCPHub reinstall,
   DEC-037; rollback checklist [issue-25-rollback-plan.md](hardware-checks.md)).
9. Close M6 and confirm M3 to M5 in GitHub after the release (DEC-030); record the facts here like
   [release-m2.md](releases.md).

### Release and registry publication 2026-11-13

Recorded by the coordinator from the main session's commands and readbacks, each step on the owner's
explicit instruction ("everything of the release", 2026-11-13;
[DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)).

- **Merge:** PR #231 squash-merged as `5bd45b96eb4779cd73620dff2c7a1ee3c61a5e71` by admin merge on
  the owner's instruction; CI green on head `aa34822`.
- **Tag and release:** annotated tag `v0.4.0` on `5bd45b9` and GitHub release `v0.4.0`.
- **Workflow:** `publish.yml` run 43414020842: all four jobs succeeded (build and smoke test, MCPB
  build, PyPI publish, attach MCPB). The `pypi` deployment was approved through the API by the main
  session on the owner's instruction after the hash comparison; the job summary was not readable via
  the API, the upload job re-verifies the files against the build job's checksums.
- **Hash check:** wheel SHA-256 `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3` and
  sdist `a47dacf52ecb09f86d5bfa6ed0445cee038d974d8b5e29aedb35b8a4ae265afc` from the run's artifacts
  equal an independent rebuild (macOS arm64) from a fresh clone of the tag; PyPI shows the same values
  and the `mcp-name: io.github.descipar/wled-mcp` marker.
- **Install check:** `uvx --isolated --python 3.13 --from wled-mcp==0.4.0 wled-mcp --version` in an
  empty directory without GitHub credentials printed `wled-mcp 0.4.0`.
- **MCPB (first bundle run, [#151](stage-2-release.md#first-release-run)):** assets `wled-mcp-0.4.0.mcpb`
  (15006 bytes) and `.sha256`; SHA-256 `a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf`
  equals the `.sha256` file and the build artifact; the `build-mcpb` summary hash was not read via the
  API; no Claude Desktop run.
- **Registry:** `mcp-publisher` 1.8.9 (darwin_arm64, checksum equal to the release checksums file;
  `gh attestation verify` found no SLSA provenance, `cosign` not installed) run outside the repository.
  After the owner's `login github`, `publish` at the tagged clone printed "Successfully published".
  The registry lists 0.2.0, 0.3.0 and 0.4.0; 0.4.0 active, `isLatest` true, `publishedAt`
  2026-11-13T11:54:32Z.

#### Closure state and what is still owner-gated

- [DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release): the M6 closure
  condition (a minor release and an adapted README) is met; M3 to M5 closed without own releases
  (DEC-032, DEC-034, DEC-036). Closing the milestone in GitHub is not a coordinator action
  ([AGENT-WORKFLOW.md](../AGENT-WORKFLOW.md)); it is left to the owner or the main session.
- Deployment of 0.4.0 on the target was done afterwards on a separate owner instruction
  ([deploy-0.4.0.md](releases.md); update from 0.3.0 succeeded, no MCPHub reinstall). The rollback
  after 0.4.0 (to 0.3.0) was not run and stays pending.

## Launch report: published release 0.3.0

Evidence for [#25](https://github.com/descipar/wled-mcp/issues/25) (S2-LAUNCH-01, S2-LAUNCH-02,
acceptance items 2 to 4, and the live rollback of item 1 in section 3). Decisions:
[ISSUE-25-DEC-001, -002 and -003](../decisions/stage-2.md).

**Target.** Published release **v0.3.0** (PyPI, GitHub release, MCP Registry, 33 tools). M3 to M6 work
is merged but unreleased ([CHANGELOG](../../CHANGELOG.md#unreleased), 37 tools). Release 0.4.0 was
published and deployed later the same day ([deploy-0.4.0.md](releases.md)); its rollback was not
run. Nothing was published, tagged, released or submitted by this work; the deployed service was
restarted twice for the one authorized rollback 0.3.0 to 0.2.0 and back.

Environment of the new runs (2026-11-13, empty scratch directories, no GitHub credentials, `python -I`):
macOS 27.2.1 arm64, uv 0.11.7, Python 3.13.2, `mcp` 2.3.0. Scripts are not part of the repository.

### 1. Clean install from PyPI

| Check | Result |
| --- | --- |
| `uvx --isolated --no-cache --python 3.13 --from wled-mcp==0.3.0 wled-mcp --version`, empty cache | installs 29 packages, prints `wled-mcp 0.3.0`, exit 0 |
| Installed metadata | `wled-mcp` 0.3.0, `mcp` 2.3.0, Python 3.13.2 |
| `wled-mcp --help` | stdio default; `--transport streamable-http`, `--profile`, `--allowed-host`, `--http-token-file` listed |

Repeats [release-m2.md](#release-and-registry-publication-2026-11-11) from a clean
cache. Not covered: Linux, Windows, Python other than 3.13 (package requires `>=3.13,<3.14`).

### 2. Interoperability, one run per transport

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

### 3. Upgrade and rollback evidence

- **Live updates of the deployed HTTP service:** second #12 run
  ([VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06)), the second
  release in [live-check-2026-11-08.md](hardware-checks.md), 0.1.2 ([issue-25.md](hardware-checks.md)),
  0.3.0 (read-only observation), 0.4.0 ([deploy-0.4.0.md](releases.md)).
- **Retained data, newer code reads older data:** `tests/test_upgrade_compat.py`
  ([issue-21.md](stage-2-release.md), [versioning](../contract/versioning.md#upgrade-downgrade-and-rollback)).
- **Published releases, local synthetic run:** three stdio sessions on one inventory and data
  directory: 0.2.0 saved a group and a scene, 0.3.0 listed both and saved a second pair, 0.2.0 again
  listed both groups and both scenes. Files byte-identical across the rollback session's reads; 0
  `POST`. `config validate` and `doctor` exist on 0.1.2, 0.2.0 and 0.3.0. This closes, for groups and
  scenes only, the "older server reading newer data" gap of versioning.md; presets snapshots were not
  covered and 0.3.0 changed no data format.
- **Live rollback on the deployed target, run once on 2026-11-13 (S2-COMPAT-03, live part).**
  Authority: [ISSUE-25-DEC-003](../decisions/stage-2.md) (this issue only); the hub itself is never
  reinstalled ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).
  - Before: HTTP service on image `wled-mcp:0.3.0`, healthy, profile `full`, one device. The 0.2.0
    release was not staged and had to be staged first.
  - Backups: `compose.yaml`, the whole data directory (archive plus SHA-256 list of 9 files, needs
    root) and the hub settings file.
  - Staging 0.2.0 on the target (DEC-026): clean clone of tag `v0.2.0`, `uv sync --locked`,
    `check_distribution.py` PASS (aarch64, Python 3.13.5), `deploy/stage_release.py`,
    `sha256sum -c` OK. The staged wheel is byte-identical to the PyPI 0.2.0 wheel
    ([issue-24.md](stage-2-release.md)). Image `wled-mcp:0.2.0` built locally, never pushed.
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
- **0.4.0:** the upgrade from 0.3.0 succeeded ([deploy-0.4.0.md](releases.md)); the rollback 0.4.0
  to 0.3.0 was **not** run and stays pending.

### 4. Hardware and firmware observations

All hardware evidence is from **one controller: WLED 16.0.1 (build 2606300), ESP32-C3, 133 LEDs, one
RGB segment**; no other controller, firmware, RGBW, CCT, 2D or multi-bus setup was observed.

| Evidence | Release or build | What ran on the controller |
| --- | --- | --- |
| [Issue #11 live check](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06), [#12 runs 1 to 3](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06) | 0.1.x builds | HTTP and stdio via the hub: facts, reads, load, drain, master, effect, segments, layout, presets in slot 250, visible effect, transition |
| [Live check of the second release](hardware-checks.md) | second release | reads, master power and brightness, a 60 s effect run |
| [#134](hardware-checks.md) | 0.1.1 on the hub | group and scene, preset store, export, import, restore, one playlist, all restored |
| [#128](hardware-checks.md) | 0.3.0 source, stdio | five reads and a minimal write set under settings PIN, OTA lock and both |
| [#150](m3-m6.md) | candidate | one live snapshot call: endpoint unavailable (HTTP 501); no positive snapshot |
| [#30](stage-3.md) | `main` at PR #175 | one read-only explanation call |
| [#28](stage-3.md) | candidate, **unreleased** | temporary signal start, expiry restore, cancel with conflict; stdio only |
| [#25 H07](hardware-checks.md) | deployed 0.1.2 | offline entry on a non-routed address failed alone; the real controller was unaffected |
| **Section 4a** | **0.3.0 from PyPI, stdio** | two reads, two writes with restoration |

Mock or loopback only: named zones (#27) and layout preview (#29, unreleased), effect and palette
names in segment writes (#149), served guidance (#147), multi-device scenes, tool profiles on
hardware, CCT, RGBW and 2D, restore onto an occupied slot, playlist import, restoring a playlist
preset, a positive live snapshot, discovery and enrollment (M8 not merged), the MCPB bundle,
reboot or power-cycle persistence. See [VALIDATION.md](../VALIDATION.md#known-limitations).

#### 4a. Published 0.3.0 on the selected test controller (2026-11-13)

Authorized by [ISSUE-25-DEC-002](../decisions/stage-2.md) (this issue only); the controller is not
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

### 5. External routes, verified from outside the project

Unauthenticated `GET` requests to public endpoints on 2026-11-13.

| Route | Observation |
| --- | --- |
| PyPI `wled-mcp` | releases 0.1.2, 0.2.0, 0.3.0; 0.3.0 wheel and sdist hashes equal [release-m2.md](releases.md); none yanked; `requires_python` `<3.14,>=3.13`; description carries `mcp-name: io.github.descipar/wled-mcp` |
| MCP Registry | search returns 0.2.0 (active) and 0.3.0 (active, latest, published 2026-11-11); one `pypi` package each, no `remotes` |
| GitHub | repository public, Apache-2.0; releases v0.1.0 to v0.3.0 published; annotated tag `v0.3.0` resolves to the commit recorded in release-m2.md; the release has no assets (MCPB bundle comes later) |
| Container image | **not published** ([#156](https://github.com/descipar/wled-mcp/issues/156), Backlog); HTTP deployments build locally |
| MCPHub fresh install | **waived** ([ISSUE-24-DEC-005](../decisions/stage-2.md)); finding in [issue-24.md](stage-2-release.md#mcphub-registry-tab-observed-install-dialog-2026-11-10) |

No other listing exists or is planned ([ISSUE-24-DEC-003](../decisions/stage-2.md)).

### 6. Unresolved defects and limits

Open Backlog issues on 2026-11-13, none a blocker: #223, #222, #220, #217, #216, #215, #214, #213,
#190, #180, #162, #156, #138, #117; six Dependabot pull requests (#224 to #229). Behavior limits are
in [VALIDATION.md](../VALIDATION.md#known-limitations). The bounded source review is
[issue-181.md](m3-m6.md), not an audit.

### 7. Maintenance scope

Best effort ([CONTRIBUTING](../../CONTRIBUTING.md), [README support](../../README.md#support)); no
security support ([SECURITY.md](../../SECURITY.md), DEC-013); fixes for the latest release only
([CHANGELOG](../../CHANGELOG.md)); "supported" means covered by the
[compatibility matrix](../contract/compatibility.md). WLED 16.0.0+ is the target, 16.0.1 the only
tested firmware, 0.x releases may break with migration notes.

### 8. Tests not run

- Full suite, linters and distribution check were not re-run for this report (CI of the release
  commit is the evidence, [release-m2.md](releases.md)); documentation only.
- Linux, Windows, Python other than 3.13; clients other than the SDK client; MCPHub (waived),
  Claude Desktop, MCPB bundle, TLS, non-loopback bind.
- Upgrade and rollback of the next minor release (0.4.0 to 0.3.0).
- Hardware: any other controller, firmware or capability; reboot and power-cycle persistence; the
  mock-only items of section 4; the HTTP transport on hardware with the published package.
- Preset snapshots read by an older release after a newer one wrote them.
- No load, soak or fuzz testing of the published package.

## Deployment record: release 0.4.0 on the deployed target (2026-11-13)

One owner-authorized update of the deployed HTTP service from 0.3.0 to the published 0.4.0, run by the
coordinator session through the hub's SSH tool, following
[DEPLOYMENT.md](../DEPLOYMENT.md#http-service-update-rollback-recreation-removal) and the
[rollback checklist](hardware-checks.md). Authority: owner instruction relayed 2026-11-13, this
update only; the hub itself is never reinstalled
([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)). Hostnames, paths and
addresses omitted. Times UTC.

### Result

The update succeeded; **no rollback was run** (every check passed). The rollback after this
code-changing release (0.4.0 to 0.3.0) was **not** exercised; its source (image and staged directory of
0.3.0) was kept. The earlier rollback evidence (0.3.0 to 0.2.0 and back) is in the
[launch report](#3-upgrade-and-rollback-evidence).

### Steps

| Step | Observation |
| --- | --- |
| Before (11:55) | image `wled-mcp:0.3.0`, healthy, profile `full`, one device; staged 0.1.2, 0.2.0, 0.3.0 |
| Backups | `compose.yaml`, hub settings file (0600), data directory archive (root needed, 0600) and SHA-256 list of its 9 files (equal to the list before the earlier rollback) |
| Source checked | PyPI wheel SHA-256 `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3`, sdist `a47dacf52ecb09f86d5bfa6ed0445cee038d974d8b5e29aedb35b8a4ae265afc`, neither yanked; annotated tag `v0.4.0` at commit `5bd45b96eb4779cd73620dff2c7a1ee3c61a5e71` |
| Staging (DEC-026) | clean clone of the tag on the target, `uv sync --locked`, `check_distribution.py` PASS (aarch64, 29 runtime versions), `deploy/stage_release.py`, `sha256sum -c` OK; staged wheel byte-identical to the PyPI wheel |
| Image | `wled-mcp:0.4.0` built locally from the staged directory, never pushed |
| Switch (11:58:42) | `image:` 0.3.0 to 0.4.0, `up -d --no-deps wled-mcp`; `healthy` within 40 s |

### Verification on 0.4.0 (read-only against controllers)

- Authenticated `ping` HTTP 200; log shows the listen line only.
- Through the hub (entry unchanged): `wled_get_service_status` version 0.4.0, streamable-http, profile
  `full`, backups writable; the hub's tool list includes the new tools without any hub change.
- `tools/list`: **37 tools** (33 in 0.3.0).
- Upgrade read of existing data: the existing device, 7 existing snapshots (all `restorable`,
  `invalid_count` 0), 0 groups, 0 scenes; the data checksum list was **identical** after the run.
- `wled_get_state` of the controller: firmware 16.0.1, master off, brightness 47, segment 0 unchanged.
- Counters: 6 calls, 6 read, 0 control, 0 manage, 0 failed. No controller was written.

### Hub, left on the target, limits

The hub entry needed and received **no change** (settings file byte-identical to its backup); no hub
reinstall; no fresh-install test (waiver ISSUE-24-DEC-005). Staged directory and image of 0.4.0 are in
use; 0.3.0, 0.2.0, 0.1.2 and the backups stay. Limits: one update of one deployment, no data-format
change between the releases, no write tool exercised on 0.4.0 (signal and preview tools not run on
hardware here; snapshots written by 0.4.0 not read by 0.3.0), rollback 0.4.0 to 0.3.0 not run.

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
