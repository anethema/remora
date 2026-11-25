"""Check local simulation exclusivity without launching another firmware process."""
# AP_FLAKE8_CLEAN
import fcntl
from pathlib import Path

import pytest

from remora import sitl


def test_exclusive_run_and_failed_start_release(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(sitl, "ROOT", tmp_path)
    binary = tmp_path / "build/sitl/bin/ardurover"
    binary.parent.mkdir(parents=True)
    binary.touch()

    def fail_before_launch():
        raise OSError("PTY unavailable")

    monkeypatch.setattr(sitl.os, "openpty", fail_before_launch)
    directory = tmp_path / ".cache/remora"
    directory.mkdir(parents=True)
    with (directory / "simulator.lock").open("a+b") as competing:
        fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="already running"):
            with sitl.Sitl(tmp_path / "busy"):
                pytest.fail("Duplicate simulation admitted")
        fcntl.flock(competing, fcntl.LOCK_UN)
        with pytest.raises(OSError, match="PTY unavailable"):
            with sitl.Sitl(tmp_path / "interrupted"):
                pytest.fail("Startup unexpectedly succeeded")
        fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
