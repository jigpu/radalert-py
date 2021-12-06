"""
HID protocol implmentation for Radiation Alert geiger counters.

The recent Radiation Alert series of geiger counters from SE International
provide a USB HID connection that can be used to communicate with the
device. This module implements the HID protocol used by this connection,
decoding the packets into a form which is more easily usable.

There are still some unknown components of this protocol, but its current
state is good enough for most basic work :)
"""

import sys
import struct
import datetime
import re
import time
from enum import Enum
from typing import Callable, Dict, Generator, List, NoReturn, Optional, Tuple, Union

import hid
from radalert import generic


class RadAlertHIDStatus(generic.RadAlertStatus):
    """
    Representation of a status packet from a RadAlertHID device.

    Not all fields in the status packet have been deciphered yet.
    """
    # yapf: disable
    _MODE_DISPLAY_INFO: Dict[int, Tuple[str, Callable[[float], float]]] = {
        0:  ("cpm",    lambda x: x),       # CPM -> CPM
        1:  ("cps",    lambda x: x/10),    # centi-CPS -> CPS
        2:  ("µR/h",   lambda x: x),       # uR/h -> uR/h
        3:  ("µSv/h",  lambda x: x/1000),  # nSv/h -> uS/h
        20: ("counts", lambda x: x),       # counts -> counts
        23: ("mR/h",   lambda x: x/1000),  # uR/h -> mR/h
    }
    # yapf: enable

    def __init__(self, bytestr: bytes) -> None:
        """
        Create a status object from a bytes object.
        """
        self._data: Dict[str, Union[int, bool]] = \
            RadAlertHIDStatus.unpack(bytestr)
        self.type: str = "status"

    @property
    def cps(self) -> int:
        """
        Number of counts observed in the last second.
        """
        return self._data["cps"]

    @property
    def cpm(self) -> float:
        """
        Average number of counts per minute.
        """
        raise NotImplementedError("CPM data is not available")

    @property
    def id(self) -> int:
        """
        Rolling ID number of this packet.
        """
        return self._data["id"]

    @property
    def is_charging(self) -> bool:
        """
        Flag indicating if the device is charging.
        """
        return True

    @property
    def battery_percent(self) -> Optional[float]:
        """
        Battery percentage, or None if not available.
        """
        return None

    @property
    def alarm_state(self) -> generic.RadAlertStatus.AlarmState:
        """
        Current device alarm state (disabled, set, alerting, etc.)
        """
        raise NotImplementedError("Alarm state is not available")

    @property
    def display_value(self) -> float:
        """
        Value being displayed on screen in the current mode.

        See also: display_units()
        """
        mode = self._data["mode"]
        value = self._data["value"]
        info = RadAlertHIDStatus._MODE_DISPLAY_INFO[mode]
        return info[1](value)

    @property
    def display_units(self) -> str:
        """
        Units associated with the current mode.

        See also: display_value()
        """
        mode = self._data["mode"]
        info = RadAlertHIDStatus._MODE_DISPLAY_INFO[mode]
        return info[0]

    @property
    def _unknown(self) -> List[Tuple[int, int]]:
        """
        Unknown data contained within the packet.
        """
        # yapf: disable
        return [
            (int(self._data["unknown1"]), 0),  # 8 bits?
            (int(self._data["unknown2"]), 0x0000),  # 2 bytes? Number of memory locations used?
        ]
        # yapf: enable

    @staticmethod
    def unpack(bytestr: bytes) -> Dict[str, Union[int, bool]]:
        """
        Attempt to unpack a status packet.

        Returns a dictionary of unpacked values, or throws an exception
        if this was not possible.

        Dictionary keys:
          * cps:    Number of counts measured in the last second
          * id:     8-bit counter which increments with each packet
          * value:  Value currently displayed on screen (scaled)
          * mode:   Device's current mode number (affects meaning & scale of "value")
          * unknown1: 8-bit value with unknown purpose
          * unknown2: 16-bit value with unknown purpose
        """
        keys = ("cps", "id", "value", "mode", "unknown1", "unknown2")
        values = struct.unpack("<IBIBBI", bytestr)
        data = dict(zip(keys, values))

        RadAlertHIDStatus._validate(data)
        return data

    @staticmethod
    def _validate(data: Dict[str, Union[int, bool]]) -> None:
        """
        Check that the unpacked dictionary data is reasonable.
        """
        if data["cps"] > 7500 * 100 or data["cps"] < 0:
            # It isn't clear what the maximum value actually is, but the
            # manual says that the devices won't saturate in a field
            # 100 times the maximum reading. Its unlikely that the device
            # will actually report values 100x the spec, but just to be
            # safe, lets assume it does. Maximum CPS specs are 7500 for
            # the 1000EC, 5000 for the Ranger, and 3923 for the Monitor
            # 200.
            raise ValueError(
                f'cps = {data["cps"]} is unreasonably large or negative')

        if data["mode"] not in RadAlertHIDStatus._MODE_DISPLAY_INFO:
            raise ValueError(f'mode = {data["mode"]} is not a known state')


