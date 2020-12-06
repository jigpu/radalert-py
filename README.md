Python script to log data from a bluetooth-enabled Radiation Alert
device from SE International.

Tested with the Monitor200

~~~
$ ./main.py
Scanning for Mon200 devices...
time	battery	cpm/(mR/h)	60s-count	5.0m-avg-cpm	12.0h-avg-cpm	90.0d-avg-cpm	5.0m-max-cpm	5.0m-min-cpm
Connecting to xx:xx:xx:xx:xx:xx
2020-12-06 12:36:59.143979	75.0%	None	0	0.00	0.00	0.00	0.00	0.00
2020-12-06 12:37:02.144238	75.0%	None	0	0.00	0.00	0.00	0.00	0.00
2020-12-06 12:37:05.144475	75.0%	1070	1	6.67	0.00	0.00	8.57	0.00
2020-12-06 12:37:08.144719	75.0%	1070	1	5.00	0.00	0.00	8.57	0.00
2020-12-06 12:37:11.145004	75.0%	1070	2	8.00	0.00	0.00	9.23	0.00
2020-12-06 12:37:14.145243	75.0%	1070	2	6.67	0.00	0.00	9.23	0.00
2020-12-06 12:37:17.145484	75.0%	1070	3	8.57	0.00	0.00	9.23	0.00
~~~
