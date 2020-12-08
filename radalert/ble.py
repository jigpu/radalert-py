"""
BLE serial protocol implmentation for Radiation Alert geiger counters.

The recent Radiation Alert series of geiger counters from SE International
provide a Bluetooth LE connection that can be used to communicate with the
device. This module implements the serial protocol used by this connection,
decoding the packets into a form which is more easily usable.

There are still some unknown components of this protocol, but its current
state is good enough for most basic work :)
"""

import struct
from enum import Enum
from bluepy.btle import Peripheral
from bluepy.btle import BTLEDisconnectError

from radalert.util.ble import TransparentService


class RadAlertLEStatus:
    """
    Representation of a status packet from a RadAlertLE device.

    Not all fields in the status packet have been deciphered yet.
    """

    _MODE_DISPLAY_INFO = {
        0:  ("cpm",    lambda x: x),       # convert data from CPM
        1:  ("cps",    lambda x: x/10),    # convert data from centi-CPS
        2:  ("µR/h",   lambda x: x),       # convert data from uR/h
        3:  ("µSv/h",  lambda x: x/1000),  # convert data from nSv/h
        20: ("counts", lambda x: x),       # convert data from counts
        23: ("mR/h",   lambda x: x/1000),  # convert data from uR/h
    }

    class AlarmState(Enum):
        """Enumeration of possible alarm states."""
        DISABLED = 1
        SET = 2
        ALERTING = 3
        SILENCED = 4

    def __init__(self, bytestr):
        """
        Create a status object from a bytes object.
        """
        self._data = RadAlertLEStatus.unpack(bytestr)
        self.type = "status"

    @property
    def cps(self):
        """Get the number of counts observed in the last second."""
        return self._data["cps"]

    @property
    def cpm(self):
        """Get the average number of counts per minute."""
        return self._data["cpm"]

    @property
    def id(self):
        """Get the rolling ID number of this packet."""
        return self._data["id"]

    @property
    def is_charging(self):
        """Get a bool indicating if the device is charging."""
        return self._data["power"] == 5

    @property
    def battery_percent(self):
        """Get the battery percentage, or None if not available."""
        return None if self.is_charging else \
               self._data["power"] / 4 * 100

    @property
    def alarm_state(self):
        """Get the current alarm state."""
        return RadAlertLEStatus.AlarmState.SILENCED if self._data["alarm_silenced"] else \
               RadAlertLEStatus.AlarmState.ALERTING if self._data["alarm_alerting"] else \
               RadAlertLEStatus.AlarmState.SET      if self._data["alarm_set"]      else \
               RadAlertLEStatus.AlarmState.DISABLED

    @property
    def display_value(self):
        """
        Get the on-screen value being displayed in the current mode.

        See also: display_units()
        """
        mode = self._data["mode"]
        value = self._data["value"]
        info = RadAlertLEStatus._MODE_DISPLAY_INFO[mode]
        return info[1](value)

    @property
    def display_units(self):
        """
        Get the units associated with the current mode.

        See also: display_value()
        """
        mode = self._data["mode"]
        info = RadAlertLEStatus._MODE_DISPLAY_INFO[mode]
        return info[0]

    @property
    def unknown(self):
        """
        Get the unknown data contained within the packet.

        This is either a 2-bit value or two flag bits.
        """
        return self._data["unknown"]

    @staticmethod
    def unpack(bytestr):
        """
        Attempt to unpack a status packet.

        Returns a dictionary of unpacked values, or throws an exception
        if this was not possible.

        Dictionary keys:
          * cps:    Number of counts measured in the last second
          * value:  Value currently displayed on screen (scaled)
          * mode:   Device's current mode number (affects meaning & scale of "value")
          * cpm:    Current average counts per minute
          * id:     8-bit counter which increments with each packet
          * power:  Battery level / charging indication
          * alarm_active:   Flag indicating if the radiation alarm has been tripped
          * alarm_set:      Flag indicating if the radiation alarm is set
          * alarm_silenced: Flag indicating if the radiation alarm has been silenced
          * unknown: 2-bit value or pair of flags with unknown purpose
        """
        keys = ("cps", "value", "mode", "cpm", "status", "id")
        values = struct.unpack("<2IHI2B", bytestr)
        data = dict(zip(keys, values))

        # Unpack the status byte into its individual fields
        status = data["status"]
        data["power"]          =      (status >> 0) & 7
        data["alarm_alerting"] = bool((status >> 3) & 1)
        data["alarm_set"]      = bool((status >> 4) & 1)
        data["alarm_silenced"] = bool((status >> 5) & 1)
        data["unknown"]        =      (status >> 6) & 3
        del data["status"]

        return data


