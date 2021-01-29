"""
Bluetooth Low Energy (BLE) service implementations.

This module uses the bluepy library to implment the (PC) client side of
a BLE connection to various services.
"""

from typing import Callable, Dict

from bluepy.btle import BTLEException
from bluepy.btle import DefaultDelegate


class DeviceInfoService:
    """
    Client implementation of the Bluetooth LE "Device Information"
    service.

    The Radiation Alert devices appear to return information about the
    Bluetooth chip rather than the geiger counter itself.

    Example from a Radiation Alert Monitor200:
     * 'manufacturer':  'ISSC'
     * 'model_number':  'BM70'
     * 'serial_number': '0000'
     * 'hw_revision':   '5505 102_BLDK3'
     * 'fw_revision':   '01040101'
     * 'sw_revision':   '0000'
    """
    _UUID_SERVICE: str = "0000180a-0000-1000-8000-00805f9b34fb"
    _UUID_CHARACTERISTIC_MANUFACTURER: str = "00002a29-0000-1000-8000-00805f9b34fb"
    _UUID_CHARACTERISTIC_MODEL_NUMBER: str = "00002a24-0000-1000-8000-00805f9b34fb"
    _UUID_CHARACTERISTIC_SERIAL_NUMBER: str = "00002a25-0000-1000-8000-00805f9b34fb"
    _UUID_CHARACTERISTIC_HW_REVISION: str = "00002a27-0000-1000-8000-00805f9b34fb"
    _UUID_CHARACTERISTIC_FW_REVISION: str = "00002a26-0000-1000-8000-00805f9b34fb"
    _UUID_CHARACTERISTIC_SW_REVISION: str = "00002a28-0000-1000-8000-00805f9b34fb"

    def __init__(self, peripheral):
        try:
            self._service = peripheral.getServiceByUUID(self._UUID_SERVICE)
        except (BTLEException, IndexError) as exception:
            raise BTLEException("DeviceInfo service not found") from exception

    def _read_characteristic(self, uuid) -> str:
        try:
            char = self._service.getCharacteristics(forUUID=uuid)[0]
            return char.read()
        except (BTLEException, IndexError):
            return ""

    def get_information(self) -> Dict[str, str]:
        """
        Read and return information provided by the Device Information
        service.

        Returns a dictionary of some of the more interesting properties.
        The empty string will be used as the dictionary value for any
        characteristics that do not exist.
        """
        return {
            "manufacturer":  self._read_characteristic(DeviceInfoService._UUID_CHARACTERISTIC_MANUFACTURER),
            "model_number":  self._read_characteristic(DeviceInfoService._UUID_CHARACTERISTIC_MODEL_NUMBER),
            "serial_number": self._read_characteristic(DeviceInfoService._UUID_CHARACTERISTIC_SERIAL_NUMBER),
            "hw_revision":   self._read_characteristic(DeviceInfoService._UUID_CHARACTERISTIC_HW_REVISION),
            "fw_revision":   self._read_characteristic(DeviceInfoService._UUID_CHARACTERISTIC_FW_REVISION),
            "sw_revision":   self._read_characteristic(DeviceInfoService._UUID_CHARACTERISTIC_SW_REVISION),
        }


class TransparentService:
    """
    Client implementation of the Bluetooth LE "Transparent UART"

    The "Transparent UART" service is a (poorly documented) vendor-
    specific service used by some Microchip products. The BM70 chip,
    for example, provides this functionality. Transparent UART makes
    it trivial to set up a serial communication channel between a
    (peripheral) server and (PC) client.

    Be aware that the protocol is documented from the point of view
    of the (peripheral) servier -- not the (PC) client. This can be
    confusing! For example, the "RX" characteristic is what the
    server would be receiving from, but what we need to transmit to.
    Conversely, the "TX" characteristic is what the server is sending
    to and what we receive from.
    """
    _UUID_SERVICE: str = "49535343-FE7D-4AE5-8FA9-9FAFD205E455"
    _UUID_CHARACTERISTIC_TX: str = "49535343-1E4D-4BD9-BA61-23C647249616"
    _UUID_CHARACTERISTIC_RX: str = "49535343-8841-43F4-A8D4-ECBE34729BB3"
    _UUID_DESCRIPTOR_TX: str = "00002902-0000-1000-8000-00805f9b34fb"

    class _TransparentDelegate(DefaultDelegate):
        def __init__(self, callback: Callable[[bytes], None], handle: int) -> None:
            DefaultDelegate.__init__(self)
            self.callback = callback
            self.handle = handle

        def handleNotification(self, cHandle: int, data: bytes) -> None:
            if cHandle == self.handle:
                self.callback(data)

    def __init__(self, peripheral, callback: Callable[[bytes], None]) -> None:
        try:
            service = peripheral.getServiceByUUID(self._UUID_SERVICE)

            self._char_tx = service.getCharacteristics(forUUID=TransparentService._UUID_CHARACTERISTIC_TX)[0]
            self._char_rx = service.getCharacteristics(forUUID=TransparentService._UUID_CHARACTERISTIC_RX)[0]
            self._desc_tx = service.getDescriptors(forUUID=TransparentService._UUID_DESCRIPTOR_TX)[0]
        except (BTLEException, IndexError) as exception:
            raise BTLEException("Transparent UART service not found") from exception

        # Set up the notification delegate and turn them on
        delegate = self._TransparentDelegate(callback, self._char_tx.getHandle())
        peripheral.setDelegate(delegate)
        self._desc_tx.write(b'\x01\x00')

    def send_string(self, message: str, encoding: str = "utf-8") -> None:
        """
        Send a string message over the transparent UART connection.

        This method defaults to encoding the string in UTF-8. This can
        be overridden if you know that the peripheral expects something
        different.

        We do not append any kind of newline to the end of the message
        so be sure that you append one yourself if necessary.
        """
        self._char_rx.write(message.encode(encoding))

    def send_bytes(self, bytestr: bytes) -> None:
        """
        Send a raw string of bytes over the transparent UART connection.

        This method is primarily intended to be used in situations where
        the peripheral is expecting raw binary data rather an encoded
        string.
        """
        self._char_rx.write(bytestr)
