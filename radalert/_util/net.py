"""
Network protocols for uploading data.

This module impelements several network protocols for uploading dose
rate information to various public sites.
"""

import time
from typing import Dict, Optional, Tuple

from urllib.request import urlopen, Request
from urllib.parse import quote
from urllib.parse import urlencode


class Gmcmap:
    """
    Simple class to upload logging data to the GMC.MAP service.
    """
    _URL: str = "http://www.GMCmap.com/log2.asp?"

    def __init__(self, account_id: str, geiger_id: str) -> None:
        self.account_id: str = account_id
        self.geiger_id: str = geiger_id

    def send_values(self,
                    cpm: Optional[float] = None,
                    acpm: Optional[float] = None,
                    usv: Optional[float] = None) -> None:
        """
        Send the log data to the service.
        """
        params: Dict[str, str] = {
            'AID': self.account_id,
            'GID': self.geiger_id
        }
        if cpm is not None:
            params['CPM'] = f'{cpm:.2f}'
        if acpm is not None:
            params['ACPM'] = f'{acpm:.2f}'
        if usv is not None:
            params['uSV'] = f'{usv:.5f}'

        getdata = urlencode(params)
        urlopen(Gmcmap._URL + getdata).read()


class Radmon:
    """
    Simple class to upload logging data to the Radmon service.

    API Docs: https://radmon.org/index.php/forum/howtos-and-faqs\
    /864-radmon-org-api
    """

    _URL: str = "http://radmon.org/radmon.php?"

    def __init__(self, account_id: str, geiger_id: str) -> None:
        self.account_id: str = account_id
        self.geiger_id: str = geiger_id

    def send_values(self,
                    cpm,
                    unixtime: float = None,
                    latlon: Tuple[float, float] = None):
        """
        Send the log data to the service.
        """
        params: Dict[str, str] = {
            'function': 'submit',
            'user': self.account_id,
            'password': self.geiger_id,
            'value': f'{cpm:.2f}',
            'unit': 'CPM',
        }
        if unixtime is not None:
            params['datetime'] = f'{int(time.time())}'
        if latlon is not None:
            params['function'] = 'submitwithlatlng'
            params['latitude'] = f'{latlon[0]}'
            params['longitude'] = f'{latlon[1]}'

        getdata = urlencode(params)
        urlopen(Radmon._URL + getdata).read()


class URadMonitor:
    """
    Simple class to upload logging data to the uRadMonitor service.

    API documentation: https://www.hackster.io/radhoo/simple-iot-14efa1

    API headers:
      * https://github.com/radhoo/uradmonitor_kit1/blob/master/code/\
        misc/expProtocol.h
      * https://github.com/radhoo/uradmonitor_kit1/blob/master/code/\
        geiger/detectors.h
    """

    _URL: str = "http://data.uradmonitor.com/api/v1/upload/exp/"

    # yapf: disable
    _TUBE: Dict[str, int] = {
        'unknown': 0, 'SBM-20':   1, 'SI-29BG': 2, 'SBM-19': 3,
        'LND-712': 4, 'SBM-20M':  5, 'SI-22G':  6, 'STS-5':  7,
        'SI-3BG':  8, 'SBM-21':   9, 'SBT-9':  10, 'SI-1G': 11,
        'SI-8B':  12, 'SBT-10A': 13,
    }

    _PARAM: Dict[str, int] = {
        'time': 1, 'cpm': 11, 'hwver': 14, 'fwver': 15, 'tube': 16,
    }
    # yapf: enable

    def __init__(self,
                 user_id: str,
                 user_hash: str,
                 device_id: str,
                 hwver: Optional[str] = None,
                 fwver: Optional[str] = None,
                 tube: Optional[str] = None):
        self.user_id: str = user_id
        self.user_hash: str = user_hash
        self.device_id: str = device_id
        self.hwver: Optional[str] = hwver
        self.fwver: Optional[str] = fwver
        if tube is None:
            self.tube = URadMonitor._TUBE["unknown"]
        else:
            self.tube = URadMonitor._TUBE.get(tube,
                                              URadMonitor._TUBE["unknown"])

    def send_values(self, cpm: float, unixtime: Optional[float] = None):
        if unixtime is None:
            unixtime = time.time()

        # yapf: disable
        headers: Dict[str, str] = {
            'X-User-id':   self.user_id,
            'X-User-hash': self.user_hash,
            'X-Device-id': self.device_id,
        }

        params: Dict[int, str] = {
            URadMonitor._PARAM['time']:  f'{int(unixtime)}',
            URadMonitor._PARAM['cpm']:   f'{cpm:.2f}',
            URadMonitor._PARAM['tube']:  f'{self.tube}',
        }
        # yapf: enable

        if self.hwver is not None:
            params[URadMonitor._PARAM['hwver']] = self.hwver
        if self.fwver is not None:
            params[URadMonitor._PARAM['fwver']] = self.fwver

        restful_path = URadMonitor._restful_encode(params)
        urlopen(Request(Radmon._URL + restful_path, headers=headers)).read()

    @staticmethod
    def _restful_encode(params: Dict[int, str]) -> str:
        path = ""
        for k, v in params.items():
            path += "/"
            path += quote(f'{k}')
            path += "/"
            path += quote(v)
        return path
