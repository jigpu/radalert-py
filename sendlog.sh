#!/bin/sh

LOGFILE="${HOME}/.cache/py-radalert-le.log"

MAXIMUM_AGE_MINUTES=10

GMC_ENABLE=0
GMC_ACCOUNT_ID=
GMC_GEIGER_ID=

RADMON_ENABLE=0
RADMON_USERNAME=
RADMON_PASSWORD=

if ! test -f "${LOGFILE}"; then
	echo "Log file could not be found"
	exit 1
elif ! find "${LOGFILE}" -mmin -${MAXIMUM_AGE_MINUTES} > /dev/null; then
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

CPM=$(awk -F'\t' '{print $5}' <<< "$LOGLINE")
ACPM=$(awk -F'\t' '{print $6}' <<< "$LOGLINE")
USV=$(awk -F'\t' '{print $5/$3*10}' <<< "$LOGLINE")


ERR=0
if test "${GMC_ENABLE}" -eq 1; then
	if test -z "${GMC_ACCOUNT_ID}"; then
		echo "GMC: Account ID must be set" >&2
		ERR=1
	fi
	if test -z "${GMC_GEIGER_ID}"; then
		echo "GMC: Gieger counter ID must be set" >&2
		ERR=1
	fi
fi
if test "${RADMON_ENABLE}" -eq 1; then
	if test -z "${RADMON_USERNAME}"; then
		echo "Radmon: Username must be set" >&2
		ERR=1
	fi
	if test -z "${RADMON_PASSWORD}"; then
		echo "Radmon: Password must be set" >&2
		ERR=1
	fi
fi

if test "${ERR}" -ne 0; then
	exit ${ERR}
fi

if test "${GMC_ENABLE}" -eq 1; then
	URL="http://www.GMCmap.com/log2.asp?AID=${GMC_ACCOUNT_ID}&GID=${GMC_GEIGER_ID}&CPM=${CPM}&ACPM=${ACPM}&uSV=${USV}"
	curl -s "${URL}" > /dev/null || echo "GMC: Failed to send" >&2
fi
if test "${RADMON_ENABLE}" -eq 1; then
	URL="http://radmon.org/radmon.php?function=submit&user=${RADMON_USERNAME}&password=${RADMON_PASSWORD}&value=${CPM}&unit=CPM"
	curl -s "${URL}" > /dev/null || echo "Radmon: Failed to send" >&2
fi