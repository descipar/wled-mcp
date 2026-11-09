# Effect and palette names in segment tools

Issue #149, NAME-01. `wled_patch_segments` and `wled_replace_layout` accept
`effect_name` and `palette_name` in each segment, as alternatives to `effect_id`
and `palette_id` respectively. A name must be nonblank; supplying both a name and
its ID is a validation error. Omitted fields retain the existing patch/layout
semantics.

Names resolve against the selected device's catalog under its operation lock and
deadline, before the complete request is planned and before any write. Resolution
uses a unique exact case-sensitive match first, then a unique case-folded trimmed
match. Reserved effect placeholders never match. Each required catalog kind is
loaded at most once per invocation, using the existing firmware-aware cache.
Numeric-only requests need no catalog reads.

An ambiguous name returns `AMBIGUOUS_NAME`; an unknown name returns
`VALIDATION_ERROR`. Both expose at most ten `{id,name}` entries in `data.candidates`
and the total in `data.candidate_total`. Unknown-name candidates are case-folded
substring suggestions, not automatic matches. Any unresolved name prevents every
write, including stale-segment removal during layout replacement.

Dry run and actual execution use the same resolution and planning path. The public
plan and readback postconditions contain numeric IDs. A later actual invocation
resolves again, so a changed device catalog may legitimately produce a different
ID from an earlier dry run. An acknowledgement without the expected ID in readback
is a verification mismatch, and uncertain writes retain the existing no-retry rule.

Example (configured synthetic controller ID):

```json
{"device_id":"desk","segments":[{"id":0,"effect_name":"Blink","palette_name":"Party"}],"dry_run":true}
```

Names refer to the device's real catalog. No prefix, substring or fuzzy suggestion
is applied, and no physical-device acceptance is claimed from automated mocks.
