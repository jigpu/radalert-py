"""
A console logger for use with the RadAlertLE class.

The RadAlertLE class requires you to give it a callback function that
will be called whenever new data is available from the geiger counter.
This module provides a basic logging class that can be hooked up to
the callback to provide a basic console logging program.
"""

import datetime
from time import sleep

from radalertle import RadAlertLEStatus
from radalertle import RadAlertLEQuery
from filter import FIRFilter
from filter import IIRFilter


class RadAlertConsoleLogger:
    """
    Simple console-logging class for the Radiation Alert devices.

    Keeps track of a few key properties and periodically prints them to
    the console.
    """

    def __init__(self, delay=30, average_samples=(300,43200,7776000), minmax_samples=300):
        """
        Create a new logger with the given properties.

        :param int delay: Number of seconds to wait between printed updates
        :param average_samples: Number of samples used in the short/medium/long averages
        :param minmax_samples: Number of samples used in the min/max values
        """
        self.conversion = None
        self.running = False

        self.delay = delay
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
            avg_short  = self.averages[0].value * 60
            avg_medium = self.averages[1].value * 60
            avg_long   = self.averages[2].value * 60

            maximum = self.maximum.value * 60
            minimum = self.minimum.value * 60

            table = (
                f"{datetime.datetime.now()}",
                f"{self.battery}%",
                f"{self.conversion}",
                f"{avg_short : .2f}",
                f"{avg_medium :.2f}",
                f"{avg_long :.2f}",
                f"{maximum :.2f}",
                f"{minimum :.2f}",
            )
            return "\t".join(table)
        except:
            return ""

    def header(self):
        def timespan(time):
            unit = "s"
            if time > 60:
                time /= 60
                unit = "m"
            if time > 60:
                time /= 60
                unit = "h"
            if time > 24:
                time /= 24
                unit = "d"
            return (time,unit)

        ts_short = timespan(self.average_samples[0])
        ts_medium = timespan(self.average_samples[1])
        ts_long = timespan(self.average_samples[2])
        ts_minmax = timespan(self.minmax_samples)

        table = (
            f"time",
            f"battery",
            f"cpm/(mR/h)",
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
        if self.running == False:
            print(self.header())
            self.running = True

        while self.running:
            line = self.__str__()
            if len(line) > 0:
                print(line)
            sleep(self.delay)

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
        cps = data.cps

        self.battery = data.battery_percent

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
