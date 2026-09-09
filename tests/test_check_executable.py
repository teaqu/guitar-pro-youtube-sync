"""Regression tests for the packaged-executable CI harness."""

from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

from scripts import check_executable


def _arguments(monkeypatch, executable: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["check_executable.py", str(executable)])


def test_rejects_successful_process_without_self_test_marker(monkeypatch, tmp_path, capsys):
    executable = tmp_path / "app"
    executable.touch()
    _arguments(monkeypatch, executable)
    monkeypatch.setattr(
        check_executable.subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([str(executable)], 0, "unsupported option\n")),
    )

    assert check_executable.main() == 1
    output = capsys.readouterr().out
    assert "unsupported option" in output
    assert check_executable.SUCCESS_MARKER in output


def test_timeout_preserves_captured_output(monkeypatch, tmp_path, capsys):
    executable = tmp_path / "app"
    executable.touch()
    _arguments(monkeypatch, executable)
    timeout = subprocess.TimeoutExpired([str(executable), "--self-test"], 120, output="partial output\n")
    monkeypatch.setattr(check_executable.subprocess, "run", Mock(side_effect=timeout))

    assert check_executable.main() == 124
    output = capsys.readouterr().out
    assert "partial output" in output
    assert "timed out after 120 seconds" in output
