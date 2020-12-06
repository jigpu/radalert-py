#!/usr/bin/env python3

import sys

from bluepy.btle import Scanner

from radalertle import RadAlertLE
from radalertlog import RadAlertConsoleLogger


def spin(address):
    print("Connecting to {}".format(address))
    logger = RadAlertConsoleLogger()
    device = RadAlertLE(address, logger.radalert_le_callback)
    logger.start()
    device.spin() # Infinite loop

def scan():
    print("Scanning for Mon200 devices...")
    results = []
    entries = Scanner().scan(1.0)
    for entry in entries:
        name = entry.getValueText(9) # "Complete Local Name"
        if name is not None and "Mon200" in name:
            results.append(entry.addr)
    return results

def connect_any():
    addrs = []
    while len(addrs) == 0:
        addrs = list(set(addrs) | set(scan()))
    return addrs[0]

def main():
    if len(sys.argv) == 1:
        address = connect_any()
    else:
        address = sys.argv[1]
    spin(address) # Infinite loop

if __name__=="__main__":        
    main()
