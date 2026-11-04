"""Fail when the checked-in runtime export differs from the locked graph."""

import os
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    artifacts = root / ".artifacts"
    artifacts.mkdir(exist_ok=True)
    env = os.environ | {"UV_CACHE_DIR": str(root / ".uv-cache"), "UV_PYTHON_DOWNLOADS": "never"}
    with tempfile.TemporaryDirectory(dir=artifacts) as temporary:
        exported = Path(temporary) / "runtime.txt"
        subprocess.run(
            [
                "uv",
                "export",
                "--locked",
                "--offline",
                "--no-dev",
                "--no-emit-project",
                "--no-hashes",
                "--no-header",
                "--output-file",
                str(exported),
            ],
            cwd=root,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            timeout=30,
        )
        if exported.read_text() != (root / "requirements-runtime.txt").read_text():
            raise SystemExit(
                "Runtime export drift: regenerate requirements-runtime.txt from uv.lock."
            )
    print("Lock/export consistency: PASS")


if __name__ == "__main__":
    main()
