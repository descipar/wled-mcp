# Deployment record: release 0.4.0 on the deployed target (2026-11-13)

One owner-authorized update of the deployed HTTP service from 0.3.0 to the published 0.4.0, run by the
coordinator session through the hub's SSH tool, following
[DEPLOYMENT.md](../DEPLOYMENT.md#http-service-update-rollback-recreation-removal) and the
[rollback checklist](issue-25-rollback-plan.md). Authority: owner instruction relayed 2026-11-13, this
update only; the hub itself is never reinstalled
([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)). Hostnames, paths and
addresses omitted. Times UTC.

## Result

The update succeeded; **no rollback was run** (every check passed). The rollback after this
code-changing release (0.4.0 to 0.3.0) was **not** exercised; its source (image and staged directory of
0.3.0) was kept. The earlier rollback evidence (0.3.0 to 0.2.0 and back) is in the
[launch report](launch-report.md#3-upgrade-and-rollback-evidence).

## Steps

| Step | Observation |
| --- | --- |
| Before (11:55) | image `wled-mcp:0.3.0`, healthy, profile `full`, one device; staged 0.1.2, 0.2.0, 0.3.0 |
| Backups | `compose.yaml`, hub settings file (0600), data directory archive (root needed, 0600) and SHA-256 list of its 9 files (equal to the list before the earlier rollback) |
| Source checked | PyPI wheel SHA-256 `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3`, sdist `a47dacf52ecb09f86d5bfa6ed0445cee038d974d8b5e29aedb35b8a4ae265afc`, neither yanked; annotated tag `v0.4.0` at commit `5bd45b96eb4779cd73620dff2c7a1ee3c61a5e71` |
| Staging (DEC-026) | clean clone of the tag on the target, `uv sync --locked`, `check_distribution.py` PASS (aarch64, 29 runtime versions), `deploy/stage_release.py`, `sha256sum -c` OK; staged wheel byte-identical to the PyPI wheel |
| Image | `wled-mcp:0.4.0` built locally from the staged directory, never pushed |
| Switch (11:58:42) | `image:` 0.3.0 to 0.4.0, `up -d --no-deps wled-mcp`; `healthy` within 40 s |

## Verification on 0.4.0 (read-only against controllers)

- Authenticated `ping` HTTP 200; log shows the listen line only.
- Through the hub (entry unchanged): `wled_get_service_status` version 0.4.0, streamable-http, profile
  `full`, backups writable; the hub's tool list includes the new tools without any hub change.
- `tools/list`: **37 tools** (33 in 0.3.0).
- Upgrade read of existing data: the existing device, 7 existing snapshots (all `restorable`,
  `invalid_count` 0), 0 groups, 0 scenes; the data checksum list was **identical** after the run.
- `wled_get_state` of the controller: firmware 16.0.1, master off, brightness 47, segment 0 unchanged.
- Counters: 6 calls, 6 read, 0 control, 0 manage, 0 failed. No controller was written.

## Hub, left on the target, limits

The hub entry needed and received **no change** (settings file byte-identical to its backup); no hub
reinstall; no fresh-install test (waiver ISSUE-24-DEC-005). Staged directory and image of 0.4.0 are in
use; 0.3.0, 0.2.0, 0.1.2 and the backups stay. Limits: one update of one deployment, no data-format
change between the releases, no write tool exercised on 0.4.0 (signal and preview tools not run on
hardware here; snapshots written by 0.4.0 not read by 0.3.0), rollback 0.4.0 to 0.3.0 not run.
