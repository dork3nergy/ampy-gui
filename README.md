# ampy-gui
Gtk 3.0 GUI for Adafruit's ampy CLI

This is just a GUI interface for Adafruit's commandline ampy utility that allows you to transfer files from your machine to an ESP32 or other similar device.  It's written in python and I have no idea if it usable or port-able to a windows machine.

I believe it implements all ampy commands except for the --no-output run modifier.

The default baud setting of 115200 seems to be the only baud setting the works with ampy. Not sure why that is.

Any errors are also displayed in the scrollbox.

Prerequisites:
- make sure Adafruit ampy is installed: https://learn.adafruit.com/micropython-basics-load-files-and-run-code/install-ampy
- make sure Gtk is installed: https://pygobject.readthedocs.io/en/latest/getting_started.html

USAGE:
python3 ampy-gui.py

To also print debug messages to your local terminal, run with:
python3 ampy-gui.py debug

Instructions:
- Plug in your device
- Set your port and optionally the baud rate and delay.
- Hit connect

Troubleshooting:
- I can connect to my device (including the 'Hello world' message), but don't see any files.
  - Make sure you're not connected to the serial port in any other application (e.g. another serial terminal program)
  - If you're running Linux, take a look at this page for help: https://github.com/scientifichackers/ampy/issues/9

![Alt text](screenshot.png?raw=true "Screenshot")
