"""
Generic base class defnitions for Radiation Alert geiger counters.
"""

from abc import ABCMeta, abstractmethod

import datetime
from enum import Enum
from typing import Callable, Dict, Generator, List, NoReturn, Optional, Tuple, Union


class RadAlertStatus(metaclass=ABCMeta):
    class AlarmState(Enum):
        """
        Enumeration of possible alarm states.
        """

        DISABLED = 1
        SET = 2
        ALERTING = 3
        SILENCED = 4

    @abstractmethod
    def __init__(self, bytestr: bytes) -> None:
        """
        Create a status object from a bytes object.
        """
        pass

    @property
    @abstractmethod
    def cps(self) -> int:
        """
        Number of counts observed in the last second.
        """
        pass

    @property
    @abstractmethod
    def cpm(self) -> float:
        """
        Average number of counts per minute.
        """
        pass

    @property
    @abstractmethod
    def id(self) -> int:
        """
        Rolling ID number of this packet.
        """
        pass

    @property
    @abstractmethod
    def is_charging(self) -> bool:
        """
        Flag indicating if the device is charging.
        """
        pass

    @property
    @abstractmethod
    def battery_percent(self) -> Optional[float]:
        """
        Battery percentage, or None if not available.
        """
        pass

    @property
    @abstractmethod
    def alarm_state(self) -> AlarmState:
        """
        Current device alarm state (disabled, set, alerting, etc.)
        """
        pass

    @property
    @abstractmethod
    def display_value(self) -> float:
        """
        Value being displayed on screen in the current mode.

        See also: display_units()
        """
        pass

    @property
    @abstractmethod
    def display_units(self) -> str:
        """
        Units associated with the current mode.

        See also: display_value()
        """
        pass

    @property
    @abstractmethod
    def _unknown(self) -> List[Tuple[int, int]]:
        """
        Unknown data contained within the packet.
        """
        pass

    @staticmethod
    @abstractmethod
    def unpack(bytestr: bytes) -> Dict[str, Union[int, bool]]:
        """
        Attempt to unpack a status packet.
        """
        pass


class RadAlertQuery(metaclass=ABCMeta):
    """
    Representation of a query packet from a RadAlertHID device.

    Not all fields in the query packet have been deciphered yet.
    """

    @abstractmethod
    def __init__(self, bytestr: bytes) -> None:
        """
        Create a status object from a bytes object.
        """
        pass

    @property
    @abstractmethod
    def alarm_is_set(self) -> bool:
        """
        Flag indicating if the device's alarm has been set.
        """
        pass

    @property
    @abstractmethod
    def auto_averaging_enabled(self) -> bool:
        """
        Flag indicating if the device's auto-averaging mode is enabled.

        Auto-averaging mode causes the device to change its averaging
        time depending on recent raditation levels. The device manual
        will specify the averaging times and levels. When disabled,
        averaging may still be present, but will not be automatically
        adjusted.
        """
        pass

    @property
    @abstractmethod
    def alarm_level(self) -> int:
        """
        Current alarm level in CPS (even if alarm is disabled).
        """
        pass

    @property
    @abstractmethod
    def audible_beeps(self) -> bool:
        """
        Flag indicatating if the device will produce audible beeps.
        """
        pass

    @property
    @abstractmethod
    def audible_clicks(self) -> bool:
        """
        Flag indicating if the device will produce audible detection clicks.
        """
        pass

    @property
    @abstractmethod
    def backlight_duration(self) -> int:
        """
        Number of seconds that the backlight will remain on.
        """
        pass

    @property
    @abstractmethod
    def calibration_date(self) -> Optional[datetime.datetime]:
        """
        Return the date of last calibration, or None if not set.
        """
        pass

    @property
    @abstractmethod
    def contrast(self) -> float:
        """
        Display contrast percentage.
        """
        pass

    @property
    @abstractmethod
    def conversion_factor(self) -> float:
        """
        Conversion factor from CPM to mR/h.

        Divide a CPM count by this value to transform it into an
        approximate dose rate in mR/h.
        """
        pass

    @property
    @abstractmethod
    def count_duration(self) -> int:
        """
        Number of seconds the device will perform a timed count for.
        """
        pass

    @property
    @abstractmethod
    def datalog_enabled(self) -> bool:
        """
        Flag indicating if the datalog function is enabled.
        """
        pass

    @property
    @abstractmethod
    def datalog_interval(self) -> int:
        """
        Number of minutes between datalog samples.
        """
        pass

    @property
    @abstractmethod
    def datalog_is_circular(self) -> bool:
        """
        Flag indicating if the datalog writes to a circular buffer.
        """
        pass

    @property
    @abstractmethod
    def deadtime(self) -> float:
        """
        Tube deadtime in seconds.
        """
        pass

    @property
    @abstractmethod
    def serial_number(self) -> int:
        """
        Serial number of the device.
        """
        pass


class RadAlert(metaclass=ABCMeta):
    """
    Generic client implementation for the Radiation Alert series
    of devices from SE International.
    """

    @abstractmethod
    def spin(self) -> NoReturn:
        """
        Spin our wheels reading data from the device.

        This is a temporary method to allow us to simply monitor what
        the device is sending. Calling this method enters an infinite
        loop that keeps the connection alive and prints out status
        updates each time we get something new from the device.

        The only way we leave this method is due to a problems with
        HID. A HID or USB stack error may be raised, for example.
        """
        pass
