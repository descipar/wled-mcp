# Issue #61 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-61-DEC-001 — Accept underscores in `base_url` host labels

- ID: ISSUE-61-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #61 only.
- Authority/source: human decision, owner answer 2026-11-06 choosing issue option A
  ("Unterstrich erlauben", English: "allow underscore") over option B; no permalink.
- Scope: `base_url` host validation in `src/wled_mcp/config.py`, tests and inventory docs.
- Decision: an underscore is accepted in DNS host labels of a device `base_url`. Everything else
  stays fail-closed: userinfo, query, fragment, path, whitespace and percent-encoding remain
  rejected; IP-literal handling unchanged; no discovery or name scanning. A rejected inventory
  names the offending device entry without echoing secrets.
- Conditions: label rules beyond the underscore are technical proposals (DEC-002).

## ISSUE-61-DEC-002 — Host label rules and device-locating error message

- ID: ISSUE-61-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #61 only; technical proposals TD-61-1 to TD-61-9 accepted by the
  coordinator, not a human decision; the owner may veto at review.
- Decision:
  - TD-61-1 to TD-61-6: label characters `[A-Za-z0-9_-]`, ASCII only, at most 253 characters,
    each label 1–63 characters starting and ending with a letter or digit (underscore-only
    labels rejected); no special rule for last or single labels; IP-literal, IPv6, case and
    normalization handling unchanged.
  - TD-61-7: the diagnostic locates entries only from the validation error location, as
    `devices[<zero-based index>]` plus the field (`id`, `name`, `base_url`; unknown key reported
    as unsupported field without its name); at most five locators; never value, URL, host or
    exception text. Non-device errors keep the generic message.
  - TD-61-8: the device id is not shown. TD-61-9: probe script and `--allowed-host` out of scope.
- Conditions: revisit if an HTTP library upgrade starts IDNA-encoding ASCII hosts (guarded by a
  client-level test). Refines DEC-001.
