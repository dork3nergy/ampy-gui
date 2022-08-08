# ampy-gui
Gtk 3.0 GUI for Adafruit's ampy CLI

This is just a GUI interface for Adafruit's commandline ampy utility that allows you to transfer files from your machine to an ESP32 or other similar device.  It's written in python and I have no idea if it usable or port-able to a windows machine.

I believe it implements all ampy commands except for the --no-output run modifier.

The default baud setting of 115200 seems to be the only baud setting the works with ampy. Not sure why that is.

Any errors are also displayed in the scrollbox.

USAGE:
python3 ./ampy-gui.py

Instructions:
- Plug in your device
- Set your port and optionally the baud rate and delay.
- Hit connect

![Alt text](screenshot.png?raw=true "Screenshot")
