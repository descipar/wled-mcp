# Issue #20 validation evidence

Evidence for [issue #20](https://github.com/descipar/wled-mcp/issues/20). Contract:
[contract/profiles.md](../contract/profiles.md). Requirements: S2-ACCESS-01, S2-ACCESS-02
and scenario S2-T02 of [STAGE-2.md](../STAGE-2.md); decisions
[ISSUE-20-DEC-001](../decisions/issue-20.md#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes)
(human) and
[ISSUE-20-DEC-002](../decisions/issue-20.md#issue-20-dec-002--technical-defaults-td-20-1-to-td-20-15)
(coordinator).

Hardware honesty: none claimed. Every test below uses a mock transport or a synthetic
loopback device on `127.0.0.1`; no LAN device, no physical lighting and no deployed
service was contacted. This file is extended by the second pull request (diagnostics and
status tool).

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
| Startup event: one INFO line with the transport, the profile and the number of capped devices, emitted inside `serve()`/`serve_http()` (the default level shows nothing; the existing silent-stderr serve tests pass unchanged) | `::test_serve_passes_the_policy_to_create_server_and_logs_one_startup_event`, `::test_serve_http_passes_the_policy_to_create_server_and_logs_the_event`, `tests/test_doctor.py::test_serve_is_silent_when_backups_are_writable`, `::test_serve_prints_one_backups_advisory_and_still_starts` |

Review checks that these tests were written to fail under (mutation spot checks run by the
implementer, not a substitute for independent review): G2 disabled, registry filter
inverted, ambient default lowered from `manage`, the `read` ambient refusal removed, the
import-entry guard removed, `lower` returning the higher class, and the guard removed
from `write_sequence_verified` each fail at least one of the tests above.

## Commands run

Recorded in the pull request description with their results. `scripts/check_distribution.py`
fails locally at its uvx handshake because the working directory path contains a space; the
restricted-profile handshake before it, and the setup and HTTP smoke steps, ran.

## Not covered by the first pull request

Correlation ID, bounded structured logs, the `wled_get_service_status` tool and the
no-telemetry checks (S2-ACCESS-03, T20-14 to T20-17) belong to the second pull request.
Scene composites of #17 are not in this branch; the guard is tested with test-double
composites that use the same engines and `Resources.require_access`.
