#!/bin/sh

# Spins up the program for logging to a file. This file can also be
# used to send data to the GMC.MAP service with the help of the
# sendlog.sh script
#
# You will probably want to pass the MAC address of the geiger counter
# as an argument so that this doesn't have to run as root...

LOGFILE="${HOME}/tmp/radalert.log"

python3 -u ./main.py $@ | tee "$LOGFILE"