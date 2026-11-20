# Issue #25: live rollback checklist for the deployed target

Status: **executed once on 2026-11-13 (0.3.0 to 0.2.0 and back);** results are in the
[launch report](launch-report.md#3-upgrade-and-rollback-evidence). The checklist is kept as the
procedure that was followed. It covers acceptance item 1 of
[#25](https://github.com/descipar/wled-mcp/issues/25) (S2-COMPAT-03, live part) and follows
[DEPLOYMENT.md](../DEPLOYMENT.md#http-service-update-rollback-recreation-removal). All names, paths
and tags are placeholders.

The run restarts the deployed HTTP service twice (rollback, restore); the hub sees a short outage each
time. It touches only the `wled-mcp-http` Compose project and its `wled-mcp` service, never the hub or
its network. Authorization: the owner's instruction naming the target and this run
([ISSUE-25-DEC-003](../decisions/issue-25.md)); no publication, release, tag or registry step, and no
hub change other than backing up and restoring the wled-mcp entry.

## Preconditions

0. Observed 2026-11-13 (read-only): the target ran 0.3.0 (updated to 0.4.0 later, see
   [deploy-0.4.0.md](deploy-0.4.0.md)). The owner chose rollback target P = 0.2.0, staged on the target
   per DEC-026 (`deploy/stage_release.py` from a clean checkout of the tag; the PyPI wheel is not the
   staged artifact and its hash is not guaranteed equal). The hub is never reinstalled
   ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)); the hub entry may change
   only if verification needs it: back it up, restore it, record both states without hostnames.
1. A real rollback exists: release N runs and an older P is retained as image `wled-mcp:<tag-P>` and
   `/app/binaries/wled-mcp/<P>/` (or rebuildable there). Record both.
2. Quiet window: no tool call in flight, no active signal (stop sends SIGTERM, up to 130 s drain).
3. Only read tools are called; the service profile is unchanged.
4. Backups first, on the target and outside Git: `compose.yaml`, the inventory (also as
   `devices.toml.previous`) and the whole `data/wled-mcp` tree (`cp -a`). Record file counts and a
   checksum list of `backups/`, `groups/`, `scenes/` and the inventory.
5. Version compatibility: confirm in the CHANGELOG between P and N that no data or inventory format
   changed (0.2.0 to 0.3.0 changed none). If one did, stop and ask.
6. A rollback to a release with fewer tools may need the hub entry reloaded (expected from the
   tool-list refresh finding of [live-check-2026-11-08.md](live-check-2026-11-08.md), not observed).

## Steps

1. Record before: `ps`, current `image:` tag and ID, `logs --tail 50`, authenticated `ping`,
   `wled_get_service_status`, `wled_list_devices`, `wled_get_state` of one controller.
2. Validate the inventory with release P on a copy: `uvx --from wled-mcp==<P> wled-mcp config validate
   --config <copy> --data-dir <copy-dir>`.
3. Set `image:` to `wled-mcp:<tag-P>`; `docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps
   wled-mcp`.
4. Verify on P: `ps`, logs (startup line, no configuration error, no `BACKUPS_NOT_WRITABLE`), `ping`
   HTTP 200, hub entry reloaded if needed, tool count equals P's, devices, state, groups, scenes and
   snapshots written by N present, service status.
5. Prove no controller write: call counters and log lines show only `class=read` calls; the data
   directory checksum list is unchanged.
6. Restore `image:` to N, repeat the command and step 4, record health.
7. Keep both images and release directories; remove only scratch copies outside the data tree. Never
   prune backups.

## What to record

Versions N and P with build provenance (tag, source commit, wheel SHA-256), the exact commands in
order, time from `up -d` to the first `ping` for each switch, tool counts, outcomes of steps 1, 4 and
6, the step-5 proof, the data directory comparison, deviations from DEPLOYMENT.md, and what was not
run. Use "the deployed target"; no hostnames, addresses, paths or tokens.

## Stop conditions

Stop and report when: no older release is retained or buildable; the service is not ready on P and the
previous `compose.yaml` does not bring it back at once (restore N immediately); a data or inventory
format differs between N and P; the run would need a new artifact, tag or publication.
