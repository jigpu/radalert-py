# Radiation Alert Python API

Python API to communicate with Radiation Alert geiger counters from S.E.
International.

At the moment this library only supports communication over Bluetooth
LE and has only been tested with a Monitor 200 device.


## Introduction

The current range of Radiation Alert geiger counters sold by S.E.
International include both USB and Bluetooth LE interfaces. These
interfaces were designed for use with properitary software which is
only available for Windows (USB) and Android (BLE). This limitation
is what triggered the development of this project.

At the moment only the Bluetooth LE connection has had any reverse
engineering work done, and only for a single device (the Monitor 200).
It is expected, however, that its sibling devices should also be
compatible:

 * Radiation Alert Ranger
 * Radiation Alert Ranger EXP
 * Radiation Alert Monitor 200
 * Radiation Alert Monitor 1000EC

The Bluetooth library used (bluepy) is compatible with Linux only,
but there is no reason it could not be swapped out for something
which is cross-platform.


## Examples

An example logging program is included which is capable of writing
the current device status to the console. It can also be edited to
submit data to the GMC.MAP and Radmon services with little effort.

To use the example, you can either run it without any command-line
arguments to scan for devices (though this may require root) or
add the MAC address of a specific sensor as an argument.

Once the program is running, enable Bluetooth on the geiger counter
and it should be detected by the program in a matter of seconds.
Afterwards, it will begin sampling data (for 30s at a time) and
then printing the result to the console.

~~~
$ PYTHONPATH=. ./examples/log/example.py
Scanning for Mon200 devices...
time	battery	cpm/(mR/h)	60s-count	5.0m-avg-cpm	12.0h-avg-cpm	90.0d-avg-cpm	5.0m-max-cpm	5.0m-min-cpm
Connecting to xx:xx:xx:xx:xx:xx
2020-12-08 19:57:22	75.0%	1070	16	14.60	14.42	9.09	17.80	14.00
2020-12-08 19:57:52	75.0%	1070	21	14.80	14.43	9.09	17.80	14.00
2020-12-08 19:58:22	75.0%	1070	16	14.60	14.43	9.09	17.80	14.00
2020-12-08 19:58:52	75.0%	1070	13	14.20	14.42	9.09	17.80	14.00
2020-12-08 19:59:22	75.0%	1070	11	13.60	14.42	9.09	17.40	13.60
2020-12-08 19:59:52	75.0%	1070	10	13.80	14.42	9.09	15.80	13.20
2020-12-08 20:00:22	75.0%	1070	17	14.60	14.42	9.09	15.80	13.20
~~~


## Open Items

The following is a list of things that could be worked on in the
future:

* Bluetooth LE Protocol
  * Figure out the few remaining unknown fields
  * Determine if the other devices have any more "modes"
  * Figure out if there is any way to control the device over BLE
  * Figure out if there is any way to program the device over BLE
  * Figure out if there is any way to download logs over BLE
  * Swap the backend from bluepy to something cross-platform

* USB Protocol
  * Everything :)
