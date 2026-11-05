# Synthetic v1 contract examples

These JSON files illustrate the [tool contract](../../docs/TOOL-CONTRACT.md).
They are not runtime responses, executable tests, schema snapshots or observations
of an installed controller. Exception: `state.json` and `catalogs.json` hold the
actual output of the #5 tools, and `replace.json` plus the `replace_layout_partial_application`
case in `errors.json` hold the actual #7 output (checked by `tests/test_layouts.py`) against the synthetic mock transport (not firmware). `presets.json` and the `backup_failure` case in `errors.json` hold actual #9 output (checked by `tests/test_presets.py`) against the stateful preset mock; `preset.json` stays a design illustration whose `data` shape differs from the implemented result. IDs and names are synthetic. Internal fixture fields
such as `profile` and `expected` are not tool arguments.

| File | Observable assertion | Contract / future scenario |
| --- | --- | --- |
| [patch.json](patch.json) | False/zero are explicit, omitted state stays unchanged; dry-run has no device/filesystem writes | C2-01/04/06/10; T04/T07/T08 |
| [replace.json](replace.json) | Actual `wled_replace_layout` dry-run output (stateful mock): noncontiguous existing IDs, exact stale removal with `step_payloads`, preserved existing state, explicit new defaults; sparse creation rejected | C2-02/03/04/06/10; T05–T07/T09 |
| [preset.json](preset.json) | Design illustration: lowest free slot, unknown occupied entry, full capture verification and explicit conflict | C2-07/08/10; T11/T13 |
| [presets.json](presets.json) | Actual #9 output: list with types, exact unknown entry, empty slot, occupied-without-overwrite conflict, activation and delete dry runs | C2-07; T11/T12 |
| [errors.json](errors.json) | Unknown/mismatch application, #7 partial layout application, backup failure, transition boundaries and MCP parity | C2-05/09/10; T06/T08/T09/T12–T14/T18 |
| [state.json](state.json) | #5 normalized state: explicit segment IDs, remembered vs effective brightness, trimmed zero white only for proven RGB-only, raw retained, redaction list; unknown device | C5-01/02/08; T02/T14/T15 |
| [catalogs.json](catalogs.json) | #5 catalogs: preserved IDs with `RSVD` placeholder, fxdata metadata, cache hit with age, metadata unavailable (length mismatch) | C5-03/05/06; T03 |
| [snapshot.json](snapshot.json) | Versioned exact saved object (validated by `tests/test_backups.py`), unknown fields retained, no integrity/authenticity claim | C2-09; T12 |

`expected` values are normalized domain envelopes. MCP wraps them in
`structuredContent` and an equivalent JSON text block; `isError` is the inverse
of `ok`. A dry-run success has `application=not_attempted`, never `applied`.
Fields in `postconditions` describe what later adapter tests must assert.

The replacement fixture assumes proven slot allocation and main-ID redirection.
Its sequence removes conflicting old ranges before moving/creating segments, and
uses single-object removal to avoid the reviewed firmware's array purge behavior.
A real adapter must prove that profile before accepting it. Failure midway is
partial/uncertain application, not a transaction. T18–T21 add transport/access/
lifecycle execution coverage; no network or hardware behavior was tested here.
