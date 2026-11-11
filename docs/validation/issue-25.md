# Issue #25: live H07 offline-controller check (2026-11-11)

One owner-authorized live check of H07 (behavior with an unreachable configured controller) on the
deployed Streamable HTTP service, as moved from #12 by ISSUE-12-DEC-007 item 6. Host names,
addresses of real devices, paths and the controller's name are omitted. The permitted method is the
one in [VALIDATION.md](../VALIDATION.md): an approved test method that does not unplug a production
device or change networking.

## Authorization

Owner chat authority on 2026-11-11 (no permalink): run the H07 check, including the temporary
inventory entry and the service restart that the #25 text names as needing its own authorization.
Bounded to this run; not standing permission.

## Target

- Deployed HTTP service, release 0.1.2, access profile `full`, device ceiling `manage`, one real
  controller (WLED 16.0.1, ESP32-C3) plus the temporary entry below.
- Temporary device `h07-offline` with `base_url = http://192.0.2.1`, a reserved documentation address
  (RFC 5737) that is not routed, so no real device was touched or disconnected.

## Procedure

1. Copy the working inventory, add the entry with `wled-mcp config add-device`, run
   `wled-mcp config validate` (exit 0, 2 devices), restart only the service container.
2. Read-only observations through the hub: `wled_list_devices` with and without `probe`,
   `wled_get_state` on both devices, `wled_get_service_status`. No write tool was called.
3. Restore the copy, validate (1 device), restart, confirm with a probe. The temporary copies were
   removed afterwards.

## Observations

| Check | Result |
| --- | --- |
| `wled_list_devices` without probe | both IDs listed, `probe_status: untested`, no network |
| `wled_list_devices` with probe | real controller `reachable`; `h07-offline` `failed`, error `TIMEOUT`, `read_retryable: true`, `write_retryable: false`, reconciliation text "Read the configured device explicitly; never replay the write." |
| `wled_get_state` on `h07-offline` | `ok: false`, `TIMEOUT`, `application: not_attempted` |
| `wled_get_state` on the real controller in the same window | `ok: true`, normal full state; unaffected by the failing entry |
| `wled_get_service_status` | readiness counts `reachable: 1`, `failed: 1`; per-device `error_code: TIMEOUT` for `h07-offline` |
| After rollback and restart | probe lists only the real controller, `reachable` |

The offline controller fails alone, with a retryable-read and non-retryable-write classification, and
does not degrade the other controller (DEV-02, REL-01). The elapsed time per failing call was not
measured in this run.

## Limits

- One run, one service build, one real controller; the unreachable target is a non-routed address,
  not a controller that went offline mid-session. It shows the connect-timeout path, not a
  mid-request drop; the latter stays with the simulated T09 evidence.
- No write was attempted against the offline entry, so the not-attempted write path on hardware is
  not exercised here (covered by the mocked tests in REL-02).
- This closes only the H07 box of #25. The other #25 acceptance items are not addressed.
