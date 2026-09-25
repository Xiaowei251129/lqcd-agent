"""Trusted clock ports; interval semantics from A06 Resource Reservation."""
from dataclasses import dataclass
import time
import uuid
from typing import Protocol

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


class Clock(Protocol):
    def now(self) -> Timestamp: ...


class HostClock:
    def __init__(self):
        self.epoch_id = "host_clock_" + uuid.uuid4().hex

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


@dataclass(frozen=True)
class ActiveCharge:
    stage: str
    run_seconds: float
    attempt_seconds: float


def measure(stage, start, end, *, result_ready=None, seal_ready=None):
    """Classify an interval without starting an Attempt or settling a resource."""
    require(type(start) is Timestamp and type(end) is Timestamp, "Missing trusted interval")
    require(start.source == end.source, "Clock source changed")
    require(end.wall_seconds >= start.wall_seconds and
            end.monotonic_seconds >= start.monotonic_seconds, "Clock regression")
    require(stage in ("host_setup", "backend_active", "paused_waiting", "attempt_active", "verification"),
            "Unknown clock stage")
    duration = number(end.monotonic_seconds - start.monotonic_seconds)
    if stage == "backend_active":
        require(type(result_ready) is Timestamp and type(seal_ready) is Timestamp,
                "Backend interval requires both result and seal")
        for stamp in (result_ready, seal_ready):
            require(stamp.source == start.source and
                    start.monotonic_seconds <= stamp.monotonic_seconds <= end.monotonic_seconds and
                    start.wall_seconds <= stamp.wall_seconds <= end.wall_seconds,
                    "Invalid backend completion timestamp")
        require(end.monotonic_seconds == max(result_ready.monotonic_seconds, seal_ready.monotonic_seconds),
                "Delivery or polling cannot extend backend active time")
    else:
        require(result_ready is None and seal_ready is None, "Unexpected backend timestamps")
    return ActiveCharge(stage, 0 if stage == "paused_waiting" else duration,
                        0 if stage in ("host_setup", "paused_waiting") else duration)
