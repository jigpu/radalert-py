"""
BLE serial protocol implmentation for Radiation Alert geiger counters.

The recent Radiation Alert series of geiger counters from SE International
provide a Bluetooth LE connection that can be used to communicate with the
device. This module implements the serial protocol used by this connection,
decoding the packets into a form which is more easily usable.

There are still some unknown components of this protocol, but its current
state is good enough for most basic work :)
"""

import sys
import struct
from enum import Enum
from typing import Callable, Dict, List, NoReturn, Optional, Tuple, Union
from bluepy.btle import Peripheral

from radalert._util.ble import TransparentService


class RadAlertLEStatus:
    """
    Representation of a status packet from a RadAlertLE device.

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

    class AlarmState(Enum):
        """Enumeration of possible alarm states."""
        DISABLED = 1
        SET = 2
        ALERTING = 3
        SILENCED = 4

    def __init__(self, bytestr: bytes) -> None:
        """
        Create a status object from a bytes object.
        """
        self._data: Dict[str, Union[int, bool]] = \
            RadAlertLEStatus.unpack(bytestr)
        self.type: str = "status"

    @property
    def cps(self) -> int:
        """Get the number of counts observed in the last second."""
        return self._data["cps"]

    @property
    def cpm(self) -> float:
        """Get the average number of counts per minute."""
        return self._data["cpm"]

    @property
    def id(self) -> int:
        """Get the rolling ID number of this packet."""
        return self._data["id"]

    @property
    def is_charging(self) -> bool:
        """Get a bool indicating if the device is charging."""
        return self._data["power"] == 5

    @property
    def battery_percent(self) -> Optional[float]:
        """Get the battery percentage, or None if not available."""
        return None if self.is_charging else \
            self._data["power"] / 4 * 100

    @property
    def alarm_state(self) -> AlarmState:
        """Get the current alarm state."""

        # This chain of conditions must be kept in priority order
        if self._data["alarm_silenced"]:
            return RadAlertLEStatus.AlarmState.SILENCED
        elif self._data["alarm_alerting"]:
            return RadAlertLEStatus.AlarmState.ALERTING
        elif self._data["alarm_set"]:
            return RadAlertLEStatus.AlarmState.SET
        else:
            return RadAlertLEStatus.AlarmState.DISABLED

    @property
    def display_value(self) -> float:
        """
        Get the on-screen value being displayed in the current mode.

        See also: display_units()
        """
        mode = self._data["mode"]
        value = self._data["value"]
        info = RadAlertLEStatus._MODE_DISPLAY_INFO[mode]
        return info[1](value)

    @property
    def display_units(self) -> str:
        """
        Get the units associated with the current mode.

        See also: display_value()
        """
        mode = self._data["mode"]
        info = RadAlertLEStatus._MODE_DISPLAY_INFO[mode]
        return info[0]

    @property
    def _unknown(self) -> List[Tuple[int, int]]:
        """
        Get the unknown data contained within the packet.

        The first value is either a 2-bit value or two flag bits.
        The second value is a single byte long.
        """
        return [(self._data["unknown"], 0), (self._data["unk1"], 0)]

    @staticmethod
    def unpack(bytestr: bytes) -> Dict[str, Union[int, bool]]:
        """
        Attempt to unpack a status packet.

        Returns a dictionary of unpacked values, or throws an exception
        if this was not possible.

        Dictionary keys:
          * cps:    Number of counts measured in the last second
          * value:  Value currently displayed on screen (scaled)
          * mode:   Device's current mode number (affects meaning of "value")
          * unk1:   Unknown value, usually 0. Have seen 0x15 before.
          * id:     8-bit counter which increments with each packet
          * cpm:    Current average counts per minute
          * power:  Battery level / charging indication
          * alarm_active:   Flag: radiation alarm has been tripped
          * alarm_set:      Flag: radiation alarm is set
          * alarm_silenced: Flag: radiation alarm has been silenced
          * unknown: 2-bit value or pair of flags with unknown purpose
        """
        keys = ("cps", "value", "mode", "cpm_lo", "cpm_hi", "unk1", "status",
                "id")
        values = struct.unpack("<2IHHB3B", bytestr)
        data = dict(zip(keys, values))

        # Merge the two CPM sub-fields into a single 3-byte value
        data["cpm"] = data["cpm_lo"] + (data["cpm_hi"] << 16)
        del data["cpm_lo"]
        del data["cpm_hi"]

        # Unpack the status byte into its individual fields
        status = data["status"]

        # yapf: disable
        data["power"]          =      (status >> 0) & 7
        data["alarm_alerting"] = bool((status >> 3) & 1)
        data["alarm_set"]      = bool((status >> 4) & 1)
        data["alarm_silenced"] = bool((status >> 5) & 1)
        data["unknown"]        =      (status >> 6) & 3
        # yapf: enable

        del data["status"]

        RadAlertLEStatus._validate(data)
        return data

    @staticmethod
    def _validate(data: Dict[str, Union[int, bool]]) -> None:
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

        if data["cpm"] > 7500 * 60 or data["cpm"] < 0:
            # Only three bytes appear to be available for CPM, so 100x
            # would not fit. Limit this to just just the maximum times
            # 60 (to transform into CPM)
            raise ValueError(
                f'cpm = {data["cpm"]} is unreasonably large or negative')

        if data["power"] > 5 or data["power"] < 0:
            raise ValueError(f'power = {data["power"]} is not a known state')

        if data["alarm_alerting"] and not data["alarm_set"]:
            raise ValueError("Alarm cannot be alerting if not set")

        if data["alarm_silenced"] and not data["alarm_alerting"]:
            raise ValueError("Alarm cannot be silenced if not alerting")

        if data["mode"] not in RadAlertLEStatus._MODE_DISPLAY_INFO:
            raise ValueError(f'mode = {data["mode"]} is not a known state')


class RadAlertLEQuery:
    """
    Representation of a query packet from a RadAlertLE device.

    Not all fields in the query packet have been deciphered yet.
    """
    def __init__(self, bytestr: bytes) -> None:
        """
        Create a status object from a bytes object.
        """
        self._data: Dict[str, int] = RadAlertLEQuery.unpack(bytestr)
        self.type: str = "query"

    @property
    def alarm_level(self) -> int:
        """Get the current alarm level in CPS (even if alarm is disabled)."""
        return self._data["alarm"]

    @property
    def conversion_factor(self) -> float:
        """
        Get the conversion factor from CPM to mR/h.

        Divide a CPM count by this value to transform it into an
        approximate dose rate in mR/h.
        """
        return self._data["conv"]

    @property
    def deadtime(self) -> float:
        """
        Get the tube deadtime in seconds.
        """
        return 1 / self._data["dead"]

    @property
    def _unknown(self) -> List[Tuple[int, int]]:
        """
        Get the unknown data contained within the packet.

        This is a tuple of unknown values in the order they are found
        in the packet. Since they are unknown, their data boundaries
        are not necessarily correct...
        """
        return [(self._data["unk1"], 0xFFFFFFFF), (self._data["unk2"], 0),
                (self._data["unk4"], 0xFFFFFFFF)]

    @staticmethod
    def unpack(bytestr: bytes) -> Dict[str, int]:
        """
        Attempt to unpack a query packet.

        Returns a dictionary of unpacked values, or throws an exception
        if this was not possible.

        Dictionary keys:
          * unk1:  Unknown value; always set to 0xFFFFFFFF on my unit
          * alarm: Current alarm value in CPM (even if disabled)
          * unk2:  Unknown value; always set to 0x0000 on my unit
          * dead:  Deadtime fraction; 1/dead == tube deadtime in seconds
          * conv:  Calibration conversion factor in CPM/(mR/h)
          * unk4:  Unknown value; always set to 0xFFFFFFFF on my unit
        """
        keys = ("unk1", "alarm", "unk2", "dead", "conv", "unk4")
        values = struct.unpack("<I4HI", bytestr)
        data = dict(zip(keys, values))

        RadAlertLEQuery._validate(data)
        return data

    @staticmethod
    def _validate(data: Dict[str, int]) -> None:
        if data["alarm"] > 235400 or data["alarm"] < 0:
            raise ValueError(f'alarm = {data["alarm"]} outside expected range')
        if data["dead"] == 0:
            raise ValueError(f'dead = {data["dead"]} may not be zero')
        if data["conv"] > 7000 or data["conv"] < 200:
            raise ValueError(f'conv = {data["conv"]} outside expected range')


class RadAlertLE:
    """
    Bluetooth LE client implementation for the Radiation Alert series
    of devices from SE International.

    These devices expose several "vendor specific" services from ISSC /
    Microchip. The only service of note at the moment (because we know
    what it does) is the "transparent UART" that allows us to set up
    a serial connection with the device.

    The serial protocol used is not documented, though a few behaviors
    have been discovered. The device sends periodic updates    immediately
    after setting up the UART connection, but will timeout if we don't
    keep sending "X" in response to each message. The device also
    reacts to a "?" command which causes the device to send a single
    reply with a different set of data. The only other command found
    so far is "Z" which immediately terminates the connection.

    Curiously, it almost seems like you have to send your command **and
    then** send X. If you send X and then the command, or [X, command, X]
    things don't work right. Its kinda like X is "execute last command"
    (or ack if no last command), aside from that last observation...
    """
    # yapf: disable
    _COMMAND_STRING: Dict[str, str] = {
        "query":     "?",
        "terminate": "Z",
        "ack":       "X",
    }
    # yapf: enable
    _COMMAND_ENDL: str = "\n"

    def _reset(self) -> None:
        self._peripheral: Optional[Peripheral] = None
        self._service: Optional[TransparentService] = None
        self._command_buffer: List[str] = []
        self._receive_buffer: bytes = b''
        self._last_id: Optional[int] = None
        self._sync_count: int = 0

    def __init__(
        self,
        packet_callback: Callable[[Union[RadAlertLEStatus, RadAlertLEQuery]],
                                  None]
    ) -> None:
        self.packet_callback: \
            Callable[[Union[RadAlertLEStatus, RadAlertLEQuery]],
                     None] = packet_callback
        self._peripheral = None
        self._reset()

    def __del__(self) -> None:
        self.disconnect()

    def connect(self, address: str) -> None:
        self.disconnect()
        self._peripheral = Peripheral(address)
        # info_service = DeviceInfoService(self._peripheral)
        # print(info_service.get_information())
        self._service = TransparentService(self._peripheral, self._on_receive)

    def disconnect(self) -> None:
        if self._peripheral is not None:
            self._peripheral.disconnect()
        self._reset()

    def trigger_query(self) -> None:
        """
        Immediately request that we send a query request to the device.

        We may periodically send a query request on our own over the
        course of keeping the connection alive / current, but this method
        can be used to force an update.
        """
        self._command_buffer.append(self._COMMAND_STRING["query"])

    def spin(self) -> NoReturn:
        """
        Spin our wheels reading data from the device.

        This is a temporary method to allow us to simply monitor what
        the device is sending. Calling this method enters an infinite
        loop that keeps the connection alive and prints out status
        updates each time we get something new from the device.

        The only way we leave this method is due to a problems with
        Bluetooth. BTLEDisconnectError or similar may be raised, for
        example.
        """
        if self._peripheral is None:
            raise RuntimeError("Peripheral has not been initialized")
        while True:
            iteration: int = 0
            while self._peripheral.waitForNotifications(4.0):
                iteration += 1
                if iteration % 5 == 0:
                    self.trigger_query()
            print("Timeout while waiting for BLE notification",
                  file=sys.stderr)

    def _decode(self) -> Union[None, RadAlertLEQuery, RadAlertLEStatus]:
        if len(self._receive_buffer) < 16:
            return None
        packet: bytes = self._receive_buffer[0:16]
        data: Union[None, RadAlertLEQuery, RadAlertLEStatus] = None

        if packet[0:4] == b'\xff\xff\xff\xff':
            data = RadAlertLEQuery(packet)
        else:
            data = RadAlertLEStatus(packet)

            if self._last_id is not None:
                if (self._last_id + 1) % 256 != data.id:
                    last_id: int = self._last_id
                    self._last_id = None
                    raise ValueError(f'Packet ID jump: {last_id} to {data.id}')

            self._last_id = data.id

        if data is not None:
            for value, expect in data._unknown:
                if value != expect:
                    print(
                        f'NOTE: Data parsed from {self._receive_buffer.hex()}'
                        ' has unexpected unknown field values.',
                        file=sys.stderr)
                    break

        return data

    def _on_receive(self, bytestr: bytes) -> None:
        self._receive_buffer += bytestr
        self._process()
        while len(self._command_buffer) > 0:
            message = self._command_buffer.pop(0)
            self._send_command(message)

    def _process(self) -> None:
        self._synchronize()
        while self._synchronized():
            data: Union[None, RadAlertLEQuery, RadAlertLEStatus] = None

            try:
                data = self._decode()
                self._receive_buffer = self._receive_buffer[16:]
            except Exception as e:
                print(
                    "Failed to parse from:"
                    f"{self._receive_buffer.hex()}\n{e}",
                    file=sys.stderr)
                self._desynchronize()

            self._send_ack()
            if data is not None:
                self.packet_callback(data)
            else:
                break

    def _send_command(self, command: str) -> None:
        if self._service is None:
            raise RuntimeError("Service has not been initialized")
        self._service.send_string(command + self._COMMAND_ENDL)

    def _send_ack(self) -> None:
        self._command_buffer.append(self._COMMAND_STRING["ack"])

    def _synchronize(self) -> None:
        """
        Synchronize the receive buffer to begin at a packet boundary.

        The data we recieve over Bluetooth is not necessarily aligned
        at packet boundaries. If we start failing to decode packets
        then we've probably fell out of sync with the stream somehow.
        This might be because the connection was temporarily interrupted
        and then resumed at some place that wasn't a packet boundary.
        In any case, drop bytes from the buffer until we can reliably
        start decoding packets again.
        """
        while not self._synchronized():
            try:
                if self._decode() is None:
                    break
                else:
                    self._sync_count += 1
                    self._send_ack()
            except Exception:
                self._receive_buffer = self._receive_buffer[1:]
                self._sync_count = 0
                self._last_id = None

    def _desynchronize(self) -> None:
        self._sync_count = 0

    def _synchronized(self) -> bool:
        return self._sync_count >= 5
