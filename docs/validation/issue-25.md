# Issue #25: live H07 offline-controller check (2026-11-11)

One owner-authorized live check of H07 (behavior with an unreachable configured controller) on the
deployed Streamable HTTP service, as moved from #12 by ISSUE-12-DEC-007 item 6. Real device names and
addresses are omitted. The method is the approved one in [VALIDATION.md](../VALIDATION.md): no unplugging
of a production device and no networking change. Authorization: owner chat, 2026-11-11, bounded to this
run (temporary inventory entry and service restart), not standing permission.

## Target and procedure

- Release 0.1.2 HTTP service, profile `full`, device ceiling `manage`, one real controller (WLED
  16.0.1, ESP32-C3) plus a temporary device `h07-offline` at `http://192.0.2.1` (RFC 5737 documentation
  address, not routed), so no real device was touched.
- Steps: copy the inventory, `config add-device`, `config validate` (exit 0, 2 devices), restart only
  the service; read-only calls through the hub (no write tool called); restore the copy, validate
  (1 device), restart, confirm with a probe; temporary copies removed.

## Observations

| Check | Result |
| --- | --- |
| `wled_list_devices` without probe | both IDs listed, `probe_status: untested`, no network |
| `wled_list_devices` with probe | real controller `reachable`; `h07-offline` `failed`, `TIMEOUT`, `read_retryable: true`, `write_retryable: false`, reconciliation "Read the configured device explicitly; never replay the write." |
| `wled_get_state` on `h07-offline` | `ok: false`, `TIMEOUT`, `application: not_attempted` |
| `wled_get_state` on the real controller, same window | `ok: true`, unaffected |
| `wled_get_service_status` | `reachable: 1`, `failed: 1`; `error_code: TIMEOUT` for `h07-offline` |
| After rollback and restart | probe lists only the real controller, `reachable` |

The offline controller fails alone, with retryable-read and non-retryable-write classification, and does
not degrade the other controller (DEV-02, REL-01). Elapsed time per failing call was not measured.

## Limits

- One run, one build, one real controller; the target is a non-routed address (connect-timeout path),
  not a controller dropping mid-request (simulated T09 evidence only).
- No write was attempted against the offline entry; the not-attempted write path on hardware is covered
  by mocks only (REL-02).
- Closes only the H07 box of #25; other #25 acceptance items are not addressed.
