# Effect and palette names in segment tools

Issue #149, NAME-01. `wled_patch_segments` and `wled_replace_layout` accept `effect_name` and
`palette_name` per segment as alternatives to `effect_id` and `palette_id`. A name must be nonblank;
supplying a name and its ID together is a validation error. Omitted fields keep the existing
patch/layout semantics.

Names resolve against the selected device's catalog under its operation lock and deadline, before
the complete request is planned and before any write: a unique exact case-sensitive match first,
then a unique case-folded trimmed match. Reserved effect placeholders never match. Each required
catalog kind is loaded at most once per invocation through the firmware-aware cache; numeric-only
requests need no catalog reads.

An ambiguous name returns `AMBIGUOUS_NAME`; an unknown name `VALIDATION_ERROR`. Both expose at most
ten `{id,name}` entries in `data.candidates` and the total in `data.candidate_total`. Unknown-name
candidates are case-folded substring suggestions, never automatic matches. Any unresolved name
prevents every write, including stale-segment removal during layout replacement.

Dry run and execution share resolution and planning. Plans and readback postconditions contain
numeric IDs; a later invocation resolves again, so a changed device catalog may give a different ID
than an earlier dry run. An acknowledgement without the expected ID in readback is a verification
mismatch; uncertain writes keep the no-retry rule.

```json
{"device_id":"desk","segments":[{"id":0,"effect_name":"Blink","palette_name":"Party"}],"dry_run":true}
```

No prefix, substring or fuzzy matching is applied, and no physical-device acceptance is claimed from
mocks.
