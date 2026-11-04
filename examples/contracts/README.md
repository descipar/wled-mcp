# Synthetic v1 contract examples

These JSON files illustrate the [tool contract](../../docs/TOOL-CONTRACT.md).
They are not runtime responses, executable tests, schema snapshots or observations
of an installed controller. Exception: `state.json` and `catalogs.json` hold the
actual output of the #5 tools against the synthetic mock transport (not firmware). IDs and names are synthetic. Internal fixture fields
such as `profile` and `expected` are not tool arguments.

| File | Observable assertion | Contract / future scenario |
| --- | --- | --- |
| [patch.json](patch.json) | False/zero are explicit, omitted state stays unchanged; dry-run has no device/filesystem writes | C2-01/04/06/10; T04/T07/T08 |
| [replace.json](replace.json) | Noncontiguous existing IDs, exact stale removal, preserved existing state, explicit new defaults; sparse creation rejected | C2-02/03/04/06/10; T05–T07/T09 |
| [preset.json](preset.json) | Lowest free slot, unknown occupied entry, full capture verification and explicit conflict | C2-07/08/10; T11/T13 |
| [errors.json](errors.json) | Unknown/mismatch application, backup failure, transition boundaries and MCP parity | C2-05/09/10; T06/T08/T09/T12–T14/T18 |
| [state.json](state.json) | #5 normalized state: explicit segment IDs, remembered vs effective brightness, trimmed zero white only for proven RGB-only, raw retained, redaction list; unknown device | C5-01/02/08; T02/T14/T15 |
| [catalogs.json](catalogs.json) | #5 catalogs: preserved IDs with `RSVD` placeholder, fxdata metadata, cache hit with age, metadata unavailable (length mismatch) | C5-03/05/06; T03 |
| [snapshot.json](snapshot.json) | Versioned exact saved object, unknown fields retained, no integrity/authenticity claim | C2-09; T12 |

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
