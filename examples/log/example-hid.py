#!/usr/bin/env python3
"""
Example of a simple logging program which uses the radalert API.

This program connects to the first Radiation Alert Monitor200 device
that it can find over USB. Once connected, it will begin gathering
events and performing statistics. Logs data will be printed out
periodically as tab-separated values. If the connection is interrupted
the program will remain running and try to connect again.

This module focuses on getting the connection set up (and resumed
if it fails). The heavy-lifting of the logging / statistics is
handled inside the logger module that lives alongside this example.

User applications do not typically have permissions to directly
access USB devices. Successful use of this program may require either
running as root or changing the permissions of the USB / hidraw
device nodes. See the README.md for more information.
"""

import sys
import time
import traceback
from threading import Thread

from logger import ConsoleLogger
from logger import LogBackend
#from logger import GmcmapLogger
#from logger import RadmonLogger

import hid

from radalert.hid import RadAlertHID


def spin(device):
    """
    Connect to the given address and begin spinning for data.

    This method creates a device with the given address, setting
    up a connection to it. If all goes well, we then call the
    device's spin method to continuously get events.

    This function only returns in the case of an error or
    disconnection.
    """
    try:
        device.spin()  # Infinite loop
    except Exception as e:
        print("While spinning:", file=sys.stderr)
        traceback.print_exc()
    device.disconnect()


def find_any():
    """
    Try to connect to any Monitor200 geiger counter.

    Repeatedly scans for the presence of any device and returns its
    address once found. This loop does not exit until a device is
    found.
    """
    print("Scanning for Mon200 devices...", file=sys.stderr)
    while True:
        for d in hid.enumerate():
            vid, pid = d["vendor_id"], d["product_id"]
            #print(f"Found {vid:04x}:{pid:04x}", file=sys.stderr)
            if vid == 0x1781 and pid == 0x08e9:
                print("Mon200 found!", file=sys.stderr)
                return (vid, pid)
        print("", file=sys.stderr)
        time.sleep(1)


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
    console_thread = Thread(target=console_log.spin, daemon=True)
    console_thread.start()

    # Set up logging to the GMC.MAP service. Be sure to fill in the IDs!
    #gmc_log = GmcmapLogger(backend, "--ID--", "--ID--")
    #gmc_thread = Thread(target = gmc_log.spin, daemon=True)
    #gmc_thread.start()

    # Set up logging to the Radmon service. Be sure to fill in the user/pass!
    #radmon_log = RadmonLogger(backend, "--USER--", "--PASSWORD--")
    #radmon_thread = Thread(target = radmon_log.spin, daemon=True)
    #radmon_thread.start()

    # Keep attempting to reconnect if anything goes wrong
    device = RadAlertHID(backend.radalert_status_callback,
                         backend.radalert_query_callback)
    while True:
        if len(sys.argv) == 1:
            vid, pid = find_any()
        else:
            vid, pid = int(sys.argv[1]), int(sys.argv[2])

        try:
            print(f"Connecting to {vid}:{pid}", file=sys.stderr)
            device.connect(vid, pid)
        except Exception as e:
            print("Failure: {}".format(e), file=sys.stderr)
            continue
        print(f"Sampling from {vid}:{pid}", file=sys.stderr)
        spin(device)
        time.sleep(3)


if __name__ == "__main__":
    main()