class RadAlertHIDQuery(generic.RadAlertQuery):
    """
    Representation of a query packet from a RadAlertHID device.

    Not all fields in the query packet have been deciphered yet.
    """
    def __init__(self, bytestr: bytes) -> None:
        """
        Create a status object from a bytes object.
        """
        self._data: Dict[str, Union[str, int,
                                    bool]] = RadAlertHIDQuery.unpack(bytestr)
        self.type: str = "query"

    @property
    def alarm_is_set(self) -> bool:
        """
        Flag indicating if the device's alarm has been set.
        """
        return bool(self._data["alarm_set"])

    @property
    def auto_averaging_enabled(self) -> bool:
        """
        Flag indicating if the device's auto-averaging mode is enabled.

        Auto-averaging mode causes the device to change its averaging
        time depending on recent raditation levels. The device manual
        will specify the averaging times and levels. When disabled,
        averaging may still be present, but will not be automatically
        adjusted.
        """
        return bool(self._data["auto_averaging"])

    @property
    def alarm_level(self) -> int:
        """
        Current alarm level in CPS (even if alarm is disabled).
        """
        return int(self._data["alarm"])

    @property
    def audible_beeps(self) -> bool:
        """
        Flag indicatating if the device will produce audible beeps.
        """
        return bool(self._data["audible_beeps"])

    @property
    def audible_clicks(self) -> bool:
        """
        Flag indicating if the device will produce audible detection clicks.
        """
        return bool(self._data["audible_clicks"])

    @property
    def backlight_duration(self) -> int:
        """
        Number of seconds that the backlight will remain on.
        """
        return int(self._data["backlight_duration"])

    @property
    def calibration_date(self) -> Optional[datetime.datetime]:
        """
        Return the date of last calibration, or None if not set.
        """
        default_cal_date = datetime.datetime(2000, 1, 1)
        calibration_date = datetime.datetime(
            int(self._data["year"]) + 2000, int(self._data["month"]),
            int(self._data["day"]))
        if calibration_date == default_cal_date:
            return None
        else:
            return calibration_date

    @property
    def contrast(self) -> float:
        """
        Display contrast percentage.
        """
        # TODO: What is maximum contrast?
        return int(self._data["contrast"]) / 64.0

    @property
    def conversion_factor(self) -> float:
        """
        Conversion factor from CPM to mR/h.

        Divide a CPM count by this value to transform it into an
        approximate dose rate in mR/h.
        """
        return int(self._data["conv"])

    @property
    def count_duration(self) -> int:
        """
        Number of seconds the device will perform a timed count for.
        """
        return int(self._data["count_duration"])

    @property
    def datalog_enabled(self) -> bool:
        """
        Flag indicating if the datalog function is enabled.
        """
        return bool(self._data["datalog_enabled"])

    @property
    def datalog_interval(self) -> int:
        """
        Number of minutes between datalog samples.
        """
        return int(self._data["datalog_interval"])

    @property
    def datalog_is_circular(self) -> bool:
        """
        Flag indicating if the datalog writes to a circular buffer.
        """
        return bool(self._data["datalog_circular"])

    @property
    def deadtime(self) -> float:
        """
        Tube deadtime in seconds.
        """
        return 1 / int(self._data["dead"])

    @property
    def serial_number(self) -> int:
        """
        Serial number of the device.
        """
        return int(str(self._data["serial"]).lstrip('\x00'))

    @property
    def _unknown(self) -> List[Tuple[int, int]]:
        """
        Unknown data contained within the packet.
        """
        # yapf: disable
        return [
            # Named isotope?
            (int(self._data["unkA1"]), ord('\0')), (int(self._data["unkA2"]), ord('\0')),
            (int(self._data["unkA3"]), ord('C')), (int(self._data["unkA4"]), ord('o')),
            (int(self._data["unkA5"]), ord('-')), (int(self._data["unkA6"]), ord('6')),
            (int(self._data["unkA7"]), ord('0')),

            #  Always zero?
            (int(self._data["unkB1"]), 0), (int(self._data["unkB2"]), 0),

            # Always zero?
            (int(self._data["unk1"]), 0),

            # Always zero?
            (int(self._data["unk2"]), 0),

            # Always zero?
            (int(self._data["unkC1"]), 0), (int(self._data["unkC2"]), 0),

            # Always 0x217?
            (int(self._data["unkD1"]), 0x02), (int(self._data["unkD2"]), 0x17),

            # Always zero?
            (int(self._data["unkE"]), 0),

            # Calibration data (reciprocal efficiencies?) for 8
            # pre-programmed isotopes?
            # C-14, S-35, Cs-137, P-32, Co-60, Sr/Y-90, I-131, Alpha
            (int(self._data["unkF1"]), 0x2710), (int(self._data["unkF2"]), 0x2710),
            (int(self._data["unkF3"]), 0x2710), (int(self._data["unkF4"]), 0x2710),
            (int(self._data["unkF5"]), 0x2710), (int(self._data["unkF6"]), 0x2710),
            (int(self._data["unkF7"]), 0x2710), (int(self._data["unkF8"]), 0x2710),

            # Always 0xFF list?
            (int(self._data["unkG1"]), 0xFF), (int(self._data["unkG2"]), 0xFF),
            (int(self._data["unkG3"]), 0xFF), (int(self._data["unkG4"]), 0xFF),
            (int(self._data["unkG5"]), 0xFF), (int(self._data["unkG6"]), 0xFF),
            (int(self._data["unkG7"]), 0xFF), (int(self._data["unkG8"]), 0xFF),
            (int(self._data["unkG9"]), 0xFF), (int(self._data["unkG10"]), 0xFF),
            (int(self._data["unkG11"]), 0xFF)
        ]
        # yapf: enable

    @staticmethod
    def _unpack_to_dict(
            fieldspec: List[Tuple[str, int, str]],
            bytestr: bytes,
            alignment: str = '',
            x_as_unknown: bool = False) -> Dict[str, Union[str, int, bool]]:
        """
        Helper method to unpack a byte string into a dictionary.

        Use a "fieldspec" definition (list of (name, repeat, type) tuples)
        to unpack a byte string into a dictionary. Repeated non-string
        elements get a numeric suffix indicating which item they are.
        """
        format_str = alignment
        field_names = []

        for name, repeat, fmt in fieldspec:
            if x_as_unknown and fmt == 'x':
                fmt = 'B'

            format_str = format_str + str(repeat) + fmt

            if fmt == 'x':
                continue

            if fmt == 's':
                field_names.append(name)
            else:
                for i in range(0, repeat):
                    if repeat > 1:
                        field_names.append(name + str(i))
                    else:
                        field_names.append(name)

        values = struct.unpack(format_str, bytestr)
        data = dict(zip(field_names, values))
        return data

    @staticmethod
    def unpack(bytestr: bytes) -> Dict[str, Union[str, int, bool]]:
        """
        Attempt to unpack a query packet.

        Returns a dictionary of unpacked values, or throws an exception
        if this was not possible.

        Dictionary keys:
          * serial:       ASCII string representation of the unit's serial number
          * unkA:         ASCII string representation of a named isotope (why?)
          * unkB:         Unknown value
          * alarm:        Current alarm value in CPM (even if disabled)
          * unkC:         Unknown value
          * day:          Day number of last calibration
          * unkD:         Unknown value
          * month:        Month number of last calibration
          * unkE:         Unknown value
          * year:         Year number of last calibration, starting at 2020
          * contrast:     LCD contrast setting
          * deadtime:     Reciprocal of tube deadtime in seconds (e.g. 1000 = 0.001 s)
          * unkF:         Unknown value(s)
          * counttime:    Length of time in seconds to perform a timed count for (default: 600)
          * lighttime:    Length of time in seconds the backlight should be enabled for
          * conv:         Calibration conversion factor in CPM/(mR/h)
          * unkG:         Unknown value(s)
          * interval:     Length of time in minutes to wait between datalogging samples (default: 1)
          * auto_avg:     Flag indicating if auto-averaging is enabled
          * buf_circular: Flag indicating if the datalogging buffer is treated as circular
          * alarm_set:    Flag indicating if the alarm is set
          * clicks_on:    Flag indicating if the unit will produce audible clicks for each detection event
          * silent:       Flag indicating if the unit will not produce audible beeps
          * unk1:         Unknown status flag
          * datalogging:  Flag indicating if the unit's datalogging function is active
          * unk2:         Unknown status flag
        """
        # yapf: disable
        fields = [
            ("serial",    7, "s"),          # Serial (ASCII):       00 31 30 31 39 34 38
            ("unkA",      7, "x"),          # Unknown (ASCII):      00 00 43 6f 2d 36 30
            ("unkB",      2, "x"),          # Unknown:              00 00
            ("status",    1, "B"),          # Mode number:          11
            ("alarm",     1, "H"),          # Alarm CPM:            2e 04
            ("unkC",      2, "x"),          # Unknown:              00 00
            ("day",       1, "B"),          # Calibration day:      01
            ("unkD",      2, "x"),          # Unknown:              02 17
            ("month",     1, "B"),          # Calibration month:    01
            ("year",      1, "B"),          # Calibration year:     00
            ("unkE",      1, "x"),          # Unknown:              00
            ("contrast",  1, "B"),          # LCD contrast:         19
            ("dead",  1, "H"),              # Recip. deadtime:      67 2B
            ("unkF",      8, "H"),          # Recip. efficiencies
                                            # of 8 isotopes (C-14
                                            # S-35, Cs-137, P-32,
                                            # Co-60, Sr/Y-90,
                                            # I-131, Alpha):        10 27 10 27 10 27 10 27 10 27 10 27 10 27 10 27
            ("count_duration", 1, "H"),     # Count mode time (s):  58 02
            ("backlight_duration", 1, "B"), # Backlight time (s):   07
            ("conv",      1, "H"),          # CPM/(mR/H) convers:   2e 04
            ("datalog_interval",  1, "H"),  # Datalogging interval: 01 00
            ("unkG",     11, "x"),          # Unknown:              ff ff ff ff ff ff ff ff ff ff ff
        ]
        # yapf: enable
        data = RadAlertHIDQuery._unpack_to_dict(fields, bytestr, '<', True)

        # Unpack the status byte into its individual fields
        status: int = int(data["status"])
        # yapf: disable
        data["auto_averaging"]   = bool((status >> 0) & 1)
        data["datalog_circular"] = bool((status >> 1) & 1)
        data["alarm_set"]        = bool((status >> 2) & 1)
        data["audible_clicks"]   = bool((status >> 3) & 1)
        data["audible_beeps"]    = bool((status >> 4) & 1)
        data["unk1"]             = bool((status >> 5) & 1)
        data["datalog_enabled"]  = bool((status >> 6) & 1)
        data["unk2"]             = bool((status >> 7) & 1)
        # yapf: enable

        del data["status"]

        RadAlertHIDQuery._validate(data)
        return data

    @staticmethod
    def _validate(data: Dict[str, Union[str, int, bool]]) -> None:
        """
        Check that the unpacked dictionary data is reasonable.
        """
        #serial: str = str(data["serial"])
        #if not bool(re.match("^\x00*[0-9]+$", serial)):
        #    raise ValueError(f'serial = {data["serial"]} has invalid format')

        alarm: int = int(data["alarm"])
        if alarm > 235400 or alarm < 0:
            raise ValueError(f'alarm = {data["alarm"]} outside expected range')

        year: int = int(data["year"])
        month: int = int(data["month"])
        day: int = int(data["day"])
        datetime.datetime(year + 2000, month, day)

        # TODO: What is maximum contrast?
        contrast: int = int(data["contrast"])
        if contrast > 64 or contrast < 0:
            raise ValueError(f'contrast = {data["contrast"]} '
                             'outside expected range')

        dead: int = int(data["dead"])
        if dead == 0:
            raise ValueError(f'dead = {data["dead"]} may not be zero')

        count_duration: int = int(data["count_duration"])
        if count_duration >= 24 * 60 * 60 or count_duration < 1:
            raise ValueError(f'count_duration = {data["count_duration"]} '
                             'outside expected range')

        # TODO: What is maximum backlight duration?
        backlight_duration: int = int(data["backlight_duration"])
        if backlight_duration > 30 or backlight_duration < 0:
            raise ValueError(
                f'backlight_duration = {data["backlight_duration"]} '
                'outside expected range')

        conv: int = int(data["conv"])
        if conv > 7000 or conv < 200:
            raise ValueError(f'conv = {data["conv"]} outside expected range')

        # TODO: What is maximum datalog interval?
        datalog_interval: int = int(data["datalog_interval"])
        if datalog_interval > 60 or datalog_interval < 1:
            raise ValueError(f'datalog_interval = {data["datalog_interval"]} '
                             'outside expected range')


