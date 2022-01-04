"""Timer related classes and functions."""

import time
import datetime

from typing import List


class TimerError(Exception):
    """Custom exception to report error from the Timer class."""


class Timer:
    """Timer object that tracks elapsed time with the possibility of recoding
    intermeditate times as "laps".

    :param start_timer: if True, the timer is started when the new instance of
        the class is created.
    """

    def __init__(self, start_timer: bool = False):
        self._start_time: float = -1.0
        self.recorded_times: List[float] = []
        if start_timer:
            self.start()

    def _verify_is_running(self) -> None:
        if self._start_time < 0:
            raise TimerError("Timer is not running. Use .start() to start it.")

    def _verify_is_stopped(self) -> None:
        if self._start_time >= 0:
            raise TimerError("Timer is already running. Use .stop() to stop it.")

    def start(self, reset: bool = False) -> None:
        """Start the timer."""
        self._verify_is_stopped()
        if reset:
            self.recorded_times = []
        self._start_time = time.time()

    def lap(self) -> None:
        """Record a new value."""
        self._verify_is_running()
        lap_time = time.time()
        self.recorded_times.append(lap_time - self._start_time)
        self._start_time = lap_time

    def stop(self) -> None:
        """Stop the timer."""
        self.lap()
        self._start_time = -1.0

    @property
    def last_time(self) -> float:
        """Record of the time of the last recorded lap."""
        return self.recorded_times[-1]

    @property
    def total_time(self) -> float:
        """Total time (in seconds) elapsed since the timer was started."""
        return sum(self.recorded_times)

    @property
    def total_time_as_str(self) -> str:
        """Formal total time as string."""
        return str(datetime.timedelta(seconds=round(self.total_time)))

    @property
    def recorded_times_as_str(self) -> List[str]:
        """Format recorded times as strings."""
        return [str(datetime.timedelta(seconds=round(x))) for x in self.recorded_times]
