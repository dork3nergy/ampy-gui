# ampy-gui
Gtk 3.0 GUI for Adafruit's ampy CLI

This is just a GUI interface for Adafruit's commandline ampy utility that allows you to transfer files from your machine to an ESP32 or other similar device.  It's written in python and I have no idea if it usable or port-able to a windows machine.

I believe it implements all ampy commands except for the --no-output run modifier.

The default baud setting of 115200 seems to be the only baud setting the works with ampy. Not sure why that is.

By default, the program will check every 2 minutes if the remote device is still connected. If not, it will automatically disconnect the device.

Any errors are also displayed in the scrollbox.

Prerequisites:
- make sure Adafruit ampy is installed: https://learn.adafruit.com/micropython-basics-load-files-and-run-code/install-ampy
- make sure Gtk is installed: https://pygobject.readthedocs.io/en/latest/getting_started.html

USAGE (run in terminal):
`python3 ampy-gui.py`

If you start the script from another directory than this root directory, ampy-gui will open the local tree view in 
the directory that you ran the command in. E.g. you're in directory `user/mydir` and run `python3 user/Downloads/ampy-gui.py`,
the tree view will open in `user/mydir`.

To also print debug messages to your local terminal, run with:
`python3 ampy-gui.py -d` or `python3 ampy-gui.py --debug`

The following other arguments are available:
- `-h` or `--help` : prints help info.
- `-d` or `--debug` : enables debug printing in the console that you ran the script in.
- `-n` or `--notimeout` : disables device connection timeout checking (if the device does not respond after a certain timeout delay, the connection is automatically broken).
- `-t <timeout delay>` or `--timedelay <time delay>` : specifies the timeout delay in seconds after which the device connection should be checked. Default delay is 120 seconds.

Example: run the program with debug information, and no timeout checking: `python3 ampy-gui.py -d -n`

Example: run the program with no debug information, and 5 minute timeout checking: `python3 ampy-gui.py -t 300`

Instructions:
- Plug in your device
- Set your port and optionally the baud rate and delay.
- Hit connect

Troubleshooting:
- I can connect to my device (including the 'Hello world' message), but don't see any files.
  - Make sure you're not connected to the serial port in any other application (e.g. another serial terminal program)
  - If you're running Linux, take a look at this page for help: https://github.com/scientifichackers/ampy/issues/9

![Alt text](screenshot.png?raw=true "Screenshot")
