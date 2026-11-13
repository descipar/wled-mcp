# Deployment record: release 0.4.0 on the deployed target (2026-11-13)

One owner-authorized update of the deployed HTTP service from release 0.3.0 to the published
release 0.4.0, run by the coordinator session through the hub's SSH tool, following
[DEPLOYMENT.md](../DEPLOYMENT.md#http-service-update-rollback-recreation-removal) and the
[rollback checklist](issue-25-rollback-plan.md). Authority: owner instruction relayed by the
coordinator on 2026-11-13 (no permalink), scope this update only; the hub itself is never
reinstalled ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)). Hostnames,
paths and addresses are omitted ("the deployed target", "the hub"). Times UTC.

## Result

The update succeeded; **no rollback was run** (every check passed). The service now runs 0.4.0.
The rollback after this code-changing release (0.4.0 back to 0.3.0) was **not** exercised; its
source (image and staged directory of 0.3.0) was kept. The earlier rollback evidence (0.3.0 to
0.2.0 and back) is in the [launch report](launch-report.md#3-upgrade-and-rollback-evidence).

## Steps

| Step | Observation |
| --- | --- |
| Before (11:55) | image `wled-mcp:0.3.0` (ID `84c035bc0ec0`), healthy, profile `full`, one device; staged 0.1.2, 0.2.0, 0.3.0; images 0.2.0 and 0.3.0 |
| Backups | `compose.yaml` copied; hub settings file copied (mode 0600); data directory archived (root needed, mode 0600) and a SHA-256 list of its 9 files taken (equal to the list taken before the earlier rollback) |
| Source checked | published artifacts: wheel SHA-256 `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3`, sdist `a47dacf52ecb09f86d5bfa6ed0445cee038d974d8b5e29aedb35b8a4ae265afc`, neither yanked (PyPI, checked from outside); the annotated tag `v0.4.0` points at commit `5bd45b96eb4779cd73620dff2c7a1ee3c61a5e71` |
| Staging (DEC-026) | clean clone of the tag on the target (commit `5bd45b96…`, clean tree), `uv sync --locked`, `check_distribution.py` PASS (aarch64, 29 runtime versions), `deploy/stage_release.py`, `sha256sum -c SHA256SUMS` OK; `RELEASE`: version 0.4.0, that commit, tree clean |
| Wheel identity | the staged wheel SHA-256 equals the PyPI wheel SHA-256 above (byte-identical) |
| Image | `wled-mcp:0.4.0` built locally from the staged directory (ID `30e3b4d38d60`), never pushed |
| Switch (11:58:42) | `image:` changed from 0.3.0 to 0.4.0, `compose config --quiet` OK, `up -d --no-deps wled-mcp` returned after 2 s; `healthy` within 40 s |

## Verification on 0.4.0 (read-only against controllers)

- Authenticated `ping` from inside the container: HTTP 200, empty result. Log: the listen line only.
- Through the hub (entry unchanged): `wled_get_service_status` reported version 0.4.0, transport
  streamable-http, profile `full`, backups writable. The hub's tool list now includes the new tools
  (for example `wled_start_signal`, `wled_preview_layout`) without any change to the hub entry.
- `tools/list` served by the service: **37 tools** (33 in 0.3.0).
- Upgrade read of existing data: `wled_list_devices` listed the existing device;
  `wled_list_snapshots` listed the 7 existing snapshots (all `restorable`, `invalid_count` 0);
  `wled_list_groups` and `wled_list_scenes` returned 0 each, as before; the data directory
  checksum list was **identical** after the run.
- `wled_get_state` of the controller (one `GET /json/info`, one `GET /json/state`): firmware
  16.0.1, master off, brightness 47, segment 0 unchanged from the baseline of the earlier runs.
- The service's counters after the checks: 6 calls, 6 read, 0 control, 0 manage, 0 failed. No
  controller was written and the earlier test-controller write authorization was not used.

## Hub

The wled-mcp hub entry needed **no change** and was not changed; the hub settings file was
byte-identical to its backup. Nothing else on the hub was touched; no hub reinstall; no
fresh-install test (waiver ISSUE-24-DEC-005).

## Left on the target and limits

The staged directory and image of 0.4.0 are in use; those of 0.3.0, 0.2.0 and 0.1.2 and the
backup files stay (0.3.0 is the rollback source). The scratch clone and logs were removed.
Limits: one update of one deployment, no data-format change between the two releases, no write
tool exercised on 0.4.0 (so the new signal and preview tools were not run on hardware here, and
snapshots written by 0.4.0 were not read by 0.3.0), and the rollback 0.4.0 to 0.3.0 was not run.
