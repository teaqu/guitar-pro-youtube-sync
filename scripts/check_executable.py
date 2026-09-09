"""Run a packaged executable's offline self-test in an isolated directory."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


SUCCESS_MARKER = "SELF-TEST PASSED"


def isolated_environment() -> dict[str, str]:
    """Keep OS loader/home state, but prevent host Deno and FFmpeg discovery."""
    allowed = (
        "SYSTEMROOT", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT",
        # Python imports use Path.home(), including on Windows where it derives
        # from USERPROFILE or HOMEDRIVE/HOMEPATH. Keep the real values because
        # the self-test does not read config or browser cookies.
        "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
        "TMP", "TEMP", "TMPDIR",
    )
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    # An empty PATH makes a missing bundled dependency fail the smoke test instead
    # of silently using one installed on the GitHub runner.
    environment["PATH"] = ""
    return environment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()

    executable = args.executable.resolve()
    if not executable.is_file():
        parser.error(f"executable does not exist: {executable}")

    try:
        # Spaces here catch quoting/path handling regressions in the packaged app.
        with tempfile.TemporaryDirectory(prefix="guitar pro sync smoke ") as temporary:
            result = subprocess.run(
                [str(executable), "--self-test"],
                cwd=temporary,
                env=isolated_environment(),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=120,
            )
    except subprocess.TimeoutExpired as error:
        output = error.output or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        sys.stdout.write(output)
        print("Packaged executable self-test timed out after 120 seconds.")
        return 124

    # The workflow redirects this complete output to an artifact on failure.
    # A marker prevents an unsupported CLI flag that exits successfully from
    # being mistaken for a passing package smoke test.
    sys.stdout.write(result.stdout or "")
    if result.returncode:
        return result.returncode
    if SUCCESS_MARKER not in (result.stdout or ""):
        print(f"Missing required self-test marker: {SUCCESS_MARKER}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
