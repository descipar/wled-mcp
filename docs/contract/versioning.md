# Versioning and build identity

Contract for the package version, its mapping to every artifact and the identity of non-release builds. Introduced by
[#21](https://github.com/descipar/wled-mcp/issues/21) (S2-COMPAT-01) and
[#70](https://github.com/descipar/wled-mcp/issues/70); decisions DEC-020 (pre-1.0 policy), DEC-012 (identities) and
ISSUE-21-DEC-002 (technical defaults, [decision log](../decisions/stage-2.md)). Examples use the synthetic version
`1.2.3`. The support matrix is in [compatibility.md](compatibility.md).

## Version source

- The only hand-maintained version is `project.version` in `pyproject.toml`, a static value (no version derived from Git
  tags at build time).
- At runtime the server reads the installed distribution's metadata (`importlib.metadata.version("wled-mcp")`);
  `wled_mcp.__version__` is that value. `wled-mcp --version`, MCP `serverInfo.version` and `diagnostics.server_version`
  of `wled_get_state` therefore report the version of the wheel that is running, including a non-release label.
- Everything else derives it: `scripts/check_distribution.py` and `deploy/stage_release.py` read `pyproject.toml` or the
  built wheel's metadata; the image `Dockerfile` copies the single staged wheel by pattern and pins it through
  `SHA256SUMS`; the example files use the placeholders `REPLACE_WITH_VERSION` and `REPLACE_WITH_IMAGE_TAG`; tests
  compare with `pyproject.toml`. The synthetic example `examples/contracts/state.json` shows
  `diagnostics.server_version` as `0.0.0+example`, a fixed placeholder that never equals a real version.
- The Claude Desktop bundle manifest (`deploy/mcpb/manifest.template.json`, #151) uses the placeholder
  `REPLACE_WITH_VERSION`; `deploy/build_mcpb.py` renders it from `project.version` and refuses a different requested
  version before writing anything.
- `tests/test_version_source.py` fails when a tracked file other than the allowlisted ones contains the current version
  as a literal. Allowlisted: `pyproject.toml`, its generated `uv.lock` entry, the registry metadata `server.json` (the
  version twice, as `version` and as the PyPI package `version`, both compared with `project.version`), retained
  fixtures of earlier releases (`tests/fixtures/compat/`), the release history `CHANGELOG.md`, and historical records
  that quote the version they were run or decided against (`docs/VALIDATION.md`, `docs/validation/`,
  `docs/DECISIONS.md`, `docs/decisions/`).
- A version change edits `pyproject.toml` (and refreshes `uv.lock`) and the two versions in `server.json`. Version bumps
  belong to the release work ([#25](https://github.com/descipar/wled-mcp/issues/25) or a release-preparation pull
  request the owner authorized, as ISSUE-24-DEC-001 did).

## Release versions and their mapping

A release version is `MAJOR.MINOR.PATCH`, for example `1.2.3`; a release candidate, if ever needed, is
`MAJOR.MINOR.PATCHrcN` (SemVer `MAJOR.MINOR.PATCH-rc.N`). While the major version is `0`, DEC-020 applies: breaking
changes are allowed in minor releases with migration notes, and fixes are made for the latest release only.

| Artifact | Form for release `1.2.3` |
| --- | --- |
| Package metadata (`Version:`), `--version`, `serverInfo.version` | `1.2.3` |
| Wheel | `wled_mcp-1.2.3-py3-none-any.whl` |
| Staged release directory | `<output>/1.2.3/` |
| Local image tag | `wled-mcp:1.2.3` |
| Published image (later, #22/#24) | `ghcr.io/descipar/wled-mcp:1.2.3` |
| MCP registry `version` (later, #22/#24) | `1.2.3` for `io.github.descipar/wled-mcp` |
| Git tag (created by #22/#25) | `v1.2.3` |

The PEP 440 string, image tag, registry version and Git tag are identical apart from the `v` prefix of the Git tag. The
three DEC-012 identities always carry the same version.

## Non-release builds

A build of a commit that is not a release carries a PEP 440 local version label:

```text
<base>+g<first 12 hex digits of the source commit>[.dirty]
```

- `<base>` is `project.version` of the built commit (a release version). The label starts with `g` so that it is never
  all digits; `.dirty` marks a build that includes uncommitted changes to tracked files.
- `deploy/stage_release.py --non-release` exports the checked-out commit with `git archive`, rewrites the version only
  in that exported copy, builds the wheel from it offline and stages it. `--dirty` exports the working tree of tracked
  files instead (a temporary `git stash create` commit object; checkout, index and stash list stay unchanged). Untracked
  files are never included. No tracked file is edited.
- PEP 440 orders `1.2.3 < 1.2.3+g0123456789ab < 1.2.4`; a non-release build is never mistaken for a later release.
  Package indexes do not accept local labels, so a non-release wheel is never published.

| Artifact | Form for a build of commit `0123456789ab...` on base `1.2.3` |
| --- | --- |
| Wheel metadata, `--version`, `serverInfo.version` | `1.2.3+g0123456789ab` |
| Wheel | `wled_mcp-1.2.3+g0123456789ab-py3-none-any.whl` |
| Staged release directory, stdio hub `--from`/`--constraints` paths | `<output>/1.2.3+g0123456789ab/` |
| `SHA256SUMS` | lists the wheel under that name |
| Local image tag | `wled-mcp:1.2.3-g0123456789ab` (`+` mapped to `-`; image tags cannot contain `+`) |

`RELEASE` of a non-release directory records:

```text
version=1.2.3+g0123456789ab
build_kind=non-release
label=g0123456789ab
source_commit=<full 40-hex commit>
source_tree=clean
image_tag=wled-mcp:1.2.3-g0123456789ab
```

`source_tree=modified` together with the `.dirty` label marks a `--dirty` build. The `RELEASE` of a release directory
keeps its three lines (`version`, `source_commit`, `source_tree`); its image tag is the version itself.

Staging refuses an existing directory of the same version (release or non-release), and a version whose label does not
match the build kind: a labelled version without `--non-release`, or a label that does not name the source commit. The
update and rollback procedures in [DEPLOYMENT.md](../DEPLOYMENT.md#non-release-builds) use the directory name and the
`image_tag` value, so they cover both kinds of build.

## Contract evolution

The public contract is every served tool's name, input schema, output schema (the envelope and its `data`), error codes,
enum values, annotations and documented meaning. While the major version is `0` (DEC-020):

- A patch release (`0.Y.Z` to `0.Y.Z+1`) contains no breaking change.
- A minor release (`0.Y` to `0.Y+1`) may contain breaking changes; each has a migration note (below). Nothing is renamed
  or removed silently.
- Non-breaking: a new tool; a new optional input field; a looser input bound or a new accepted input enum value; a new
  output field; a new output enum value or error code; reworded descriptions and titles that keep the meaning; a
  generated `title` or a `default: null` on an optional nullable input field that is no longer served (#235).
- Breaking: removing or renaming a tool, field, error code or enum value; a new required input; a tighter input (lower
  maximum, higher minimum, new pattern, new constraint); a changed type or default; a changed annotation
  (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`); an output field that is no longer guaranteed;
  a changed meaning of an unchanged field.
- Clients must ignore unknown fields in a result. Since [#130](https://github.com/descipar/wled-mcp/issues/130) the
  served output schema allows additional properties on the envelope and on the error object (the models still validate
  strictly inside the server), so a new output field stays non-breaking even for a client that cached the schema. Limit:
  a client that cached a schema served before that change (all `additionalProperties: false`) rejects a newly added
  envelope field once after the upgrade until it refreshes `tools/list` (reload the hub entry). The change is released
  after 0.1.1 (see the [CHANGELOG](../../CHANGELOG.md)). A new error-code or other enum value is non-breaking for the
  contract but can fail a cached schema the same way, because enums stay closed.
- Deprecation: where feasible, a field or tool to be removed stays for one minor release, is marked "Deprecated" in its
  description and has a migration note in the release that deprecates it and in the release that removes it.

`tests/test_upgrade_compat.py` enforces the mechanical part. Each retained release under
`tests/fixtures/compat/<release>/` keeps the complete served `tools/list` of that release. The test serves the current,
unfiltered contract (all tool classes, profile `full`), checks it with `contract_problems` of `tests/tool_contract.py`
and compares every retained tool with the served tool of the same name after expanding local `$ref`s. A breaking
difference fails unless a migration note below names its tool and JSON pointer; tools not in the retained data are
additions. A change of meaning without a schema change needs a migration note by review.

Limit of the snapshot: every tool serves the same output schema, the result envelope, whose `data` is a free-form
object. The comparison covers tool names, input schemas, annotations and the envelope fields (including error codes),
but cannot see a field inside `data` being removed, renamed or retyped. For `wled_get_state` alone, the envelope test
shows that the current result keeps every value of the retained one; for every other tool, changes to `data` fields are
found only by review and must be announced with a migration note.

## Schema evolution

Applies to the inventory configuration (`schema_version`), the result envelope (`schema_version`), preset snapshots
(`format_version`), preset bundles (`format_version`, [presets](presets.md#bundle-format-1)), the JSON output of the
`wled-mcp` subcommands and the `doctor --export` summary (`schema_version`, [CLI](cli.md)) and later persistent formats
(groups and scenes follow the same rules):

- Versions are integers. The current server reads configuration `schema_version` 1, envelope `schema_version` 1,
  snapshot `format_version` 1 and preset bundle `format_version` 1; a bundle with an unknown or higher version is
  rejected with a message that names it (`Unsupported preset bundle format_version 2; ...`), only for integers from 0 to
  9999.
- A reader accepts every version it knows and rejects a higher or unknown version, naming it (from the
  compatibility-policy change of #21 on), for example `Unsupported inventory configuration schema_version 2; this server
  reads schema_version 1.` or `Unsupported snapshot format version 2; this server reads format version 1.`; only
  integers from 0 to 9999 are named, other values keep the generic message, which never quotes file content. The first
  release reports only a generic error (`Invalid inventory configuration: check schema version, ...` or `Unsupported
  snapshot format version.`).
- A new optional configuration key keeps `schema_version` 1; its migration note states the minimum server version,
  because the strict reader of an older server rejects the unknown key after a downgrade. A change of meaning or a
  required key raises the version.
- A migration from an older version happens in memory while reading. The server never rewrites a configuration or
  snapshot file; writing a migrated configuration is an explicit operator action with the `wled-mcp config` commands.
  Only schema 1 exists; a migrating writer arrives with the first schema 2 (ISSUE-16-DEC-002). Snapshots are immutable;
  an unreadable newer snapshot is counted as invalid, left untouched and not pruned.

## Upgrade, downgrade and rollback

- Upgrade: install the new release; it reads the retained data of every earlier release (`tests/test_upgrade_compat.py`
  loads each retained configuration and snapshot, checks that the files stay byte-identical and that the current
  `wled_get_state` envelope only adds to the retained one).
- Downgrade or rollback of the code: an older server rejects a configuration or snapshot version it does not know
  (generic error in the first release). Restore the configuration that was kept for that release. Snapshots written by
  the newer server stay on disk untouched.
- What is tested: the current server reading the retained data of earlier releases and rejecting newer versions without
  modifying files. An older server reading data of a newer one is not run in a test (one manual run of two consecutive
  releases is in the [launch report](../validation/releases.md)); it holds while the configuration and snapshot
  formats are unchanged (both are still version 1), and any format change gets a new version and a migration note.
- A code rollback does not restore any device state, preset or layout; device state is restored only from snapshots or
  presets by an explicit request. The procedures are in [DEPLOYMENT.md](../DEPLOYMENT.md#non-release-builds) and the
  HTTP and stdio update and rollback sections there.

## Migration notes

One row per breaking change, in release order. `tests/test_upgrade_compat.py` reads this block: a row allows breaking
differences of its tool at its JSON pointer (the pointer into the tool object after `$ref` expansion, for example
`/inputSchema/properties/segments`; `/` stands for the whole tool). Rows are never deleted once released. A
configuration or snapshot format change is listed here as well, with the tool column `-` and a pointer into that file
(for example `/schema_version`).

<!-- migration-notes:start -->
| Release | Tool | JSON pointer | Change | Migration |
| --- | --- | --- | --- | --- |
| `0.1.0` | `-` | `/access` | Non-breaking addition: the optional `[access]` table (`profile`) of the inventory configuration (#20). First released in 0.1.0. | None needed. A build from before #20 (never released) rejects the unknown key at startup (exit 2); after a downgrade, use the configuration kept for that version ([profiles](profiles.md#upgrade-and-downgrade)). |
| `0.1.0` | `-` | `/devices/max_class` | Non-breaking addition: the optional per-device `max_class` of the inventory configuration (#20). First released in 0.1.0. | None needed. Same downgrade behavior as `/access`. |
| `0.4.1` | `-` | `/kind` | Non-breaking addition: the optional `kind` (`group` or `room`) of the group document (#183); `format_version` stays 1 and a plain group is written without the key. | None needed. A server from before rooms rejects a room file as an unknown key and counts it in `invalid_count` without touching it; plain-group files stay readable. Remove or convert room files before a downgrade if the older server must list them. |
| `0.4.1` | `-` | `/devices/mac` | Non-breaking addition: the optional per-device `mac` (12 lowercase hex digits) of the inventory configuration, written by `wled_add_device` (#203). `schema_version` stays 1. | None needed. A server from before M8 rejects the unknown key at startup (exit 2); after a downgrade, remove the `mac` lines or use the configuration kept for that version. |
| `0.4.1` | `-` | `/discovery` | Non-breaking addition: the optional `[discovery]` table (`ranges`, 0 to 4 RFC 1918 CIDR strings) of the inventory configuration, written by `wled_set_discovery_ranges` (#202). `schema_version` stays 1. | None needed. Same downgrade behavior as `/devices/mac`: remove the table or use the configuration kept for that version. |
| `0.5.0` | `wled_patch_segments` | `/inputSchema/properties/segments` | The optional fields of a segment (`SegmentPatch`) no longer advertise a `null` alternative in the served schema (#246). The server still accepts an explicit `null` exactly as before; bounds and `required` are unchanged. | None needed for a client that omits unused fields. A client that built requests from the schema and sent `null` for an unused field keeps working; omit the field instead. |
| `0.5.0` | `wled_replace_layout` | `/inputSchema/properties/segments` | Same for the optional fields of a layout segment (`LayoutSegment`, #246); `id`, `start` and `stop` stay required. The same change applies to `wled_preview_layout`, which is not part of the retained 0.1.0 comparison. | Same as `wled_patch_segments`. |
| `0.5.0` | `-` | `/resources` | Non-breaking addition: the server advertises the `resources` capability with the static resource `wled://devices` and the templates `wled://devices/{controller}/effects` and `.../palettes` when their read tool is registered (#258, [resources](resources.md)). Tool names, schemas, descriptions and instructions are unchanged. | None needed. A client that ignores resources is unaffected; a downgrade removes the capability. |
| `0.5.0` | `-` | `/access/tool_groups` | Non-breaking addition: the optional `tool_groups` key of the `[access]` table (group names; default `all`) and the `wled-mcp serve --tool-groups` option (#236). `schema_version` stays 1. Servers with a profile or tool group selection now serve shorter instructions (the sentences about unregistered tools are dropped); tool names and schema shapes are unchanged, but some descriptions are reworded: the `wled_plan_zone` description no longer names `wled_replace_layout`, and the `wled_store_preset` input schema text no longer names it. | None needed. An older server rejects the unknown key as `access: unsupported field` (exit 2, fail-closed) and the unknown option as a usage error; after a downgrade remove the key or use the configuration kept for that version. |
<!-- migration-notes:end -->

Release 0.5.0 is the first release with breaking rows in the migration notes: the advertised input schemas of the segment tools (#246, the two `0.5.0` rows with a tool name). A client that omits unused optional segment fields needs no change, and the server still accepts an explicit `null`.
