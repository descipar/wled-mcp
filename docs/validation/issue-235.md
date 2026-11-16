# Issue #235: slim served tool schemas and token budget

Evidence for the acceptance criteria of [#235](https://github.com/descipar/wled-mcp/issues/235)
(milestone M9, DEC-028). Scope: shrink what `tools/list` serves without changing behavior. No
tool, name, annotation, field name, validation rule or result changed; no device or LAN was
contacted (in-memory servers, mocks only). Hardware is not part of this issue.

## What changed

1. **Slim schemas.** `src/wled_mcp/schema_slim.py` removes two annotations from each generated
   schema before it is served (input schemas and the shared output schema): the generated
   `title` of every schema node, and `"default": null` on a nullable (`anyOf` with `null`)
   optional field. A property that is literally named `title` stays (the helper never touches a
   key of a `properties` or `$defs` mapping), and `default`, `enum`, `const` and `examples`
   values are copied as they are. Everything else is byte-equal: types, `anyOf`, bounds,
   `required`, `additionalProperties`, descriptions and non-null defaults such as
   `default: false`. Validation uses the pydantic models, which are untouched, so an omitted
   nullable field and an explicit `null` are accepted exactly as before.
2. **Tighter descriptions.** The signal tools use shorter description texts (the longer
   `TIMING_NOTE` and `NO_PERSISTENCE_NOTE` stay as the warnings of results, which are unchanged).
   The repeated trailer "Overwriting replaces the destination's previous stored entry after a
   snapshot." is removed from the five tools that already state "needs overwrite=true and is
   snapshotted first". Smaller rewordings in `wled_apply_scene`, `wled_apply_zone`, `wled_plan_zone`,
   `wled_save_scene` and the segment model docstrings (issue numbers and document paths removed). Every safety statement
   and mandatory rule stays: `Use dry_run=true when the requested replacement or deletion is
   unclear.` on every destructive tool, the LIVE EFFECT warnings, never-replayed and uncertain
   statements, exclusive stops, the `overwrite`/`allow_overlap` requirements, "omitted means
   unchanged" and the capability evidence rules. The 36 segment field descriptions were
   reviewed and kept as they are: they average about 60 characters and each carries a contract
   rule (exclusive stop, "omit to preserve", capability or field evidence, device-specific IDs),
   so the saving there comes from dropping titles and `default: null` (the segment schema
   appears in three tools).
3. **Guard.** `tests/test_tool_budget.py` enforces a per-tool and a per-profile size budget
   and checks that the served guidance resolves every tool and field reference it makes.

Not done on purpose: tool groups or per-endpoint tool sets (tracked separately), flattening of
`anyOf` (it would narrow what is advertised and break the retained 0.1.0 comparison) and
dropping non-null defaults (informative; a changed default is breaking, see
[versioning](../contract/versioning.md)).

## Method

The server is built in memory for each profile (`tests.test_access_profiles.served`) and the
listing is read through an MCP client. The size of a tool is the number of characters of
compact JSON (`separators=(",", ":")`, non-ASCII kept) of its `name`, `description` and
`inputSchema`, which is what a client sends to the model with every request; the output schema
is reported separately. Tokens are approximated at 4 characters per token. Before values are
`origin/main` at `29b6c54`, after values are this change. The budget test uses the same measure.

## Per profile

| Profile | Tools | Before (chars) | Before (about tokens) | After slim helper only | After (chars) | After (about tokens) | Saved | Output schemas before | Output schemas after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `full` | 37 | 70926 | 17731 | 61762 | 60572 | 15143 | 10354 (14.6 %) | 67118 | 53095 |
| `control` | 27 | 51119 | 12779 | 44693 | 43933 | 10983 | 7186 (14.1 %) | 48978 | 38745 |
| `read-only` | 19 | 24343 | 6085 | 21144 | 21036 | 5259 | 3307 (13.6 %) | 34466 | 27265 |

For the `full` profile the descriptions went from 19102 to 18072 characters and the input
schemas from 51031 to 41707 characters. The output schema is the shared result envelope and is
served once per tool; it shrinks by the same title and default removal and is not trimmed
further.

## Per tool (profile `full`, sorted by size before)

| Tool | Before (chars) | After (chars) | After (about tokens) | Saved | Description before | Description after |
| --- | --- | --- | --- | --- | --- | --- |
| `wled_preview_layout` | 8750 | 7385 | 1846 | 1365 | 725 | 725 |
| `wled_replace_layout` | 8638 | 7323 | 1830 | 1315 | 724 | 724 |
| `wled_patch_segments` | 8470 | 7038 | 1759 | 1432 | 380 | 380 |
| `wled_store_preset` | 5805 | 4427 | 1106 | 1378 | 738 | 659 |
| `wled_start_signal` | 2806 | 2525 | 631 | 281 | 1528 | 1379 |
| `wled_save_scene` | 2730 | 2495 | 623 | 235 | 724 | 689 |
| `wled_save_playlist` | 2459 | 2061 | 515 | 398 | 841 | 762 |
| `wled_import_presets` | 2365 | 2056 | 514 | 309 | 1120 | 1041 |
| `wled_search_effects` | 2087 | 1653 | 413 | 434 | 415 | 415 |
| `wled_apply_zone` | 1997 | 1884 | 471 | 113 | 953 | 934 |
| `wled_save_group` | 1863 | 1673 | 418 | 190 | 423 | 423 |
| `wled_plan_zone` | 1801 | 1696 | 424 | 105 | 864 | 849 |
| `wled_apply_scene` | 1679 | 1533 | 383 | 146 | 991 | 925 |
| `wled_explain_lighting` | 1541 | 1309 | 327 | 232 | 328 | 328 |
| `wled_set_state` | 1455 | 1288 | 322 | 167 | 243 | 243 |
| `wled_save_preset` | 1296 | 1081 | 270 | 215 | 694 | 615 |
| `wled_restore_preset` | 1265 | 1042 | 260 | 223 | 705 | 626 |
| `wled_get_effects` | 1102 | 934 | 233 | 168 | 301 | 301 |
| `wled_cancel_signal` | 1083 | 748 | 187 | 335 | 771 | 489 |
| `wled_plan_scene` | 1077 | 1016 | 254 | 61 | 634 | 634 |
| `wled_list_scenes` | 964 | 856 | 214 | 108 | 386 | 386 |
| `wled_export_presets` | 961 | 845 | 211 | 116 | 482 | 482 |
| `wled_get_signal_status` | 905 | 765 | 191 | 140 | 517 | 448 |
| `wled_list_zones` | 767 | 710 | 177 | 57 | 454 | 454 |
| `wled_delete_preset` | 741 | 653 | 163 | 88 | 372 | 372 |
| `wled_get_live_snapshot` | 679 | 610 | 152 | 69 | 246 | 246 |
| `wled_delete_group` | 663 | 597 | 149 | 66 | 252 | 252 |
| `wled_activate_preset` | 648 | 558 | 139 | 90 | 275 | 275 |
| `wled_list_snapshots` | 632 | 546 | 136 | 86 | 293 | 293 |
| `wled_delete_scene` | 620 | 554 | 138 | 66 | 209 | 209 |
| `wled_list_groups` | 579 | 517 | 129 | 62 | 307 | 307 |
| `wled_get_preset` | 510 | 443 | 110 | 67 | 210 | 210 |
| `wled_list_presets` | 447 | 398 | 99 | 49 | 232 | 232 |
| `wled_get_palettes` | 436 | 370 | 92 | 66 | 159 | 159 |
| `wled_get_state` | 418 | 372 | 93 | 46 | 209 | 209 |
| `wled_get_service_status` | 405 | 374 | 93 | 31 | 285 | 285 |
| `wled_list_devices` | 282 | 237 | 59 | 45 | 112 | 112 |

The five largest tools after the change are `wled_preview_layout`, `wled_replace_layout`,
`wled_patch_segments`, `wled_store_preset` and `wled_start_signal`. The three segment tools
stay large because the segment schema (36 optional nullable fields, each an `anyOf`) appears in
each of them; trimming that further needs a change of what is advertised and is outside this
issue.

## Budget

`tests/test_tool_budget.py` holds one limit per tool and one per profile, about 3 percent above
the values in the tables. A new tool without a limit, or growth over a limit, fails the test
with the instruction to raise the number deliberately and to update this document with the new
measurement.

## Validation

Mocks and in-memory servers only; no device was contacted.

| Check | Result |
| --- | --- |
| `uv run pytest -q -n auto` | 3570 passed, 47 skipped (platform and opt-in checks) |
| `uv run ruff check` and `ruff format --check` on the CI file list, `ruff check src --select S --ignore S101` | pass |
| `uv run mypy` | no issues in 60 source files |
| `uv run python scripts/sync_agents.py --check`, `scripts/check_agent_setup.py`, `scripts/check_lock.py` | pass |
| `uv run pytest -q tests/test_version_source.py` | 38 passed |
| `uv run python scripts/check_distribution.py` | PASS (wheel, clean install, stdio, HTTP, uvx) |

| Acceptance criterion | Evidence |
| --- | --- |
| Titles and redundant defaults dropped, behavior unchanged | `tests/test_schema_slim.py`; `tests/test_tools_list_cache.py` (served equals the slimmed generation, annotations and descriptions equal the operations); `tests/test_tool_budget.py::test_served_schemas_carry_no_generated_titles_or_null_defaults`; the contract, parity and 0.1.0 compatibility tests unchanged except for the one rule below |
| Longest descriptions tightened without losing a safety statement | tables above; the existing phrase assertions (`tests/test_agent_guidance.py`, `tests/test_signal_tools.py`, `tests/test_scene_apply.py`, LIVE EFFECT tests) pass unchanged |
| Before and after measurement recorded | this document |
| Budget enforced by test | `tests/test_tool_budget.py` |
| Served guidance still resolves tool and field references | `tests/test_tool_budget.py::test_served_guidance_resolves_every_tool_and_field_reference` (checked to fail on a mutated tool name) |

The compatibility comparison against the retained 0.1.0 listing (`tests/test_upgrade_compat.py`)
treats a dropped `default: null` of a nullable optional field as non-breaking (an omitted field
already means no value); a dropped or changed non-null default, a `default: null` dropped from a
non-nullable node and a changed default still break, with their own controls.

## Limits

- The number of tokens is an approximation (4 characters per token); real tokenizers differ.
- Clients that cached a schema served before this change see the same fields, types, bounds and
  required lists; only titles and `default: null` are gone. Behavior of the server does not
  depend on the served schema.
- No client-side measurement of a real MCP host was made.

## Rooms (#183)

Rooms add one tool and a few fields, so the budget was raised on purpose (the test message asks
for exactly this). Same method as above; mocks and in-memory servers only. Before values are
`main` at `e766976`.

| Profile | Tools before | Tools after | Before (chars) | After (chars) | Growth | New limit |
| --- | --- | --- | --- | --- | --- | --- |
| `full` | 37 | 38 | 60572 | 63676 | 3104 (5.1 %, about 780 tokens) | 65000 |
| `control` | 27 | 28 | 43933 | 46782 | 2849 | 47800 |
| `read-only` | 19 | 19 | 21036 | 21415 | 379 | 21700 (unchanged) |

| Tool | Before (chars) | After (chars) | New limit | What grew |
| --- | --- | --- | --- | --- |
| `wled_apply_room` | - | 2246 | 2300 | new tool: `room`, `state` (3 fields), `scene_id`, `mode`, `dry_run` and the description |
| `wled_save_group` | 1673 | 1928 | 2000 | `kind` and one description sentence |
| `wled_plan_zone` | 1696 | 1914 | 1950 | optional `room` and one sentence |
| `wled_apply_zone` | 1884 | 2108 | 2150 | optional `room` and one sentence |
| `wled_list_groups` | 517 | 604 | 650 | one sentence (`kind`, conflicts) |
| `wled_list_devices` | 237 | 311 | 350 | one sentence (`room`, unusable store never fails the list) |

The served `instructions` and the prompt grew by one sentence (about 330 characters, outside the
per-tool measure). Why the cost is justified: the extension-only variant (no new tool) could not
deliver the state patch to a room that the acceptance criteria require, and no separate plan tool
was added (about 1200 more characters): `dry_run=true` on the apply is the preview. The three
tools that are not new stayed within about 14 percent of their previous size. If the tool-group
work of M9 (#236) or the segment schema simplification (#246) merge, the limits move again.

Checks: `uv run pytest tests/test_tool_budget.py` (per-tool and per-profile limits, the guidance
resolution test) passes with the numbers above.
