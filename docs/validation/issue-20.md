# Issue #20 validation evidence

Evidence for [issue #20](https://github.com/descipar/wled-mcp/issues/20). Contracts:
[contract/profiles.md](../contract/profiles.md) and
[contract/diagnostics.md](../contract/diagnostics.md). Requirements: S2-ACCESS-01 to S2-ACCESS-03
and scenario S2-T02 of [STAGE-2.md](../STAGE-2.md); decisions
[ISSUE-20-DEC-001](../decisions/issue-20.md#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes)
(human) and
[ISSUE-20-DEC-002](../decisions/issue-20.md#issue-20-dec-002--technical-defaults-td-20-1-to-td-20-15)
(coordinator).

Hardware honesty: none claimed. Every test below uses a mock transport or a synthetic
loopback device on `127.0.0.1`; no LAN device, no physical lighting and no deployed
service was contacted. The first pull request is below; the second pull request (diagnostics
and status tool) extends this file after it.

## First pull request: profiles, device ceilings and guard layers

Scenario IDs T20-01 to T20-13 follow the requirements packet. Tests are in
`tests/test_access_profiles.py` unless a row names another file.

| Scenario | Evidence |
| --- | --- |
| T20-01 per profile, stdio and HTTP: `tools/list` equals `expected_names(profile)` and each served tool is byte-identical to the full list's tool | `::test_tools_list_equals_the_profile_expectation_and_each_tool_is_unchanged` (in-process), `::test_stdio_console_serves_exactly_the_profile_tools`, `::test_http_console_serves_exactly_the_profile_tools` (installed console, three profiles each), `::test_the_file_profile_applies_and_the_option_overrides_it` |
| T20-02 a direct `tools/call` of every excluded tool is the same `-32602` "Unknown tool" as a made-up name; zero device requests, data directory unchanged, both transports | `::test_excluded_tool_is_an_unknown_tool_before_any_io`, and in the console tests above (`profile_session`) |
| T20-03 the SDK `get_tool_input_schema` is `None` for excluded tools | `::test_sdk_schema_lookup_is_none_for_excluded_tools` |
| T20-04 G3 with test doubles: a `control` composite on a `read`-capped device through each engine and the import entry, a `read` operation attempting any write, a `manage` write on a `control`-capped device are `ACCESS_DENIED`, `not_attempted`, zero requests, with the device lock held (guard before the lock); the ambient class is visible in task-group children and threads | `::test_every_engine_refuses_before_the_lock_and_any_io`, `::test_the_import_entry_refuses_before_parsing_or_any_io`, `::test_an_engine_call_outside_a_tool_fails_closed_only_under_a_restriction`, `::test_the_ambient_class_is_set_per_call_visible_in_children_and_reset`, `::test_a_control_composite_cannot_reach_a_read_capped_device_even_when_listed`, `::test_require_access_is_pure_and_lets_unknown_devices_through`, `::test_every_engine_checks_access_as_its_first_statement`, `::test_the_import_path_checks_access_before_parsing_the_bundle` |
| T20-05 class parity: production `Operation.tool_class` equals the contract class for all registered tools, both directions; a missing class fails at construction; a non-`ToolClass` value is refused by `create_server` | `::test_production_classes_equal_the_contract_classes_in_both_directions`, `::test_an_operation_without_a_class_cannot_be_constructed`, `::test_create_server_refuses_a_class_that_is_not_a_tool_class`, `::test_production_profiles_equal_the_independent_expectation_both_ways` |
| T20-06 the control/manage split is pinned: literal name sets (a change detector), `control` tools never send `psave`/`pdel` or write a file, `read` tools send no POST | `::test_control_and_manage_name_sets_are_pinned`, `::test_the_behavior_check_covers_every_read_and_control_tool`, `::test_read_tools_send_no_post_and_write_nothing`, `::test_control_tools_never_send_storage_commands_or_write_files` |
| T20-07 invalid `--profile`, `[access] profile` or `max_class`: exit 2 or `ConfigurationError` with the fixed positional message, no value echo; precedence option, file, default; `--profile` with a subcommand is a usage error | `::test_invalid_access_settings_are_positional_and_value_free`, `::test_access_locators_sort_after_the_device_entries`, `::test_an_invalid_profile_option_is_a_usage_error_without_echo`, `::test_the_profile_option_before_a_subcommand_is_a_usage_error`, `::test_an_invalid_profile_in_the_file_exits_2_at_startup_without_serving`, `::test_profile_precedence_is_option_then_file_then_full`, `::test_an_invalid_profile_option_never_reaches_a_server_process`, `::test_serve_hands_the_resolved_policy_to_the_service`, `::test_no_environment_variable_selects_a_profile` |
| T20-08 caps: G2 refuses every device-taking write tool above the cap before I/O including `dry_run`; reads stay allowed; effective class is the lower of profile and cap; other devices unaffected; unknown device keeps `UNKNOWN_DEVICE`; validation precedes G2 | `::test_a_device_cap_refuses_every_higher_class_before_any_io_including_dry_run`, `::test_reads_stay_allowed_on_a_capped_device_and_other_devices_are_unaffected`, `::test_the_effective_class_is_the_lower_of_profile_and_cap`, `::test_effective_ceiling_is_the_lower_of_profile_and_cap`, `::test_an_unknown_device_keeps_its_own_error_and_a_validation_error_comes_first`, `::test_the_cap_cases_cover_every_write_tool` |
| T20-09 concurrent HTTP clients plus a parallel stdio process see the same list and the same refusals; interleaved calls to capped and uncapped devices; the capped device receives no write | `::test_concurrent_http_clients_and_a_stdio_process_see_the_same_list_and_refusals` (installed console, two loopback devices) |
| T20-10 configuration: retained 0.1.0 and shipped configurations validate unchanged; new keys accepted; unknown `[access]` key rejected value-free; `config validate`/`doctor` text unchanged without access settings; JSON additive; `add-device` keeps bytes with `[access]` present; export carries only the profile and class names | `::test_access_settings_are_additive_and_optional`, `::test_retained_and_shipped_configurations_are_unchanged_by_the_new_keys`, `tests/test_setup_cli.py::test_validate_output_is_unchanged_without_access_settings`, `::test_validate_reports_configured_access_settings_additively`, `::test_validate_names_an_invalid_access_value_without_echo`, `::test_add_device_keeps_every_byte_with_access_settings_and_stays_valid`, `tests/test_doctor.py::test_doctor_output_is_unchanged_without_access_settings`, `::test_doctor_reports_the_configured_profile_and_caps`, `::test_export_carries_only_the_profile_and_class_names`, `::test_doctor_has_no_profile_option_and_never_serves` |
| T20-11 `tests/test_upgrade_compat.py` and migration-note parsing pass without edits | `tests/test_upgrade_compat.py` (unedited; the two new rows of [versioning.md](../contract/versioning.md#migration-notes) parse) |
| T20-12 structural: `post_state` is referenced only from the client, `resources.py` and `bundle_tools.py` | `::test_post_state_is_referenced_only_by_the_engines_and_the_import_path` |
| T20-13 restricted-profile smoke against the installed wheel | `scripts/check_distribution.py` (`restricted_handshake`: `--profile read-only` lists `expected_names("read-only")`, `wled_list_devices` works, `wled_set_state` is an unknown tool) |
| Startup event: one INFO line with the transport, the profile and the number of capped devices, emitted inside `serve()`/`serve_http()` (it arrived in this pull request; the default level shows nothing, and the second pull request adds `WLED_MCP_LOG_LEVEL=info` to make it visible; the existing silent-stderr serve tests pass unchanged) | `::test_serve_passes_the_policy_to_create_server_and_logs_one_startup_event`, `::test_serve_http_passes_the_policy_to_create_server_and_logs_the_event`, `tests/test_doctor.py::test_serve_is_silent_when_backups_are_writable`, `::test_serve_prints_one_backups_advisory_and_still_starts` |

Review checks that these tests were written to fail under (mutation spot checks run by the
implementer, not a substitute for independent review): G2 disabled, registry filter
inverted, ambient default lowered from `manage`, the `read` ambient refusal removed, the
import-entry guard removed, `lower` returning the higher class, and the guard removed
from `write_sequence_verified` each fail at least one of the tests above.

## Second pull request: correlation ID, bounded logs and the status tool

Contract: [contract/diagnostics.md](../contract/diagnostics.md). Requirement S2-ACCESS-03
(with OPS-03 and OPS-05). Scenario IDs T20-14 to T20-17 follow the requirements packet. Tests
are in `tests/test_diagnostics.py` unless a row names another file.

| Scenario | Evidence |
| --- | --- |
| T20-14 a correlation ID on every served envelope (ok, domain error, validation error, `ACCESS_DENIED`, also a refused `dry_run`), unique per call, never client-chosen, appended to the `-32603` message, absent from direct `execute` dumps (retained examples unchanged), not in the output schema's `required` list; parity tests strip it through one helper | `::test_every_served_envelope_carries_a_unique_server_generated_id`, `::test_a_client_cannot_choose_the_id`, `::test_the_id_is_optional_in_the_schema_and_absent_from_unserved_dumps`, `::test_the_result_text_and_structured_content_carry_the_same_id`, `::test_an_internal_failure_names_the_id_and_nothing_else`, `::test_an_unknown_tool_error_is_unchanged_and_the_name_is_not_logged`, `::test_the_strip_helper_validates_before_it_strips`; unchanged examples: `tests/test_layouts.py::test_contract_examples_equal_actual_mock_output` and the preset example tests; helper `tests/envelopes.py` used by `tests/test_compat.py`, `tests/test_acceptance_parity.py`, `tests/test_http_service.py`, `tests/test_scene_parity.py` (`comparable`) and `tests/test_access_profiles.py` (`mask`); additive compatibility: `tests/test_upgrade_compat.py` (unedited) |
| T20-15 logs: only allowlisted fields; planted argument values, URLs, header and credential strings absent; line bound; unknown tool name not logged; level and JSON format; stdout untouched on stdio; default level silent on success; existing silent-stderr tests pass | `::test_a_call_line_has_only_allowlisted_fields_and_no_planted_value`, `::test_the_line_carries_the_outcome_facts_and_class`, `::test_lines_stay_within_the_bound_in_both_formats`, `::test_the_default_level_is_silent_on_success_and_reports_failures`, `::test_the_info_level_logs_successes_and_json_lines_parse`, `::test_third_party_libraries_do_not_inherit_the_info_level`, `::test_the_handler_writes_to_the_current_stderr_never_stdout`, `::test_an_invalid_log_setting_is_named_without_its_value`, `::test_log_settings_default_and_parse_case_insensitively`, `::test_the_stdio_console_keeps_stdout_clean_at_info_level` (installed console), `::test_the_http_console_logs_one_bounded_json_line_per_call` (installed console); `tests/test_doctor.py::test_serve_is_silent_when_backups_are_writable` and `::test_serve_prints_one_backups_advisory_and_still_starts` (unchanged) |
| Startup event made visible (carried N7): the PR A INFO event is shown with `WLED_MCP_LOG_LEVEL=info` and silent at the default | `::test_the_startup_event_is_visible_only_when_the_level_allows_it`; PR A's `tests/test_access_profiles.py::test_serve_passes_the_policy_to_create_server_and_logs_one_startup_event` |
| T20-16 status tool: zero requests and zero file writes; an unobserved device is `unknown`; after a failed read its code and age; after a good read `reachable` with age; polling never changes an age or sends a request; present in all three profiles (second in the list); no URL, host, path or credential in `data`; read class with read annotations; counters bounded | `::test_the_status_tool_is_listed_in_every_profile_and_sends_nothing`, `::test_the_status_tool_is_a_read_class_tool_with_read_annotations`, `::test_an_unobserved_device_is_unknown_never_healthy`, `::test_a_failed_read_is_reported_with_its_code_and_age`, `::test_a_good_read_after_a_failure_is_reachable_with_a_fresh_age`, `::test_polling_the_status_never_refreshes_an_observation_or_sends_a_request`, `::test_writes_and_probes_are_observed_like_reads`, `::test_the_status_data_names_no_url_host_path_or_credential`, `::test_call_counters_are_bounded_by_fixed_keys_and_exclude_the_current_call`, `::test_the_monitor_ignores_unconfigured_devices_and_keeps_bounded_state`, `::test_the_client_observer_sees_only_requests_that_reached_the_transport`; registry position and class: `tests/test_tool_contract.py` and `tests/test_access_profiles.py::test_production_classes_equal_the_contract_classes_in_both_directions` against `tests/tool_contract.py`; README row: `tests/test_readme.py`; coverage placement: `scripts/check_coverage.py` |
| T20-17 no outbound connection besides configured device requests during a full tool pass; liveness (TCP connect, authenticated `ping`) unchanged and device-free | `::test_a_full_tool_pass_opens_no_connection_besides_the_configured_devices` (socket guard plus host assertion over every listed tool), `::test_nothing_runs_in_the_background_between_calls`; liveness: the existing `tests/test_http_service.py` and `tests/test_http_cli.py` checks (unchanged) |
| TD-20-12 rotation and tenancy statements | `::test_the_contract_states_restart_based_rotation_and_no_tenancy`, `::test_the_documents_link_the_diagnostics_contract_and_the_validation_file` |
| Carried review nits of PR A | N1 `AccessPolicy.restricted` removed (it was only used by tests; `tests/test_access_profiles.py::test_default_policy_is_unrestricted_and_a_manage_cap_changes_nothing` now checks the ceilings); N2 `tests/test_access_profiles.py::test_the_g3_and_g2_refusals_have_the_same_envelope_shape_including_dry_run`; N3 and N4 wording in [profiles.md](../contract/profiles.md) and [cli.md](../contract/cli.md); N5 the unknown `[access]` key now reads `access: unsupported field` like `devices[i]: unsupported field` (`tests/test_access_profiles.py::test_invalid_access_settings_are_positional_and_value_free`) |

Mutation spot checks run by the implementer (not a substitute for independent review):
MUTATIONS_PLACEHOLDER

Boundaries of the evidence: the status tool and the observer are proven against a mock
transport and synthetic loopback devices. What a real controller returns after a power loss,
a Wi-Fi roam or a captive portal is not exercised; the readiness states describe only what
this process observed and make no claim about the device now. No hardware evidence is claimed
for #20.

## Commands run

Recorded in the pull request description with their results. `scripts/check_distribution.py`
fails locally at its uvx handshake because the working directory path contains a space; the
restricted-profile handshake before it, and the setup and HTTP smoke steps, ran.

## Not covered

The first pull request did not cover the correlation ID, the logs, the status tool and the
no-telemetry checks; the second pull request above does. `wled_apply_scene` of #17 (its second
pull request) is not part of this work: the guard layers are tested with test-double
composites that use the same engines and `Resources.require_access`, and the status tool and
the call log are class-agnostic, so `wled_apply_scene` needs no change here beyond its
registration and its `tests/tool_contract.py` entry. The seven group and scene tools of #17
pull request A are classified (`wled_save_group`, `wled_delete_group`, `wled_save_scene`,
`wled_delete_scene` as `manage`; the list and plan tools as `read`) and covered by the profile
tests.
