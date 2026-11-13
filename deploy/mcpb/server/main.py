"""Placeholder for the entry point that the MCPB manifest schema requires.

The bundle contains no server code: ``manifest.json`` makes the host start the released
PyPI package through ``uvx``. This file only keeps the path named in the manifest
valid and is not meant to run.
"""

import sys

sys.stderr.write(
    "This file is a placeholder. The bundle starts wled-mcp through uvx (see manifest.json); "
    "check that uv is installed and on the PATH of the application.\n"
)
raise SystemExit(2)
