"""
A set of logging classes for use with the RadAlertLE class.

The RadAlertLE class requires you to give it callback functions that
will be called whenever new data is available from the geiger counter.
This module provides a basic logging class that can be hooked up to
the callbacks to provide a basic console logging program.
"""

import sys
import threading
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from radalert._util.filter import FIRFilter
from radalert._util.filter import IIRFilter
from radalert._util.net import Gmcmap
from radalert._util.net import Radmon
from radalert.generic import RadAlertStatus
from radalert.generic import RadAlertQuery


class LogBackend:
    """
    Backend class to interface with the radalert package.

    Keeps track of various statistics and device state for loggers.
    """

    def __init__(self, samples: List[int] = [10, 60, 300, 3600]) -> None:
        """
        Create a new logger with the given properties.
        """
        self.last_update: Optional[datetime] = None

        self.conversion: Optional[float] = None
        self.battery: Optional[float] = None

        self.averages = []
        for count in samples:
            self.averages.append(FIRFilter(count, sum))

    def radalert_status_callback(self, data: RadAlertStatus) -> None:
        """
        Update internal logger state in response to status updates.

        This callback should be given to the e.g. RadAlertLE object when
        it is created so that we can be periodically informed of status
        updates from the RadAlert device.
        """
        self._on_data(data)

    def radalert_query_callback(self, data: RadAlertQuery) -> None:
        """
        Update internal logger state in response to query updates.

        This callback should be given to the e.g. RadAlertLE object when
        it is created so that we can be informed of the RadAlert device's
        response to any query requests.
        """
        self._on_query(data)

    def _on_data(self, data: RadAlertStatus) -> None:
        self.last_update = datetime.now()
        cps = data.cps

        self.battery = data.battery_percent

        for f in self.averages:
            f.iterate(cps)

    def _on_query(self, data: RadAlertQuery) -> None:
        self.conversion = data.conversion_factor


class ConsoleLogger:
    """
    Simple console-logging class for the Radiation Alert devices.

    Periodically prints the properties tracked by the backend to the
    console.
    """

    def __init__(self, backend: LogBackend, delay: int) -> None:
        self.backend = backend
        self.delay = delay

        self._running = False
        self._thread_event = threading.Event()

    def __str__(self) -> str:
        try:
            if self.backend.last_update is None:
                return ""
            update_delay = datetime.now() - self.backend.last_update
            if update_delay.total_seconds() > self.delay:
                return ""

            table = [
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"{self.backend.battery}%",
                f"{self.backend.conversion}",
            ]

            for f in self.backend.averages:
                total = f.value
                if total is None:
                    table.extend(["", ""])
                else:
                    average = total / len(f.values) * 60
                    table.extend(
                        [
                            f"{total}",
                            f"{average:.1f}",
                        ]
                    )

            return "\t".join(table)
        except:
            return ""

    def header(self) -> str:
        def timespan(time: float) -> Tuple[float, str]:
            if time <= 60:
                return (time, "s")
            time /= 60
            if time <= 60:
                return (time, "m")
            time /= 60
            if time <= 24:
                return (time, "h")
            time /= 24
            return (time, "d")

        table = ["time", "battery", "cpm/(mR/h)"]
        for f in self.backend.averages:
            ts = timespan(f.size)
            table.extend(
                [
                    f"{ts[0]:.0f}{ts[1]}-cnt",
                    f"{ts[0]:.0f}{ts[1]}-cpm",
                ]
            )
        return "\t".join(table)

    def spin(self) -> None:
        """
        Spin our wheels periodically logging to the console.

        This should be executed in a seperate thread to ensure that
        execution can still continue.
        """
        if not self._running:
            print(self.header())
            self._running = True

        while self._running:
            line = self.__str__()
            if len(line) > 0:
                print(line)
            self._thread_event.wait(timeout=self.delay)

    def stop(self) -> None:
        """Stop execution of the spin function."""
        self._running = False
        self._thread_event.set()


class GmcmapLogger:
    """
    Simple class to take care of logging data to the GMC.MAP service.
    """

    def __init__(
        self, backend: LogBackend, account_id: str, geiger_id: str, delay: int
    ) -> None:
        self.backend = backend
        self.Gmcmap = Gmcmap(account_id, geiger_id)
        self.delay = delay

        self._running = False
        self._thread_event = threading.Event()

    def send_update(self) -> None:
        try:
            if self.backend.last_update is None:
                return
            update_delay = datetime.now() - self.backend.last_update
            if update_delay.total_seconds() > self.delay:
                return

            avg_short = self.backend.averages[1].value
            avg_long = self.backend.averages[2].value
            conversion = self.backend.conversion

            if avg_short is None or avg_long is None:
                return

            avg_short = avg_short / len(self.backend.averages[1].values) * 60
            avg_long = avg_long / len(self.backend.averages[2].values) * 60

            usv: Optional[float] = None
            if conversion is not None:
                usv = avg_short / conversion * 10

            self.send_values(avg_short, avg_long, usv)
        except Exception as e:
            print(f"Unable to send values to gmc server: {e}", file=sys.stderr)

    def send_values(self, cpm: float, acpm: float, usv: Optional[float]) -> None:
        """
        Send the log data to the service.
        """
        self.Gmcmap.send_values(cpm, acpm, usv)

    def spin(self) -> None:
        """
        Spin our wheels periodically logging to the server.

        This should be executed in a seperate thread to ensure that
        execution can still continue.
        """
        if not self._running:
            self._running = True

        while self._running:
            self.send_update()
            self._thread_event.wait(timeout=self.delay)

    def stop(self) -> None:
        """Stop execution of the spin function."""
        self._running = False
        self._thread_event.set()


class RadmonLogger:
    """
    Simple class to take care of logging data to the Radmon service.
    """

    def __init__(
        self, backend: LogBackend, account_id: str, geiger_id: str, delay: int
    ) -> None:
        self.backend = backend
        self.Radmon = Radmon(account_id, geiger_id)
        self.delay = delay

        self._running = False
        self._thread_event = threading.Event()

    def send_update(self) -> None:
        try:
            if self.backend.last_update is None:
                return
            update_delay = datetime.now() - self.backend.last_update
            if update_delay.total_seconds() > self.delay:
                return

            avg_long = self.backend.averages[2].value

            if avg_long is None:
                return

            avg_long = avg_long / len(self.backend.averages[2].values) * 60

            self.send_values(avg_long)
        except Exception as e:
            print(f"Unable to send values to radmon server: {e}", file=sys.stderr)

    def send_values(self, cpm: float) -> None:
        """
        Send the log data to the service.
        """
        self.Radmon.send_values(cpm)

    def spin(self) -> None:
        """
        Spin our wheels periodically logging to the server.

        This should be executed in a seperate thread to ensure that
        execution can still continue.
        """
        if not self._running:
            self._running = True

        while self._running:
            self.send_update()
            self._thread_event.wait(timeout=self.delay)

    def stop(self) -> None:
        """Stop execution of the spin function."""
        self._running = False
        self._thread_event.set()
