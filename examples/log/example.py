#!/usr/bin/env python3

"""
Example of a simple logging program which uses the radalert API.

This program connects to the first Radiation Alert Monitor200 device
that it can find over BLE. Once connected, it will begin gathering
events and performing statistics. Logs data will be printed out
periodically as tab-separated values. If the connection is interrupted
the program will remain running and try to connect again.

This module focuses on getting the connection set up (and resumed
if it fails). The heavy-lifting of the logging / statistics is
handled inside the logger module that lives alongside this example.

If you run this example without any arguments, it will start a BLE
scan for devices with "Mon200" in their name. This may require
root permissions. Alternatively, you can provide the address of a
specific device to connect to as a command-line argument and we
will attempt to connect to that device directly without needing
root rights.
"""

import sys
from threading import Thread

from logger import ConsoleLogger
from logger import LogBackend

from bluepy.btle import Scanner
from bluepy.btle import BTLEDisconnectError

from radalert.ble import RadAlertLE


def spin(address, backend):
    """
    Connect to the given address and begin spinning for data.

    This method creates a device with the given address, setting
    up a connection to it. If all goes well, we then call the
    device's spin method to continuously get events.

    This function only returns in the case of an error or
    disconnection.
    """
    print("Connecting to {}".format(address), file=sys.stderr)
    try:
        device = RadAlertLE(address, backend.radalert_le_callback)
    except BTLEDisconnectError:
        return
    device.spin() # Infinite loop

def scan(seconds):
    """
    Scan for a Monitor200 geiger counter.

    Starts a BLE scan for devices with "Mon200" in their name. A list
    of all matching device addresses is returned. This list may be
    empty if none were found.
    """
    results = []
    entries = Scanner().scan(seconds)
    for entry in entries:
        name = entry.getValueText(9) # "Complete Local Name"
        if name is not None and "Mon200" in name:
            results.append(entry.addr)
    return results

def find_any():
    """
    Try to connect to any Monitor200 geiger counter.

    Repeatedly scans for the presence of any device and returns its
    address once found. This loop does not exit until a device is
    found.
    """
    print("Scanning for Mon200 devices...", file=sys.stderr)
    addrs = []
    while len(addrs) == 0:
        addrs = scan(3)
    return addrs[0]

def main():
    """
    Start the logging example.

    Set up the console logger and then find a device to gather
    data from. If anything goes wrong, try to re-estable a
    connection to let the log continue.

    An address may be explicitly provided on the command-line, or
    if none is given the program will scan for devices.
    """
    backend = LogBackend()

    console_log = ConsoleLogger(backend)
    console_thread = Thread(target = console_log.spin, daemon=True)
    console_thread.start()

    # Keep attempting to reconnect if anything goes wrong
    while True:
        if len(sys.argv) == 1:
            address = find_any()
        else:
            address = sys.argv[1]
        spin(address, backend)

if __name__=="__main__":
    main()
