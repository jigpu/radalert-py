"""
A console logger for use with the RadAlertLE class.

The RadAlertLE class requires you to give it a callback function that
will be called whenever new data is available from the geiger counter.
This module provides a basic logging class that can be hooked up to
the callback to provide a basic console logging program.
"""

import threading
from datetime import datetime
from time import sleep

from radalert.ble import RadAlertLEStatus
from radalert.ble import RadAlertLEQuery
from radalert.util.filter import FIRFilter
from radalert.util.filter import IIRFilter


class RadAlertConsoleLogger:
    """
    Simple console-logging class for the Radiation Alert devices.

    Keeps track of a few key properties and periodically prints them to
    the console.
    """

    def __init__(self, delay=30, actual_samples=60, average_samples=(300,43200,7776000), minmax_samples=300):
        """
        Create a new logger with the given properties.

        :param int delay: Number of seconds to wait between printed updates
        :param average_samples: Number of samples used in the short/medium/long averages
        :param minmax_samples: Number of samples used in the min/max values
        """
        self._running = False
        self._thread_event = threading.Event()
        self._active = False

        self.conversion = None

        self.delay = delay
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
        self.battery = 0

    def __str__(self):
        try:
            actual = self.actuals.value

            avg_short  = self.averages[0].value * 60
            avg_medium = self.averages[1].value * 60
            avg_long   = self.averages[2].value * 60

            maximum = self.maximum.value * 60
            minimum = self.minimum.value * 60

            table = (
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"{self.battery}%",
                f"{self.conversion}",
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

        ts_actual = timespan(self.actual_samples)
        ts_short = timespan(self.average_samples[0])
        ts_medium = timespan(self.average_samples[1])
        ts_long = timespan(self.average_samples[2])
        ts_minmax = timespan(self.minmax_samples)

        table = (
            f"time",
            f"battery",
            f"cpm/(mR/h)",
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
        if self._running == False:
            print(self.header())
            self._running = True

        while self._running:
            line = self.__str__()
            if len(line) > 0 and self._active:
                print(line)
                self._active = False
            self._thread_event.wait(timeout=self.delay)

    def stop(self):
        self._running = False
        self._thread_event.set()

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
        self._active = True
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
