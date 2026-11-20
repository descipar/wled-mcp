# Issue #20 validation evidence

Evidence for [issue #20](https://github.com/descipar/wled-mcp/issues/20). Contracts:
[contract/profiles.md](../contract/profiles.md) and
[contract/diagnostics.md](../contract/diagnostics.md). Requirements: S2-ACCESS-01 to S2-ACCESS-03
and scenario S2-T02 of [STAGE-2.md](../STAGE-2.md); decisions
[ISSUE-20-DEC-001](../decisions/issue-20.md#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes)
(human) and
[ISSUE-20-DEC-002](../decisions/issue-20.md#issue-20-dec-002--technical-defaults-td-20-1-to-td-20-15)
(coordinator).

Hardware honesty: none claimed. Every test uses a mock transport or a synthetic loopback device on
`127.0.0.1`; no LAN device, physical lighting or deployed service was contacted.

## First pull request: profiles, device ceilings and guard layers

Scenario IDs T20-01 to T20-13. Tests are in `tests/test_access_profiles.py` unless named otherwise.

| Scenario | Evidence |
| --- | --- |
| T20-01 per profile, stdio and HTTP: `tools/list` equals `expected_names(profile)`, each tool byte-identical to the full list's | `test_tools_list_equals_the_profile_expectation_and_each_tool_is_unchanged`, installed-console tests for stdio and HTTP (three profiles each), `test_the_file_profile_applies_and_the_option_overrides_it` |
| T20-02 a direct `tools/call` of an excluded tool is the same `-32602` "Unknown tool" as a made-up name; zero device requests, both transports | `test_excluded_tool_is_an_unknown_tool_before_any_io` and the console tests |
| T20-03 SDK `get_tool_input_schema` is `None` for excluded tools | `test_sdk_schema_lookup_is_none_for_excluded_tools` |
| T20-04 G3 with test doubles: a `control` composite on a `read`-capped device through each engine and the import entry, a `read` operation attempting a write, a `manage` write on a `control`-capped device are `ACCESS_DENIED`, `not_attempted`, zero requests, guard before the device lock; ambient class visible in children and threads | `test_every_engine_refuses_before_the_lock_and_any_io`, `test_the_import_entry_refuses_before_parsing_or_any_io`, `test_the_ambient_class_is_set_per_call_visible_in_children_and_reset`, `test_every_engine_checks_access_as_its_first_statement` and five more |
| T20-05 class parity: production `Operation.tool_class` equals the contract class for all tools, both directions; a missing class fails at construction; a non-`ToolClass` value is refused by `create_server` | `test_production_classes_equal_the_contract_classes_in_both_directions`, `test_an_operation_without_a_class_cannot_be_constructed`, `test_create_server_refuses_a_class_that_is_not_a_tool_class` |
| T20-06 control/manage split pinned: literal name sets, `control` tools never send `psave`/`pdel` or write a file, `read` tools send no POST | `test_control_and_manage_name_sets_are_pinned`, `test_read_tools_send_no_post_and_write_nothing`, `test_control_tools_never_send_storage_commands_or_write_files` |
| T20-07 invalid `--profile`, `[access] profile` or `max_class`: exit 2 or `ConfigurationError`, fixed positional message, no value echo; precedence option, file, default; `--profile` with a subcommand is a usage error | `test_invalid_access_settings_are_positional_and_value_free`, `test_profile_precedence_is_option_then_file_then_full`, `test_no_environment_variable_selects_a_profile` and six more |
| T20-08 caps: G2 refuses every device-taking write tool above the cap before I/O including `dry_run`; reads stay allowed; effective class is the lower of profile and cap; unknown device keeps `UNKNOWN_DEVICE`; validation precedes G2 | `test_a_device_cap_refuses_every_higher_class_before_any_io_including_dry_run`, `test_the_effective_class_is_the_lower_of_profile_and_cap`, `test_the_cap_cases_cover_every_write_tool` and three more |
| T20-09 concurrent HTTP clients plus a parallel stdio process see the same list and refusals; the capped device receives no write | `test_concurrent_http_clients_and_a_stdio_process_see_the_same_list_and_refusals` (installed console, two loopback devices) |
| T20-10 configuration: retained 0.1.0 and shipped configurations validate unchanged; new keys accepted; unknown `[access]` key rejected value-free; `config validate`/`doctor` text unchanged without access settings; `add-device` keeps bytes; export carries only profile and class names | `test_access_settings_are_additive_and_optional`, `test_retained_and_shipped_configurations_are_unchanged_by_the_new_keys`, `tests/test_setup_cli.py`, `tests/test_doctor.py` (access cases) |
| T20-11 `tests/test_upgrade_compat.py` and migration-note parsing pass without edits | `tests/test_upgrade_compat.py` (unedited) |
| T20-12 structural: `post_state` referenced only from the client, `resources.py` and `bundle_tools.py` | `test_post_state_is_referenced_only_by_the_engines_and_the_import_path` |
| T20-13 restricted-profile smoke against the installed wheel | `scripts/check_distribution.py` (`restricted_handshake`) |
| Startup event: one INFO line with transport, profile and number of capped devices | `test_serve_passes_the_policy_to_create_server_and_logs_one_startup_event`, `test_serve_http_passes_the_policy_to_create_server_and_logs_the_event` |

Implementer mutation spot checks (not a substitute for review): G2 disabled, registry filter
inverted, ambient default lowered, `read` ambient refusal removed, import-entry guard removed,
`lower` returning the higher class and the guard removed from `write_sequence_verified` each fail at
least one test.

## Second pull request: correlation ID, bounded logs and the status tool

Contract: [contract/diagnostics.md](../contract/diagnostics.md). Requirement S2-ACCESS-03 (with
OPS-03 and OPS-05). Scenario IDs T20-14 to T20-17. Tests are in `tests/test_diagnostics.py` unless
named otherwise.

| Scenario | Evidence |
| --- | --- |
| T20-14 a correlation ID on every served envelope (ok, domain error, validation error, `ACCESS_DENIED`, refused `dry_run`), unique per call, never client-chosen, appended to the `-32603` message, absent from direct `execute` dumps, not in the output schema's `required` list; parity tests strip it through one helper | `test_every_served_envelope_carries_a_unique_server_generated_id`, `test_a_client_cannot_choose_the_id`, `test_the_id_is_optional_in_the_schema_and_absent_from_unserved_dumps`, `test_an_internal_failure_names_the_id_and_nothing_else` and three more; helper `tests/envelopes.py`; `tests/test_upgrade_compat.py` unedited |
| T20-15 logs: only allowlisted fields; planted argument values, URLs, header and credential strings absent; line bound; unknown tool name not logged; level and JSON format; stdout untouched on stdio; default level silent on success | `test_a_call_line_has_only_allowlisted_fields_and_no_planted_value`, `test_lines_stay_within_the_bound_in_both_formats`, `test_the_default_level_is_silent_on_success_and_reports_failures`, `test_the_stdio_console_keeps_stdout_clean_at_info_level`, `test_the_http_console_logs_one_bounded_json_line_per_call` and eight more |
| Startup event visible with `WLED_MCP_LOG_LEVEL=info`, silent at the default | `test_the_startup_event_is_visible_only_when_the_level_allows_it` |
| T20-16 status tool: zero requests and file writes; unobserved device `unknown`; failed read shows code and age; good read `reachable`; polling never changes an age; present in all three profiles; no URL, host, path or credential in `data`; read class; counters bounded | `test_the_status_tool_is_listed_in_every_profile_and_sends_nothing`, `test_an_unobserved_device_is_unknown_never_healthy`, `test_polling_the_status_never_refreshes_an_observation_or_sends_a_request`, `test_the_status_data_names_no_url_host_path_or_credential` and eight more; `tests/test_tool_contract.py`, `tests/test_readme.py`, `scripts/check_coverage.py` |
| T20-17 no outbound connection besides configured device requests during a full tool pass; liveness unchanged and device-free | `test_a_full_tool_pass_opens_no_connection_besides_the_configured_devices`, `test_nothing_runs_in_the_background_between_calls`; existing `tests/test_http_service.py` and `tests/test_http_cli.py` |
| TD-20-12 rotation and tenancy statements | `test_the_contract_states_restart_based_rotation_and_no_tenancy` |

Mutation spot checks (implementer): 12 mutations (serializer, ID source, level filter, monitor
observing a rejected address, unobserved reported reachable, status tool sending a request, log
handler on stdout, and others) all killed; six more after correction round 1, all killed.

Boundaries: the status tool and observer are proven against a mock transport and synthetic loopback
devices only. What a real controller returns after a power loss, Wi-Fi roam or captive portal is not
exercised; readiness states describe only what this process observed. No hardware evidence is
claimed for #20.

## Commands and not covered

Commands and results are in the pull request description. `scripts/check_distribution.py` fails
locally at its uvx handshake when the working directory path contains a space; the restricted-profile
handshake before it and the setup and HTTP smoke steps ran. `wled_apply_scene` of #17 is not part of
this work: the guard layers are tested with test-double composites using the same engines and
`Resources.require_access`.
