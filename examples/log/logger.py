"""
A set of logging classes for use with the RadAlertLE class.

The RadAlertLE class requires you to give it a callback function that
will be called whenever new data is available from the geiger counter.
This module provides a basic logging class that can be hooked up to
the callback to provide a basic console logging program.
"""

import sys
import threading
from datetime import datetime

from radalert.ble import RadAlertLEStatus
from radalert.ble import RadAlertLEQuery
from radalert._util.filter import FIRFilter
from radalert._util.filter import IIRFilter
from radalert._util.net import Gmcmap
from radalert._util.net import Radmon


class ConsoleLogger:
    """
    Simple console-logging class for the Radiation Alert devices.

    Periodically prints the properties tracked by the backend to the
    console.
    """
    def __init__(self, backend, delay=30):
        self.backend = backend
        self.delay = delay

        self._running = False
        self._thread_event = threading.Event()

    def __str__(self):
        try:
            if self.backend.last_update is None:
                return ""
            update_delay = datetime.now() - self.backend.last_update
            if update_delay.total_seconds() > self.delay:
                return ""

            actual = self.backend.actuals.value

            avg_short = self.backend.averages[0].value * 60
            avg_medium = self.backend.averages[1].value * 60
            avg_long = self.backend.averages[2].value * 60

            maximum = self.backend.maximum.value * 60
            minimum = self.backend.minimum.value * 60

            table = (
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"{self.backend.battery}%",
                f"{self.backend.conversion}",
                f"{actual}",
                f"{avg_short:.2f}",
                f"{avg_medium:.2f}",
                f"{avg_long:.2f}",
                f"{maximum:.2f}",
                f"{minimum:.2f}",
            )

            return "\t".join(table)
        except:
            return ""

    def header(self):
        def timespan(time):
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

        ts_actual = timespan(self.backend.actual_samples)
        ts_short = timespan(self.backend.average_samples[0])
        ts_medium = timespan(self.backend.average_samples[1])
        ts_long = timespan(self.backend.average_samples[2])
        ts_minmax = timespan(self.backend.minmax_samples)

        table = (
            "time",
            "battery",
            "cpm/(mR/h)",
            f"{ts_actual[0]}{ts_actual[1]}-count",
            f"{ts_short[0]}{ts_short[1]}-avg-cpm",
            f"{ts_medium[0]}{ts_medium[1]}-avg-cpm",
            f"{ts_long[0]}{ts_long[1]}-avg-cpm",
            f"{ts_minmax[0]}{ts_minmax[1]}-max-cpm",
            f"{ts_minmax[0]}{ts_minmax[1]}-min-cpm",
        )
        return "\t".join(table)

    def spin(self):
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

    def stop(self):
        """Stop execution of the spin function."""
        self._running = False
        self._thread_event.set()


class GmcmapLogger:
    """
    Simple class to take care of logging data to the GMC.MAP service.
    """
    def __init__(self, backend, account_id, geiger_id, delay=180):
        self.backend = backend
        self.Gmcmap = Gmcmap(account_id, geiger_id)
        self.delay = delay

        self._running = False
        self._thread_event = threading.Event()

    def send_update(self):
        try:
            if self.backend.last_update is None:
                return
            update_delay = datetime.now() - self.backend.last_update
            if update_delay.total_seconds() > self.delay:
                return

            avg_short = self.backend.averages[0].value * 60
            avg_long = self.backend.averages[2].value * 60
            usv = avg_short / self.backend.conversion * 10

            self.send_values(avg_short, avg_long, usv)
        except Exception as e:
            print(f"Unable to send values to gmc server: {e}", file=sys.stderr)

    def send_values(self, cpm, acpm, usv):
        """
        Send the log data to the service.
        """
        self.Gmcmap.send_values(cpm, acpm, usv)

    def spin(self):
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

    def stop(self):
        """Stop execution of the spin function."""
        self._running = False
        self._thread_event.set()


class RadmonLogger:
    """
    Simple class to take care of logging data to the Radmon service.
    """
    def __init__(self, backend, account_id, geiger_id, delay=180):
        self.backend = backend
        self.Radmon = Radmon(account_id, geiger_id)
        self.delay = delay

        self._running = False
        self._thread_event = threading.Event()

    def send_update(self):
        try:
            if self.backend.last_update is None:
                return
            update_delay = datetime.now() - self.backend.last_update
            if update_delay.total_seconds() > self.delay:
                return

            avg_short = self.backend.averages[0].value * 60

            self.send_values(avg_short)
        except Exception as e:
            print(f"Unable to send values to radmon server: {e}",
                  file=sys.stderr)

    def send_values(self, cpm):
        """
        Send the log data to the service.
        """
        self.Radmon.send_values(cpm)

    def spin(self):
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

    def stop(self):
        """Stop execution of the spin function."""
        self._running = False
        self._thread_event.set()


class LogBackend:
    """
    Backend class to interface with the radalert package.

    Keeps track of various statistics and device state for loggers.
    """
    def __init__(self,
                 actual_samples=60,
                 average_samples=(300, 43200, 7776000),
                 minmax_samples=300):
        """
        Create a new logger with the given properties.
        """
        self.last_update = None

        self.conversion = None
        self.battery = 0

        self.actual_samples = actual_samples
        self.actuals = FIRFilter(actual_samples, sum)
        self.average_samples = average_samples
        self.averages = (
            FIRFilter(average_samples[0]),
            IIRFilter.create_from_time_constant(average_samples[1]),
            IIRFilter.create_from_time_constant(average_samples[2]),
        )
        self.minmax_samples = minmax_samples
        self.maximum = FIRFilter(minmax_samples, max)
        self.minimum = FIRFilter(minmax_samples, min)

    def radalert_le_callback(self, data):
        """
        Update internal state whenever a RadAlertLE has new data.

        This is a callback that should be given to the RadAlertLE object
        so that we can be informed whenever new data is available.
        """
        if isinstance(data, RadAlertLEStatus):
            self._on_data(data)
        elif isinstance(data, RadAlertLEQuery):
            self._on_query(data)

    def _on_data(self, data):
        self.last_update = datetime.now()
        cps = data.cps

        self.battery = data.battery_percent

        # Do not initalize actual count with any kind of average
        self.actuals.iterate(cps)

        # Initialize averaging filters to the device average
        if self.averages[0].value is None:
            self.averages[0].iterate(data.cpm / 60)
        if self.averages[1].value is None:
            self.averages[1].iterate(data.cpm / 60)
        if self.averages[2].value is None:
            self.averages[2].iterate(data.cpm / 60)

        self.averages[0].iterate(cps)
        self.averages[1].iterate(cps)
        self.averages[2].iterate(cps)

        # Initialize the minmax filters to the device average
        if len(self.maximum.values) == 0:
            self.maximum.iterate(data.cpm / 60)
        if len(self.maximum.values) == 0:
            self.maximum.iterate(data.cpm / 60)

        self.maximum.iterate(self.averages[0].value)
        self.minimum.iterate(self.averages[0].value)

    def _on_query(self, data):
        self.conversion = data.conversion_factor
