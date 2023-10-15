This is an example of how to use radalert-py with systemd to automatically
record data to the system log and services like gmcmap.com and Radmon.org.

1. Install radalert-py, following the top-level README instructions for
   a root installation.

2. Ensure `/usr/bin/radalert-usb` is installed and functions.

3. Copy the contents of the `etc` directory to `/etc`

4. Run `sudo systemd daemon-reload`

5. Configure the `/etc/default/radalert` file with your preferences

6. Run `sudo systemctl start radalert` to start the service.

7. Run `sudo journalctl -u radalert` to verify that the service is creating
   log output.

8. Optionally: run `sudo systemctl enable radalert` to ensure the service
   is automatically started whenever the system restarts.

The systemd unit is configured to run the `radalert-usb` example by default.
If you want to run a different example, you should edit the 
`/etc/systemd/system/radalert.service` file and change which example is run.
