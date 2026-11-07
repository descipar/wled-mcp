# Versioning and build identity

Contract for the package version, its mapping to every artifact and the identity of
non-release builds. Introduced by [#21](https://github.com/descipar/wled-mcp/issues/21)
(S2-COMPAT-01) and [#70](https://github.com/descipar/wled-mcp/issues/70); decisions
DEC-020 (pre-1.0 policy), DEC-012 (identities) and ISSUE-21-DEC-002 (technical defaults,
[decision log](../decisions/issue-21.md)). Examples use the synthetic version `1.2.3`.

The rules for contract evolution, schema versions, deprecation and migration notes are
added to this file by the compatibility-policy part of #21.

## Version source

- The only hand-maintained version is `project.version` in `pyproject.toml`, a static
  value (no version derived from Git tags at build time).
- At runtime the server reads the installed distribution's metadata
  (`importlib.metadata.version("wled-mcp")`); `wled_mcp.__version__` is that value.
  `wled-mcp --version`, MCP `serverInfo.version` and `diagnostics.server_version` of
  `wled_get_state` therefore report the version of the wheel that is actually running,
  including a non-release label.
- Everything else derives it: `scripts/check_distribution.py` and
  `deploy/stage_release.py` read `pyproject.toml` or the built wheel's metadata; the
  image `Dockerfile` copies the single staged wheel by pattern and pins it through
  `SHA256SUMS`; the example files name the release directory and image tag by the
  placeholders `REPLACE_WITH_VERSION` and `REPLACE_WITH_IMAGE_TAG`; tests compare with
  `pyproject.toml`.
- `tests/test_version_source.py` fails when a tracked file other than the allowlisted
  ones contains the current version as a literal. Allowlisted: `pyproject.toml`, its
  generated `uv.lock` entry, retained fixtures of earlier releases
  (`tests/fixtures/compat/`), and historical records that quote the version they were
  run or decided against (`docs/VALIDATION.md`, `docs/validation/`, `docs/DECISIONS.md`,
  `docs/decisions/`).
- A version change therefore edits `pyproject.toml` (and refreshes `uv.lock`) only.
  Version bumps belong to the release work ([#25](https://github.com/descipar/wled-mcp/issues/25)).

## Release versions and their mapping

A release version is `MAJOR.MINOR.PATCH`, for example `1.2.3`; a release candidate, if
ever needed, is `MAJOR.MINOR.PATCHrcN` (SemVer `MAJOR.MINOR.PATCH-rc.N`). While the
major version is `0`, DEC-020 applies: breaking changes are allowed in minor releases
with migration notes, and fixes are made for the latest release only.

| Artifact | Form for release `1.2.3` |
| --- | --- |
| Package metadata (`Version:`), `--version`, `serverInfo.version` | `1.2.3` |
| Wheel | `wled_mcp-1.2.3-py3-none-any.whl` |
| Staged release directory | `<output>/1.2.3/` |
| Local image tag | `wled-mcp:1.2.3` |
| Published image (later, #22/#24) | `ghcr.io/descipar/wled-mcp:1.2.3` |
| MCP registry `version` (later, #22/#24) | `1.2.3` for `io.github.descipar/wled-mcp` |
| Git tag (created by #22/#25) | `v1.2.3` |

The PEP 440 string, image tag, registry version and Git tag are identical apart from
the `v` prefix of the Git tag. The three DEC-012 identities always carry the same
version.

## Non-release builds

A build of a commit that is not a release carries a PEP 440 local version label:

```text
<base>+g<first 12 hex digits of the source commit>[.dirty]
```

- `<base>` is `project.version` of the built commit (a release version). The label
  starts with `g` so that it is never all digits; `.dirty` marks a build that includes
  uncommitted changes to tracked files.
- `deploy/stage_release.py --non-release` exports the checked-out commit with
  `git archive`, rewrites the version only in that exported copy, builds the wheel from
  it offline and stages it. `--dirty` exports the working tree of tracked files instead
  (a temporary `git stash create` commit object; checkout, index and stash list stay
  unchanged). Untracked files are never included. No tracked file is edited.
- PEP 440 orders `1.2.3 < 1.2.3+g0123456789ab < 1.2.4`; a non-release build is never
  mistaken for a later release. Local labels are not accepted by package indexes, so a
  non-release wheel is never published.

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

`source_tree=modified` together with the `.dirty` label marks a `--dirty` build. The
`RELEASE` of a release directory keeps its three lines (`version`, `source_commit`,
`source_tree`); its image tag is the version itself.

Staging refuses an existing directory of the same version (release or non-release);
the same commit is staged once. Staging also refuses a version whose label does not
match the build kind: a labelled version without `--non-release`, or a label that does
not name the source commit. The update and rollback procedures in
[DEPLOYMENT.md](../DEPLOYMENT.md#non-release-builds) use the directory name and the
`image_tag` value, so they cover both kinds of build.
