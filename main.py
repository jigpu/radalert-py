#!/usr/bin/env python3

import sys
from threading import Thread

from bluepy.btle import Scanner

from radalertle import RadAlertLE
from radalertlog import RadAlertConsoleLogger


def spin(address, logger):
    print("Connecting to {}".format(address), file=sys.stderr)
    device = RadAlertLE(address, logger.radalert_le_callback)
    device.spin() # Infinite loop

def scan(seconds):
    results = []
    entries = Scanner().scan(seconds)
    for entry in entries:
        name = entry.getValueText(9) # "Complete Local Name"
        if name is not None and "Mon200" in name:
            results.append(entry.addr)
    return results

def connect_any():
    print("Scanning for Mon200 devices...", file=sys.stderr)
    addrs = []
    while len(addrs) == 0:
        addrs = scan(3)
    return addrs[0]

def main():
    logger = RadAlertConsoleLogger()
    log_thread = Thread(target = logger.spin, daemon=True)
    log_thread.start()

    if len(sys.argv) == 1:
        address = connect_any()
    else:
        address = sys.argv[1]
    spin(address) # Infinite loop

if __name__=="__main__":        
    main()
