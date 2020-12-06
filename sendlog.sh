#!/bin/sh

LOGFILE="${HOME}/tmp/radalert.log"
ACCOUNT_ID=
GEIGER_ID=

if test -z "${ACCOUNT_ID}"; then
	echo "Account ID must be set"
	exit 1
elif test -z "${GEIGER_ID}"; then
	echo "Gieger counter ID must be set"
	exit 1
fi

if ! test -f "${LOGFILE}"; then
	echo "Log file could not be found"
	exit 1
elif ! find "${LOGFILE}" -mmin -3 > /dev/null; then
	echo "Log file is stale"
	exit 1
fi

LOGLINE=$(tail -n1 "$LOGFILE")
if grep "time" <<< "$LOGLINE"; then
	echo "Log line does not contain data"
	exit 1
elif grep "None" <<< "$LOGLINE"; then
	echo "Log line is missing data"
	exit 1
fi



CPM=$(awk -F'\t' '{print $4}' <<< "$LOGLINE")
ACPM=$(awk -F'\t' '{print $5}' <<< "$LOGLINE")
USV=$(awk -F'\t' '{print $4/$3*10}' <<< "$LOGLINE")

curl -s "http://www.GMCmap.com/log2.asp?AID=${ACCOUNT_ID}&GID=${GEIGER_ID}&CPM=${CPM}&ACPM=${ACPM}&uSV=${USV}" > /dev/null