"""Build the Claude Desktop MCPB bundle ``wled-mcp-<project.version>.mcpb`` (DIST-04, #151).

The bundle holds no server code. Its ``manifest.json`` (MCPB manifest 0.3) makes the host
run the released PyPI package through ``uvx``, pinned to the release version, over stdio.
The archive has exactly four members: ``manifest.json``, ``server/main.py`` (a placeholder
for the entry point the schema requires), ``LICENSE`` and ``NOTICE``.

The manifest is rendered from ``deploy/mcpb/manifest.template.json``: the placeholder
``REPLACE_WITH_VERSION`` becomes the version (PEP 440 in the ``uvx`` pin, semver in the
manifest ``version`` field) and ``REPLACE_WITH_AUTHOR`` the first ``project.authors`` name
of ``pyproject.toml``. It is validated against the vendored, unmodified upstream JSON
schema plus the checks the schema does not make (see ``validate_manifest``). The archive is
deterministic (stored entries, fixed timestamps, sorted names), so the SHA-256 of a
rebuild from the same tag equals the published one. Contract: docs/contract/mcpb-bundle.md.

Standard library plus ``jsonschema`` (a locked dependency of ``mcp``). The script reads
the checkout only and writes exactly one file below ``--output``. Nothing is uploaded.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tomllib
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import jsonschema  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
MCPB_DIR = Path("deploy/mcpb")
TEMPLATE = MCPB_DIR / "manifest.template.json"
SCHEMA = MCPB_DIR / "schema/mcpb-manifest-v0.3.schema.json"
STUB = MCPB_DIR / "server/main.py"
MANIFEST_VERSION = "0.3"
VERSION_PLACEHOLDER = "REPLACE_WITH_VERSION"  # as scripts/check_distribution.py
AUTHOR_PLACEHOLDER = "REPLACE_WITH_AUTHOR"
# A published release version, as deploy/stage_release.py and the release guard.
RELEASE_VERSION = re.compile(r"(\d+\.\d+\.\d+)(?:rc(\d+))?")
SEMVER = re.compile(r"\d+\.\d+\.\d+(?:-rc\.\d+)?")
USER_CONFIG_REFERENCE = re.compile(r"\$\{user_config\.([A-Za-z0-9_]+)\}")
URL_FIELDS = ("homepage", "documentation", "support")
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
FILE_MODE = 0o100644 << 16  # regular file, rw-r--r--, recorded for create_system 3 (Unix)


class BundleError(Exception):
    """A precondition failed; nothing was written."""


def bundle_name(version: str) -> str:
    return f"wled-mcp-{version}.mcpb"


def project_metadata(root: Path = ROOT) -> dict[str, Any]:
    with (root / "pyproject.toml").open("rb") as stream:
        project: dict[str, Any] = tomllib.load(stream)["project"]
    return project


def manifest_version(version: str) -> str:
    """The semver form of a release version: ``X.Y.ZrcN`` becomes ``X.Y.Z-rc.N``."""
    match = RELEASE_VERSION.fullmatch(version)
    if match is None:
        raise BundleError(f"{version!r} is not a release version (X.Y.Z or X.Y.ZrcN)")
    base, candidate = match.groups()
    return base if candidate is None else f"{base}-rc.{candidate}"


def _substitute(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        for placeholder, text in replacements.items():
            value = value.replace(placeholder, text)
        return value
    if isinstance(value, dict):
        return {key: _substitute(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item, replacements) for item in value]
    return value


def render_manifest(version: str, author: str | None = None, root: Path = ROOT) -> dict[str, Any]:
    """The manifest of release ``version``; the author defaults to ``project.authors[0]``."""
    semver = manifest_version(version)
    if author is None:
        author = str(project_metadata(root)["authors"][0]["name"])
    template: dict[str, Any] = json.loads((root / TEMPLATE).read_text("utf-8"))
    template["version"] = semver
    rendered: dict[str, Any] = _substitute(
        template, {VERSION_PLACEHOLDER: version, AUTHOR_PLACEHOLDER: author}
    )
    return rendered


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def validate_manifest(manifest: Mapping[str, Any], root: Path = ROOT) -> list[str]:
    """Every problem of a manifest: the upstream schema plus the checks it does not make."""
    schema = json.loads((root / SCHEMA).read_text("utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    problems = [
        f"schema: {'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in sorted(validator.iter_errors(dict(manifest)), key=lambda e: str(e.path))
    ]
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        problems.append(f"manifest_version is not {MANIFEST_VERSION!r}")
    if not SEMVER.fullmatch(str(manifest.get("version", ""))):
        problems.append(f"version {manifest.get('version')!r} is not semver")
    urls = [("repository.url", (manifest.get("repository") or {}).get("url"))]
    urls += [(field, manifest.get(field)) for field in URL_FIELDS]
    for field, url in urls:
        parts = urlsplit(url) if isinstance(url, str) else None
        if (
            parts is None
            or parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or re.search(r"\s", str(url))
        ):
            problems.append(f"{field} is not a plain https URL")
    config = (manifest.get("server") or {}).get("mcp_config") or {}
    referenced = {
        name
        for text in _strings([config.get("args", []), config.get("env", {})])
        for name in USER_CONFIG_REFERENCE.findall(text)
    }
    defined = set(manifest.get("user_config") or {})
    problems += [
        f"user_config.{name} is referenced but not defined" for name in sorted(referenced - defined)
    ]
    problems += [
        f"user_config.{name} is defined but never used" for name in sorted(defined - referenced)
    ]
    leftover = [text for text in _strings(dict(manifest)) if "REPLACE_WITH_" in text]
    if leftover:
        problems.append("a REPLACE_WITH_ placeholder is left in the manifest")
    return problems


def manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def entry_problems(entries: Mapping[str, bytes]) -> list[str]:
    """Names that could escape the extraction directory, and a missing ``entry_point``."""
    problems = []
    for name in entries:
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or name.endswith("/")
            or path.is_absolute()
            or ".." in path.parts
            or re.match(r"[A-Za-z]:", name)
        ):
            problems.append(f"unsafe archive member name {name!r}")
    if "manifest.json" not in entries:
        return [*problems, "manifest.json is missing"]
    manifest = json.loads(entries["manifest.json"])
    entry_point = (manifest.get("server") or {}).get("entry_point")
    if entry_point not in entries:
        problems.append(f"entry_point {entry_point!r} is not in the archive")
    return problems


def pack(entries: Mapping[str, bytes]) -> bytes:
    """A deterministic ZIP: stored entries sorted by name, fixed time, no directory entries."""
    problems = entry_problems(entries)
    if problems:
        raise BundleError("; ".join(problems))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = FILE_MODE
            archive.writestr(info, entries[name])
    return buffer.getvalue()


def assemble(version: str, root: Path = ROOT) -> bytes:
    """Render, validate and pack the bundle of ``version``; writes nothing."""
    manifest = render_manifest(version, root=root)
    problems = validate_manifest(manifest, root)
    if problems:
        raise BundleError("manifest is invalid: " + "; ".join(problems))
    return pack(
        {
            "manifest.json": manifest_bytes(manifest),
            "server/main.py": (root / STUB).read_bytes(),
            "LICENSE": (root / "LICENSE").read_bytes(),
            "NOTICE": (root / "NOTICE").read_bytes(),
        }
    )


def build(output: Path, expected_version: str | None = None, root: Path = ROOT) -> tuple[Path, str]:
    """Write ``wled-mcp-<project.version>.mcpb`` into ``output``; return it and its SHA-256.

    ``expected_version`` (the release tag without ``v``) must equal ``project.version``;
    otherwise nothing is written. An existing bundle is never replaced.
    """
    version = str(project_metadata(root)["version"])
    if expected_version is not None and expected_version != version:
        raise BundleError(
            f"requested version {expected_version!r} differs from project.version {version!r}"
        )
    data = assemble(version, root)  # every check happens before the first write
    target = output / bundle_name(version)
    if target.exists():
        raise BundleError(f"{target} already exists and is not replaced")
    created = not output.exists()
    output.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:  # exclusive: never replaces a file
            try:
                stream.write(data)
            except BaseException:
                stream.close()
                target.unlink(missing_ok=True)
                raise
    except BaseException:
        if created:
            try:
                output.rmdir()
            except OSError:
                pass
        raise
    return target, hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--output", type=Path, required=True, help="directory for the bundle")
    parser.add_argument(
        "--version",
        help="expected release version (default project.version); a different value fails",
    )
    options = parser.parse_args(argv)
    try:
        target, digest = build(options.output, options.version)
    except (BundleError, OSError) as error:
        print(f"build_mcpb: {error}", file=sys.stderr)
        return 1
    print(f"{digest}  {target.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
