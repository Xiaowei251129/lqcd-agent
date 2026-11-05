"""Trusted clock ports; interval semantics from A06 Resource Reservation."""
from dataclasses import dataclass
import time
import uuid
import sys
import subprocess

from .strict_json import number, require


@dataclass(frozen=True)
class Timestamp:
    source: str
    wall_seconds: float
    monotonic_seconds: float

    def __post_init__(self):
        require(self.source in ("host", "deterministic_harness"), "Undeclared clock source")
        number(self.wall_seconds)
        number(self.monotonic_seconds)


def host_boot_id():
    """Keep monotonic intervals bound to the same OS boot across CLI processes."""
    from pathlib import Path
    require(sys.platform in ("linux", "darwin"), "Unsupported Host boot identity platform")
    if sys.platform == "linux":
        value = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    else:
        value = subprocess.check_output(["/usr/sbin/sysctl", "-n", "kern.bootsessionuuid"],
                                        text=True, timeout=10).strip()
    return str(uuid.UUID(value))


class HostClock:
    def __init__(self):
        self.epoch_id = "host_clock_" + host_boot_id()

    def now(self):
        return Timestamp("host", time.time(), time.monotonic())


class FakeClock:
    def __init__(self, wall_seconds=0, monotonic_seconds=0, *, epoch_id="fake_clock_epoch_1"):
        self.epoch_id = epoch_id
        self._current = Timestamp("deterministic_harness", wall_seconds, monotonic_seconds)

    def now(self):
        return self._current

    def advance(self, seconds):
        number(seconds)
        self._current = Timestamp(self._current.source,
                                  self._current.wall_seconds + seconds,
                                  self._current.monotonic_seconds + seconds)
        return self._current
