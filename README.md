Python script to log data from a bluetooth-enabled Radiation Alert
device from SE International.

Tested with the Monitor200

~~~
$ sudo ./run.sh
Scanning for Mon200 devices...
Scanning for Mon200 devices...
Scanning for Mon200 devices...
Scanning for Mon200 devices...
Connecting to xx:xx:x:xx:xx:xx
time	cpm/(mR/h)	5.0m-avg-cpm	12.0h-avg-cpm	90.0d-avg-cpm	5.0m-max-cpm	5.0m-min-cpm
2020-12-06 09:32:51.297671	1070	11.07	31.99	32.00	32.00	4.57
2020-12-06 09:33:21.298233	1070	10.53	31.97	32.00	32.00	4.57
2020-12-06 09:33:51.298656	1070	11.02	31.96	32.00	32.00	4.57
~~~
