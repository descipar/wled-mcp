# Issue #235: slim served tool schemas and token budget

Evidence for [#235](https://github.com/descipar/wled-mcp/issues/235) (milestone M9, DEC-028). Scope:
shrink what `tools/list` serves without changing behavior; no tool, name, annotation, field name,
validation rule or result changed. Mocks and in-memory servers only; no device or LAN contact.

## What changed

1. **Slim schemas.** `src/wled_mcp/schema_slim.py` removes the generated `title` of every schema
   node and `"default": null` on nullable optional fields before serving (input schemas and the
   shared output schema). A property literally named `title` stays; `default`, `enum`, `const` and
   `examples` values are copied. Validation uses the untouched pydantic models.
2. **Tighter descriptions.** Shorter signal tool texts, a repeated overwrite trailer removed from
   five tools, small rewordings in scene, zone and segment texts. Every safety statement stays
   (`dry_run=true` hint on destructive tools, LIVE EFFECT warnings, never-replayed and uncertain
   statements, `overwrite`/`allow_overlap`, "omitted means unchanged", capability evidence rules).
   The 36 segment field descriptions were reviewed and kept.
3. **Guard.** `tests/test_tool_budget.py` enforces a per-tool and per-profile size budget and checks
   that served guidance resolves every tool and field it names.

Not done: tool groups (tracked separately), flattening `anyOf`, dropping non-null defaults.

## Method

Servers built in memory per profile, read through an MCP client. Size = characters of compact JSON of
`name`, `description` and `inputSchema` (output schema reported separately); about 4 characters per
token. Before = `origin/main` at `29b6c54`.

## Per profile

| Profile | Tools | Before (chars) | After (chars) | After (about tokens) | Saved | Output schemas before / after |
| --- | --- | --- | --- | --- | --- | --- |
| `full` | 37 | 70926 | 60572 | 15143 | 10354 (14.6 %) | 67118 / 53095 |
| `control` | 27 | 51119 | 43933 | 10983 | 7186 (14.1 %) | 48978 / 38745 |
| `read-only` | 19 | 24343 | 21036 | 5259 | 3307 (13.6 %) | 34466 / 27265 |

Five largest tools after the change (`full`, chars): `wled_preview_layout` 7385, `wled_replace_layout`
7323, `wled_patch_segments` 7038, `wled_store_preset` 4427, `wled_start_signal` 2525. The segment tools
stay large because the 36-field segment schema appears in each; trimming it needs a change of what is
advertised and is out of scope. The largest per-tool savings were `wled_store_preset` 1378,
`wled_patch_segments` 1432, `wled_preview_layout` 1365 and `wled_replace_layout` 1315.

## Budget

`tests/test_tool_budget.py` holds one limit per tool and per profile, about 3 percent above the
measurements. A new tool without a limit, or growth over a limit, fails with the instruction to raise
the number deliberately and update this document.

## Validation

| Check | Result |
| --- | --- |
| `uv run pytest -q -n auto` | 3570 passed, 47 skipped (platform and opt-in checks) |
| `ruff check`, `ruff format --check`, `ruff check src --select S --ignore S101`, `mypy` | pass (mypy: 60 source files) |
| `sync_agents.py --check`, `check_agent_setup.py`, `check_lock.py`, `tests/test_version_source.py` | pass (38 passed) |
| `scripts/check_distribution.py` | PASS (wheel, clean install, stdio, HTTP, uvx) |

| Acceptance criterion | Evidence |
| --- | --- |
| Titles and redundant defaults dropped, behavior unchanged | `tests/test_schema_slim.py`; `tests/test_tools_list_cache.py`; `tests/test_tool_budget.py::test_served_schemas_carry_no_generated_titles_or_null_defaults`; contract, parity and 0.1.0 compatibility tests unchanged except one rule below |
| Longest descriptions tightened without losing a safety statement | existing phrase assertions (`test_agent_guidance.py`, `test_signal_tools.py`, `test_scene_apply.py`, LIVE EFFECT tests) pass unchanged |
| Before and after measurement recorded | this document |
| Budget enforced by test | `tests/test_tool_budget.py` |
| Served guidance still resolves tool and field references | `test_served_guidance_resolves_every_tool_and_field_reference` (fails on a mutated tool name) |

`tests/test_upgrade_compat.py` treats a dropped `default: null` of a nullable optional field as
non-breaking; dropped or changed non-null defaults still break.

## Limits

Token counts are approximations; no client-side measurement of a real MCP host; clients that cached an
older schema see the same fields, types, bounds and required lists.

## Rooms (#183)

One new tool and a few fields; budget raised on purpose. Before = `main` at `e766976`.

| Profile | Tools before / after | Before (chars) | After (chars) | Growth | New limit |
| --- | --- | --- | --- | --- | --- |
| `full` | 37 / 38 | 60572 | 63676 | 3104 (5.1 %, about 780 tokens) | 65000 |
| `control` | 27 / 28 | 43933 | 46782 | 2849 | 47800 |
| `read-only` | 19 / 19 | 21036 | 21415 | 379 | 21700 |

New tool `wled_apply_room` 2246 chars (limit 2300); growth in `wled_save_group` (`kind`), `wled_plan_zone`
and `wled_apply_zone` (optional `room`), `wled_list_groups` and `wled_list_devices` (one sentence each).
Served instructions grew by about 330 characters. No separate plan tool: `dry_run=true` is the preview.
Check: `uv run pytest tests/test_tool_budget.py` passes.

## Discovery tool (#200)

`wled_discover_devices` is a read tool served in every profile. Before = `main` at `40bf74b`.

| Profile | Tools before / after | Before (chars) | After (chars) | Growth | New limit |
| --- | --- | --- | --- | --- | --- |
| `full` | 38 / 39 | 63676 | 64639 | 963 | 66000 |
| `control` | 28 / 29 | 46782 | 47745 | 963 | 48800 |
| `read-only` | 19 / 20 | 21415 | 22378 | 963 | 22400 |

Tool measured 963 chars (limit 1000). `tests/test_tool_budget.py` passes.

## Discovery ranges tool (#202)

`wled_set_discovery_ranges` (`manage`, `full` profile only). Before = `main` at `ffe87ed`.

| Profile | Tools before / after | Before (chars) | After (chars) | Growth | New limit |
| --- | --- | --- | --- | --- | --- |
| `full` | 39 / 40 | 64639 | 65404 | 765 | 66800 |

Tool measured 765 chars (limit 800). `tests/test_tool_budget.py` passes.

## Enrollment tool (#203)

`wled_add_device` (`manage`, `full` profile only). Before = `main` at `a901b2a`.

| Profile | Tools before / after | Before (chars) | After (chars) | Growth | New limit |
| --- | --- | --- | --- | --- | --- |
| `full` | 40 / 41 | 65404 | 66561 | 1157 | 68000 |

Tool measured 1157 chars (limit 1200). `tests/test_tool_budget.py` passes.
