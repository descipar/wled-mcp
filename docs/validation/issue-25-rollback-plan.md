# Issue #25: live rollback checklist for the deployed target

Status: **executed once on 2026-11-13 (0.3.0 to 0.2.0 and back);** the results are in the [launch report](launch-report.md#3-upgrade-and-rollback-evidence). The checklist below is kept as the procedure that was followed; the data backup needs root (files belong to the container UID). This is the procedure for acceptance item 1 of
[#25](https://github.com/descipar/wled-mcp/issues/25) (S2-COMPAT-03, live part). It follows
[DEPLOYMENT.md](../DEPLOYMENT.md#http-service-update-rollback-recreation-removal) and adds only
preconditions and recording. All names, paths and tags are placeholders. Status of the attempt:
[launch report, section 3](launch-report.md#3-upgrade-and-rollback-evidence).

The run restarts the deployed HTTP service twice (rollback, restore) and the hub sees a short
outage each time. It touches only the `wled-mcp-http` Compose project and its `wled-mcp` service,
never the hub or its network. Authorization needed: the owner's instruction naming the target and
this run (restart and rollback). No publication, release, tag or registry step and no hub change other than backing up and restoring the wled-mcp entry is part of it (authorization: [ISSUE-25-DEC-003](../decisions/issue-25.md)).

## Preconditions

0. **Observed 2026-11-13 (read-only) and decided.** The target ran 0.3.0 at that time (it was updated to 0.4.0 later, see
   [deploy-0.4.0.md](deploy-0.4.0.md)) with only the image of
   0.3.0 and the retained staged directories of 0.3.0 and 0.1.2. The owner chose rollback target P =
   **0.2.0**, which first has to be staged on the target. DEC-026 stages a release on the target
   machine with `deploy/stage_release.py` from a clean checkout of the tag `v0.2.0`, which also
   writes `SHA256SUMS` and `RELEASE` and copies the wheel built from that checkout by
   `scripts/check_distribution.py`; the wheel on PyPI is not the staged artifact. Confirm that this (checkout of the tag, then compare the staged wheel
   hash with the PyPI wheel hash of 0.2.0, which `stage_release.py` does not guarantee to equal) is
   what "stage from PyPI" meant. The image `wled-mcp:0.2.0` is then built from that directory.
   The hub itself is never reinstalled ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).
   The wled-mcp hub entry may be changed only if the verification needs it (ISSUE-25-DEC-003):
   back it up first, restore it at the end, record both states without hostnames or addresses;
   otherwise leave it untouched and say so. Verify on the target directly (and read-only through
   the hub).

1. **A real rollback exists.** The target runs release **N** and an older release **P** is
   retained as image `wled-mcp:<tag-P>` and as `/app/binaries/wled-mcp/<P>/` (or can be rebuilt
   there from the retained directory, staged on the target per DEC-026). Record both. If the target
   runs the oldest retained release, first update it to the next published release (the update
   procedure of DEPLOYMENT.md, an existing release, nothing new published) and use that as N.
2. **Quiet window.** No tool call in flight and no active temporary signal; stop of the service
   sends SIGTERM with up to 130 s drain.
3. **Controller safety.** Only read tools are called during the run. The service profile is not
   changed (that would alter the deployed configuration).
4. **Backups first**, on the target, outside Git: copy `compose.yaml`, the inventory
   `data/wled-mcp/config/devices.toml` (also as `devices.toml.previous`) and the whole
   `data/wled-mcp` tree (use `cp -a`; keep it read-only afterwards). Record file counts and a
   checksum list of `backups/`, `groups/`, `scenes/` and the inventory.
5. **Version compatibility.** Confirm in the CHANGELOG between P and N that no data or inventory
   format changed (0.2.0 to 0.3.0 changed none; `config validate` and `doctor` exist on 0.1.2, 0.2.0
   and 0.3.0). If a format changed, stop and ask: the older server rejects newer data.
6. Note the hub entry's cached tool list: a rollback to a release with fewer tools may need the hub
   entry reloaded (expected from the tool-list refresh finding of [live-check-2026-11-08.md](live-check-2026-11-08.md), **not observed**).

## Steps

1. Record before: `docker compose -p wled-mcp-http -f compose.yaml ps`, current `image:` tag, image
   ID, `logs --tail 50`, authenticated `ping`, `wled_get_service_status` (profile, per-device state,
   counters) and `wled_list_devices`, `wled_get_state` of one controller (read only).
2. Validate the inventory with release P without touching the running service, for example on a
   copy: `uvx --from wled-mcp==<P> wled-mcp config validate --config <copy> --data-dir <copy-dir>`
   (exits 0 when accepted; no device contact).
3. Change `image:` in `compose.yaml` to `wled-mcp:<tag-P>`; run
   `docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps wled-mcp`.
4. Verify on P: `ps`, `logs --tail 50` (startup line, no configuration error, no
   `BACKUPS_NOT_WRITABLE`), authenticated `ping` (HTTP 200, empty result), the hub entry reloaded if
   needed, `tools/list` count equals P's, `wled_list_devices` shows the existing devices,
   `wled_get_state` of one controller `ok`, `wled_list_groups`, `wled_list_scenes` and
   `wled_list_snapshots` show the data written by N, `wled_get_service_status`.
5. Prove nothing was written to a controller: the call counters and per-call log lines of the run
   show only read-class calls (`class=read`, no `application=applied`; an older target may log in another format, then use the status tool's per-class counters); the data directory checksum
   list of step 4 of the preconditions is unchanged by the reads.
6. Restore: set `image:` back to `wled-mcp:<tag-N>`, repeat the `up -d --no-deps` command, then repeat
   step 4 (counts equal N's) and record that the service is healthy.
7. Clean up: keep both images and both release directories; remove only scratch copies the run made
   outside the data tree. Never prune backups.

## What to record (sanitized, in the launch report)

Versions N and P and how they were built (tag, source commit, wheel SHA-256 as in the operations
record), the exact commands in the order run, time from `up -d` to the first successful `ping` for
each switch, tool counts, the outcomes of steps 1, 4 and 6, the proof of step 5, the data
directory comparison, anything that differed from DEPLOYMENT.md (with the corrected text), and
what was not run. Use "the deployed target"; no hostnames, addresses, paths or tokens.

## Stop conditions

Stop and report instead of improvising when: no older release is retained or buildable from a
retained directory; the service does not become ready on P and the previous `compose.yaml` does not
bring it back at once (restore N immediately); a data or inventory format differs between N and P;
the run would need a new artifact, tag or publication.
