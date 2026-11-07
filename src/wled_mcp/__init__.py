"""WLED MCP server package.

The package version has one source, ``project.version`` in ``pyproject.toml``
(docs/contract/versioning.md). At runtime it is read from the installed distribution's
metadata, so the console ``--version``, MCP ``serverInfo.version`` and
``diagnostics.server_version`` always report the version of the wheel that is running,
including a non-release build's local identifier.
"""

from importlib.metadata import PackageNotFoundError, version

DISTRIBUTION = "wled-mcp"

try:
    __version__ = version(DISTRIBUTION)
except PackageNotFoundError:  # imported from a source tree without an installed distribution
    __version__ = "0+unknown"