class RadAlertLEQuery:
    """
    Representation of a query packet from a RadAlertLE device.

    Not all fields in the query packet have been deciphered yet.
    """

    def __init__(self, bytestr):
        """
        Create a status object from a bytes object.
        """
        self._data = RadAlertLEQuery.unpack(bytestr)
        self.type = "query"

    @property
    def alarm_level(self):
        """Get the current alarm level in CPS (even if alarm is disabled)."""
        return self._data["alarm"]

    @property
    def conversion_factor(self):
        """
        Get the conversion factor from CPM to mR/h.

        Divide a CPM count by this value to transform it into an
        approximate dose rate in mR/h.
        """
        return self._data["conv"]

    @property
    def unknown(self):
        """
        Get the unknown data contained within the packet.

        This is a tuple of unknown values in the order they are found
        in the packet. Since they are unknown, their data boundaries
        are not necessarily correct...
        """
        return (self._data["unk1"],
                self._data["unk2"],
                self._data["unk3"],
                self._data["unk4"])

    @staticmethod
    def unpack(bytestr):
        """
        Attempt to unpack a query packet.

        Returns a dictionary of unpacked values, or throws an exception
        if this was not possible.

        Dictionary keys:
          * unk1:  Unknown value; always set to 0xFFFFFFFF on my unit
          * alarm: Current alarm value in CPM (even if disabled)
          * unk2:  Unknown value; always set to 0x0000 on my unit
          * unk3:  Unknown value; always set to 0x2B67 (1111 decimal) on my unit
          * conv:  Calibration conversion factor in CPM/(mR/h)
          * unk4:  Unknown value; always set to 0xFFFFFFFF on my unit
        """
        keys = ("unk1", "alarm", "unk2", "unk3", "conv", "unk4")
        values = struct.unpack("<I4HI", bytestr)
        return dict(zip(keys, values))


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
    _COMMAND_STRING = {
        "query":     "?",
        "terminate": "Z",
        "ack":       "X",
    }
    _COMMAND_ENDL = "\n"

    def __init__(self, address, packet_callback):
        self._command_buffer = []
        self._receive_buffer = b''
        self.packet_callback = packet_callback
        self._peripheral = None

        self._peripheral = Peripheral(address)
        #info_service = DeviceInfoService(self._peripheral)
        #print(info_service.get_information())
        self._service = TransparentService(self._peripheral, self._on_receive)

    def __del__(self):
        if self._peripheral is not None:
            self._peripheral.disconnect()

    def trigger_query(self):
        """
        Immediately request that we send a query request to the device.

        We may periodically send a query request on our own over the
        course of keeping the connection alive / current, but this method
        can be used to force an update.
        """
        self._command_buffer.append(self._COMMAND_STRING["query"])

    def spin(self):
        """
        Spin our wheels reading data from the device.

        This is a temporary method to allow us to simply monitor what
        the device is sending. Calling this method enters an infinite
        loop that keeps the connection alive and prints out status
        updates each time we get something new from the device.

        If the device never replies back in time, or we discover that
        the device has been disconnected, return. Otherwise, this is
        essentially an infinite loop.
        """
        try:
            iteration = 0
            while self._peripheral.waitForNotifications(10.0):
                iteration += 1
                if iteration % 5 == 0:
                    self.trigger_query()
        except BTLEDisconnectError:
            pass

    def _on_receive(self, bytestr):
        self._receive_buffer += bytestr
        self._decode()
        while len(self._command_buffer) > 0:
            message = self._command_buffer.pop(0)
            self._send_command(message)
        self._send_ack()

    def _send_command(self, command):
        self._service.send_string(command + self._COMMAND_ENDL)

    def _send_ack(self):
        self._send_command(self._COMMAND_STRING["ack"])

    def _decode(self):
        while len(self._receive_buffer) >= 16:
            data = None

            # Both the data types we've seen so far are 16 bytes
            # long; extract a chunk and figure out which it is
            packet = self._receive_buffer[0:16]
            self._receive_buffer = self._receive_buffer[16:]

            try:
                if packet[0:4] == b'\xff\xff\xff\xff':
                    data = RadAlertLEQuery(packet)
                else:
                    data = RadAlertLEStatus(packet)
            except struct.error as exception:
                print(f"Failed to parse: {packet}")
                print(exception)

            if data is not None:
                self.packet_callback(data)
