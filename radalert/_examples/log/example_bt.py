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

import os
import sys
import time
from threading import Thread
from typing import List, Tuple

from radalert._examples.log.logger import ConsoleLogger
from radalert._examples.log.logger import LogBackend
from radalert._examples.log.logger import GmcmapLogger
from radalert._examples.log.logger import RadmonLogger

from bluepy.btle import Scanner
from bluepy.btle import BTLEDisconnectError
from bluepy.btle import BTLEException

from radalert.ble import RadAlertLE


def scan(seconds: int) -> List[str]:
    """
    Scan for a Monitor200 geiger counter.

    Starts a BLE scan for devices with "Mon200" in their name. A list
    of all matching device addresses is returned. This list may be
    empty if none were found.
    """
    results = []
    entries = Scanner().scan(seconds)
    for entry in entries:
        name = entry.getValueText(9)  # "Complete Local Name"
        if name is not None and "Mon200" in name:
            results.append(entry.addr)
    return results


def find_any() -> str:
    """
    Try to connect to any Monitor200 geiger counter.

    Repeatedly scans for the presence of any device and returns its
    address once found. This loop does not exit until a device is
    found.
    """
    print("Scanning for Mon200 devices...", file=sys.stderr)
    addrs: List[str] = []
    while len(addrs) == 0:
        addrs = scan(3)
    return addrs[0]


def main() -> None:
    """
    Start the logging example.

    Set up the console logger and then find a device to gather
    data from. If anything goes wrong, try to re-estable a
    connection to let the log continue.

    An address may be explicitly provided on the command-line, or
    if none is given the program will scan for devices.
    """
    backend = LogBackend()

    console_interval = int(os.environ.get("CONSOLE_INTERVAL", 30))
    console_log = ConsoleLogger(backend, console_interval)
    console_thread = Thread(target=console_log.spin, daemon=True)
    console_thread.start()

    # Set up logging to the GMC.MAP service if env vars are set
    gmcmap_acct_id = os.environ.get("GMCMAP_ACCT_ID", None)
    gmcmap_gc_id = os.environ.get("GMCMAP_GC_ID", None)
    gmcmap_interval = int(os.environ.get("GMCMAP_INTERVAL", 180))
    if gmcmap_acct_id is not None and gmcmap_gc_id is not None:
        gmc_log = GmcmapLogger(backend, gmcmap_acct_id, gmcmap_gc_id,
                               gmcmap_interval)
        gmc_thread = Thread(target=gmc_log.spin, daemon=True)
        gmc_thread.start()

    # Set up logging to the Radmon service if env vars are set
    radmon_user_id = os.environ.get("RADMON_USER_ID", None)
    radmon_data_pw = os.environ.get("RADMON_DATA_PW", None)
    radmon_interval = int(os.environ.get("RADMON_INTERVAL", 180))
    if radmon_user_id is not None and radmon_data_pw is not None:
        radmon_log = RadmonLogger(backend, radmon_user_id, radmon_data_pw,
                                  radmon_interval)
        radmon_thread = Thread(target=radmon_log.spin, daemon=True)
        radmon_thread.start()

    # Keep attempting to reconnect if anything goes wrong
    device = RadAlertLE(backend.radalert_status_callback,
                        backend.radalert_query_callback)
    while True:
        if len(sys.argv) == 1:
            address = find_any()
        else:
            address = sys.argv[1]

        try:
            print("Connecting to {}".format(address), file=sys.stderr)
            device.connect(address)
            device.spin()
        except (BTLEDisconnectError, BTLEException, BrokenPipeError) as e:
            print(e, file=sys.stderr)
        finally:
            device.disconnect()
            time.sleep(3)


if __name__ == "__main__":
    main()