class RadAlertHID(generic.RadAlert):
    """
    USB HID client implementation for the Radiation Alert series
    of devices from SE International.
    """
    _ACK = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    _START = b'\x46\x00\x00\x00\x00\x00\x00\x00'

    def _reset(self) -> None:
        self._command_buffer: List[Tuple[int, int]] = []
        self._receive_buffer: bytes = b''
        self._poll_buffer: bytes = b''
        self._last_id: Optional[int] = None
        self._sync_count: int = 0

    def __init__(self, status_callback: Callable[[RadAlertHIDStatus], None],
                 query_callback: Callable[[RadAlertHIDQuery], None]) -> None:
        self.status_callback: \
            Callable[[RadAlertHIDStatus], None] = status_callback
        self.query_callback: \
            Callable[[RadAlertHIDQuery], None] = query_callback
        self._hiddev = hid.device()
        self._reset()

    def __del__(self) -> None:
        self.disconnect()

    def connect(self, vid: int, pid: int) -> None:
        self.disconnect()
        print("Connecting...", file=sys.stderr)
        self._hiddev.open(vid, pid)

    def disconnect(self) -> None:
        print("Disconnecting...", file=sys.stderr)
        if self._hiddev is not None:
            self._hiddev.close()
        self._reset()

    def trigger_query(self) -> RadAlertHIDQuery:
        """
        Immediately request that we send a query request to the device.

        We may periodically send a query request on our own over the
        course of keeping the connection alive / current, but this method
        can be used to force an update.
        """
        query = bytearray(self._hiddev.get_feature_report(0x00, 65))[1:]
        self._start()
        return RadAlertHIDQuery(query)

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
        while True:
            iteration: int = 0
            self._start()
            while self._wait_for_data(self._on_receive, 4.0):
                iteration += 1
                if iteration % 5 == 0:
                    query = self.trigger_query()
                    self.query_callback(query)
            print("Timeout while waiting for HID report", file=sys.stderr)

    def _decode(self) -> Optional[RadAlertHIDStatus]:
        if len(self._receive_buffer) != 15:
            return None
        #print(f'Decoding {self._receive_buffer.hex()}', file=sys.stderr)
        data: RadAlertHIDStatus = RadAlertHIDStatus(self._receive_buffer)

        if self._last_id is not None:
            if (self._last_id + 1) % 256 != data.id:
                last_id: int = self._last_id
                self._last_id = None
                raise ValueError(f'Packet ID jump: {last_id} to {data.id}')

        self._last_id = data.id

        for value, expect in data._unknown:
            if value != expect:
                print(
                    f'NOTE: Data parsed from {self._receive_buffer.hex()}'
                    ' has unexpected unknown field values:'
                    f' {data._unknown}',
                    file=sys.stderr)

        self._receive_buffer = b''
        print(data._data)
        return data

    def _start(self) -> None:
        self._hiddev.write(RadAlertHID._START)

    def _poll(self) -> Optional[bytes]:
        """
        Poll the device for new data.

        The HID read request for this device repeatedly returns the same
        packet over and over until it finally changes. To ensure we don't
        process the same data multiple times, this function also deduplicates
        the stream.

        To keep track of the poll state, this function is a generator
        which yeilds either a new set of bytes or None if the data is
        unchagned.
        """
        bytestr = bytes(self._hiddev.read(25))
        if bytestr == self._poll_buffer:
            return None
        self._poll_buffer = bytestr
        return bytestr

    def _wait_for_data(self,
                       callback: Callable[[bytes], None],
                       timeout: float,
                       sleep: float = 0.2):
        """
        Wait to recieve new data for a limited amount of time.

        Repeatedly poll the device until either new data is available
        or the timeout is exceeded. When new data is available, call
        the callback with it. Return `True` if the timeout did not
        expire or `False` otherwise.
        """
        end_time = time.monotonic() + timeout
        while True:
            data = self._poll()
            if data is not None:
                callback(data)
                return True
            if time.monotonic() > end_time:
                return False
            time.sleep(sleep)

    def _on_receive(self, bytestr: bytes) -> None:
        self._receive_buffer = bytestr
        self._process()
        #while len(self._command_buffer) > 0:
        #    message = self._command_buffer.pop(0)
        #    self._send_command(message)

    def _process(self) -> None:
        self._synchronize()
        while self._synchronized():
            #print(f'Processing {self._receive_buffer.hex()}', file=sys.stderr)
            try:
                data = self._decode()
                if data is None:
                    break
                self._send_ack()
                self.status_callback(data)
            except Exception as e:
                print(
                    "Failed to parse from:"
                    f"{self._receive_buffer.hex()}\n{e}",
                    file=sys.stderr)
                self._desynchronize()

    def _send_ack(self) -> None:
        self._hiddev.write(RadAlertHID._ACK)

    def _synchronize(self) -> None:
        """
        Synchronize the HID packets to flush out stale data.

        After a disconnect the first packet that we get may have stale
        data which trips up the packet ID check. We need to flush any
        such stale packets out of the system before we can reliably
        decode the data.
        """
        while not self._synchronized():
            #print(f'Synchronizing {self._receive_buffer.hex()}', file=sys.stderr)
            try:
                if self._decode() is None:
                    break
                self._send_ack()
                self._sync_count += 1
                print(f"Decode success {self._sync_count}", file=sys.stderr)
            except Exception as e:
                print(f"Decode failure: {e}", file=sys.stderr)
                self._sync_count = 0
                self._last_id = None

    def _desynchronize(self) -> None:
        self._sync_count = 0

    def _synchronized(self) -> bool:
        return self._sync_count >= 5
