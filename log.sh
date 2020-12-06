#!/bin/sh

# Spins up the program for logging to a file. The log can be analyzed
# locally or used by something like sendlog.sh to upload data to a
# monitoring service.
#
# You will probably want to pass the MAC address of the geiger counter
# as an argument. Otherwise, the Python script will need root rights
# to enable LE scanning...

LOGFILE="${HOME}/.cache/py-radalert-le.log"

python3 -u ./main.py $@ | tee "$LOGFILE"