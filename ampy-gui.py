#!/usr/bin/python3

import sys, os, getopt
import configparser
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, GdkPixbuf
from gi.repository import Gdk, GLib
from ampy.pyboard import PyboardError
import subprocess
import serial.tools.list_ports
from enum import Enum
from threading import Thread, Event
import glob

# TODO: wildcard .* & configurable over commmand line
ignore_files = [".DS_Store", ".git", ".idea"]	# ignore these files when listing files in a directory

class MsgType(Enum):
	""" Different message type options for the terminal window, and the corresponding color of the terminal text.
	"""
	INFO = "#45ffc1"
	WARNING = "#eb9f4d"
	ERROR = "#f5805f"

class AppWindow(Gtk.ApplicationWindow):
	debug = False

	use_timeout = True		# Whether to disconnect the device if after the timeout delay the device could net be connected to
	timeout_delay = 120  	# After how many seconds the connection should be checked again

	connected = False

	local_treeview = None
	remote_treeview = None

	remote_dirs = []
	remote_files = []

	run_local_button = None

	remote_refresh_button = None
	
	put_button = None
	get_button = None
	run_remote_button = None
	delete_button = None
	mkdir_button = None
	reset_button = None

	terminal_buffer = None

	def __init__(self, debug=False, use_timeout=True, timeout_delay=120, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.debug = debug
		self.use_timeout = use_timeout
		self.timeout_delay = timeout_delay

		self.set_border_width(10)
		self.set_size_request(900, 700)
		
		#Numbers are Column Numbers in Model
		self.ICON = 0
		self.FILENAME = 1
		self.TYPE = 2

		
		self.current_local_path = os.getcwd()

		self.progpath = os.path.join(os.getcwd(), os.path.dirname(__file__))
	
		self.current_remote_path = ''

		css = b"""
			textview text {
				background-color: black;
				color:#45ffc1;
			 }
			textview.view {
				padding-left:4px;
				background-color:black;
				font: 14px "";
			}
			frame {
				background-color:#b2b2b2;
				padding:12px;
			}
			#small_button_padding {
				padding-left:0px;
				padding-right:0px;
			}
			"""

		
		provider = Gtk.CssProvider()
		screen = Gdk.Screen.get_default()
		provider.load_from_data(css)
		style_context = Gtk.StyleContext()
		style_context.add_provider_for_screen(
			screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
		)

		# Load settings from a configuration file
		config = configparser.ConfigParser()
		config.read(os.path.join(self.progpath, 'config.ini'))
		try:
			self.ampy_args = [config['DEFAULT']['port'], config['DEFAULT']['baud'], config['DEFAULT']['delay']]
		except KeyError:
			print("Could not load configurations, falling back to defaults.")
			self.ampy_args = ['/dev/ttyUSB0', '115200', '0']
		self.update_ampy_command()
		
		self.baud_rates=["300", "600", "1200", "2400", "4800", "9600", "14400", "19200", "28800", "38400", "57600","115200",
			"230400", "460800", "500000", "576000", "921600"]

		box_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
		box_outer.set_homogeneous(False)
		self.add(box_outer)

		#SETTINGS PANEL SETUP
		port_label = Gtk.Label.new("Port")
		delay_label = Gtk.Label.new("Delay")
		baud_label= Gtk.Label.new("Baud Rate")
		
		port_entry = Gtk.Entry()
		baud_button= Gtk.ComboBoxText.new()
		delay_spin = Gtk.SpinButton.new_with_range(0, 10, 0.1)
		
		#LOAD BAUD RATES INTO COMBO BOX
		for baud_rate in self.baud_rates:
			baud_button.append_text(baud_rate)
	
		baud_button.set_active(11)
		delay_spin.set_digits(1)
		port_entry.set_text(self.ampy_args[0])

		#SET EVENT TRIGGERS for SETTINGS
		port_entry.connect("focus-out-event",self.on_port_change)
		baud_button.connect("changed",self.on_baud_change)
		delay_spin.connect("changed",self.on_delay_change)


		#Pack each setting into a box
		port_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
		baud_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
		delay_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

		select_port_button = Gtk.Button.new_with_label("Select Port")
		connect_button = Gtk.Button.new_with_label("Connect")

		port_box.pack_start(port_label,False,False,0)
		port_box.pack_start(port_entry,False,False,0)
		port_box.pack_start(select_port_button,False,False,4)
		baud_box.pack_start(baud_label,False,False,0)
		baud_box.pack_start(baud_button,False,False,0)
		delay_box.pack_start(delay_label,False,False,0)
		delay_box.pack_start(delay_spin,False,False,0)
		
		#Pack settings boxes into on big box
		settingsbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
		settingsbox.pack_start(port_box,True,True,0)
		settingsbox.pack_start(baud_box,True,True,0)
		settingsbox.pack_start(delay_box,True,True,0)
		settingsbox.pack_start(connect_button,True,True,0)

		settings_frame = Gtk.Frame()
		settings_frame.add(settingsbox)
		settings_frame.set_shadow_type(0)
		#pack settings box into outer box

		box_outer.pack_start(settings_frame, False, False, 0)
		
		#FILE BROWSER BOX
		filebrowser_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,valign="fill", halign="fill")
		box_outer.pack_start(filebrowser_box,True, True,12)

		# CREATE LOCAL TREEVIEW
		self.local_treeview = Gtk.TreeView.new()
		self.local_treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
		
		self.setup_local_tree_view(self.local_treeview)
		self.setup_local_tree_model(self.local_treeview)
		self.local_treeview.connect("row-activated", self.on_local_row_activated)
		self.local_treeview.get_selection().connect("changed", self.on_local_row_selected)

		# CREATE REMOTE TREEVIEW
		self.remote_treeview = Gtk.TreeView.new()
		self.remote_treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

		self.setup_remote_tree_view(self.remote_treeview)
		self.setup_remote_tree_model(self.remote_treeview)
		self.remote_treeview.connect("row-activated", self.on_remote_row_activated)
		self.remote_treeview.get_selection().connect("changed", self.on_remote_row_selected)

		#CREATE SCROLLED WINDOWS
		local_scrolled_win = Gtk.ScrolledWindow(valign="fill", halign="fill")
		local_scrolled_win.set_policy(Gtk.PolicyType.AUTOMATIC, 
								Gtk.PolicyType.AUTOMATIC)
		remote_scrolled_win = Gtk.ScrolledWindow()
		remote_scrolled_win.set_policy(Gtk.PolicyType.AUTOMATIC, 
								Gtk.PolicyType.AUTOMATIC)
		
		#ADD TREEVIEWS TO SCROLLED WINDOWS
		local_scrolled_win.add(self.local_treeview)
		local_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,halign="fill")
		local_box.pack_start(local_scrolled_win,True,True,0)

		local_button_box = Gtk.HBox()

		## Local directory chooser button
		local_dir_chooser_button = Gtk.Button.new_with_label("Select Directory")
		local_dir_chooser_button.set_name("small_button_padding")
		local_dir_chooser_button.set_tooltip_text("Select the root directory of the local machine")
		local_dir_chooser_button.set_margin_end(4)
		local_dir_chooser_button.connect("clicked", self.on_local_dir_chooser_button_clicked, self.local_treeview)

		## Local refresh button
		local_refresh_button = Gtk.Button.new_with_label("Refresh")
		local_refresh_button.set_name("small_button_padding")
		local_refresh_button.set_tooltip_text("Refresh the file list of the local device.")
		local_refresh_button.set_margin_start(4)
		local_refresh_button.connect("clicked", self.on_refresh_local_button_clicked, self.local_treeview)

		local_button_box.pack_start(local_dir_chooser_button, True, True, 0)
		local_button_box.pack_start(local_refresh_button, True, True, 0)
		local_box.pack_start(local_button_box, False, False, 0)

		remote_scrolled_win.add(self.remote_treeview)

		remote_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,halign="fill")
		remote_box.pack_start(remote_scrolled_win,True,True,0)
		self.remote_refresh_button = Gtk.Button.new_with_label("Refresh")
		self.remote_refresh_button.set_sensitive(False)
		self.remote_refresh_button.set_tooltip_text("Refresh the file list of the remote device.")
		self.remote_refresh_button.connect("clicked", self.on_refresh_remote_button_clicked, self.remote_treeview)
		remote_box.pack_start(self.remote_refresh_button,False,False,0)

		#DEFINE LOCAL FUNCTION BOXES
		local_buttons_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign="center")
		local_services = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign="fill")

		self.run_local_button = Gtk.Button.new_with_label("RUN")
		self.run_local_button.set_sensitive(False)
		self.run_local_button.set_tooltip_text("Run the selected local file on the remote device.")

		local_buttons_box.pack_start(self.run_local_button, False, False, 0)

		# PACK IT UP
		# Create Frame for Remote Services
		local_services_frame = Gtk.Frame()
		local_services_frame.add(local_services)
		local_services_frame.set_shadow_type(0)

		#DEFINE TRANSFER BUTTONS
		putget_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,valign="center")
		self.get_button = Gtk.Button.new_with_label("<< GET <<")
		self.put_button = Gtk.Button.new_with_label(">> PUT >>")
		self.get_button.set_sensitive(False)
		self.put_button.set_sensitive(False)
		self.get_button.set_tooltip_text("Download the selected remote file to the local device.")
		self.put_button.set_tooltip_text("Upload the selected local file to the remote device.")

		putget_box.pack_start(self.get_button,False,False,0)
		putget_box.pack_start(self.put_button,False,False,0)

		#DEFINE REMOTE FUNCTION BOXES
		remote_buttons_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,valign="center")
		remote_services = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,halign="fill")

		self.mkdir_button = Gtk.Button.new_with_label("MKDIR")
		self.run_remote_button = Gtk.Button.new_with_label("RUN")
		self.reset_button = Gtk.Button.new_with_label("RESET")
		self.delete_button = Gtk.Button.new_with_label("DELETE")

		self.mkdir_button.set_sensitive(False)
		self.run_remote_button.set_sensitive(False)
		self.reset_button.set_sensitive(False)
		self.delete_button.set_sensitive(False)

		self.mkdir_button.set_tooltip_text("Create a new directory on the remote device.")
		self.run_remote_button.set_tooltip_text("Run the selected remote file on the remote device.")
		self.reset_button.set_tooltip_text("Perform a soft reset/reboot of the remote device.")
		self.delete_button.set_tooltip_text("Delete the selected files/directories from the remote device.")

		remote_buttons_box.pack_start(self.mkdir_button,False,False,0)
		remote_buttons_box.pack_start(self.delete_button,False,False,0)
		remote_buttons_box.pack_start(self.reset_button,False,False,0)
		remote_buttons_box.pack_start(self.run_remote_button,False,False,0)

		#PACK IT UP
		#Create Frame for Remote Services
		remote_services_frame = Gtk.Frame()
		remote_services_frame.add(remote_services)
		remote_services_frame.set_shadow_type(0)

		local_services.pack_start(local_box, True, True, 2)
		local_services.pack_start(local_buttons_box, False, False, 0)
		filebrowser_box.pack_start(local_services_frame, True, True, 6)
		filebrowser_box.pack_start(putget_box,False,False,4)
		remote_services.pack_start(remote_box,True,True,2)
		remote_services.pack_start(remote_buttons_box,False,False,0)
		filebrowser_box.pack_start(remote_services_frame,True,True,6)


		#CREATE TERMINAL WINDOW
		terminal_window = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,halign="fill")
		terminal_window.set_homogeneous(False)
		box_outer.pack_start(terminal_window,True, True,6)
		
		self.terminal_view = Gtk.TextView()
		self.terminal_buffer = self.terminal_view.get_buffer()

		#MAKE TERMINAL READ ONLY
		self.terminal_view.set_property('editable',False)
		self.terminal_view.set_property('cursor-visible',False)

		terminal_scroll = Gtk.ScrolledWindow()
		terminal_scroll.add(self.terminal_view)
		terminal_window.pack_start(terminal_scroll,True,True,6)

		# TIE ACTIONS TO BUTTONS
		select_port_button.connect("clicked", self.select_port_popup, port_entry)
		connect_button.connect("clicked", self.connect_device, self.remote_treeview, self.terminal_view, self.terminal_buffer)
		self.put_button.connect("clicked", self.put_button_clicked, self.local_treeview, self.remote_treeview, self.terminal_buffer)
		self.get_button.connect("clicked", self.get_button_clicked, self.local_treeview, self.remote_treeview, self.terminal_buffer)
		self.run_local_button.connect("clicked", self.run_local_button_clicked, self.local_treeview, self.terminal_buffer)
		self.run_remote_button.connect("clicked", self.run_remote_button_clicked, self.remote_treeview, self.terminal_buffer)
		self.mkdir_button.connect("clicked", self.mkdir_button_clicked, self.remote_treeview, self.terminal_buffer)
		self.reset_button.connect("clicked", self.reset_button_clicked, self.remote_treeview, self.terminal_buffer)
		self.delete_button.connect("clicked", self.delete_button_clicked, self.remote_treeview, self.terminal_buffer)

		# Clear terminal button
		hbox = Gtk.HBox()
		clear_terminal_button = Gtk.Button.new_with_label("Clear terminal")
		hbox.pack_start(clear_terminal_button, False, False, 0)
		box_outer.pack_start(hbox, False, False, 0)
		clear_terminal_button.connect("clicked", self.clear_terminal, self.terminal_buffer)

		# Recheck the connection of the device after a certain delay time
		if self.use_timeout:
			GLib.timeout_add(self.timeout_delay * 1000, self.recheck_connection)

		#SET FOCUS TO LOCAL FILELIST
		self.local_treeview.grab_focus()
		
	def force_refresh(self):
		while Gtk.events_pending():     #   this forces GTK to refresh the screen
			Gtk.main_iteration() 


	def select_port_popup(self, button, port_entry):
		dialog = SelectPortPopUp(self)
		response = dialog.run()

		if response == Gtk.ResponseType.OK:
			port = dialog.get_result()
			dialog.destroy()
			port_entry.set_text(port)
			self.on_port_change(port_entry, None)
		else:
			dialog.destroy()

	def connect_device(self, button, remote_treeview, terminal_view, terminal_buffer):
		self.debug_print("Connecting to device...")
		response = self.check_for_device()
		if response == 0:
			self.debug_print("Connected")
			self.populate_remote_tree_model(remote_treeview)
			self.print_and_terminal(terminal_buffer,
									"Connected to device {}\nHello world!! :)".format(self.ampy_args[0]),
									MsgType.INFO)
			model, paths = self.local_treeview.get_selection().get_selected_rows()
			if len(paths) > 0:
				self.put_button.set_sensitive(True)

	def update_ampy_command(self):
		self.ampy_command = ['ampy', '--port', self.ampy_args[0], '--baud',self.ampy_args[1], '--delay',self.ampy_args[2]]

	def recheck_connection(self):
		""" Checks if the connected device is still available
		"""
		self.debug_print("Rechecking connection...")
		if self.connected:
			self.check_for_device()
		else:
			self.debug_print("No active device")
		return True		# Necessary for the GLib timeout to keep running

	def check_for_device(self):
		try:
			port = serial.Serial(port=self.ampy_args[0])
			if port.isOpen():
				self.enable_remote_buttons(True)
				self.connected = True
				return 0
		except serial.SerialException as ex:
			if self.connected:
				self.print_and_terminal(self.terminal_buffer, "Device disconnected", MsgType.WARNING)
			self.connected = False
			msg = "Can't find your remote device '{}'".format(self.ampy_args[0])
			msg_sec = "Check the port settings or whether the port is in use in another program."
			dialog = Gtk.MessageDialog(
				transient_for=self,
				flags=0,
				message_type=Gtk.MessageType.INFO,
				buttons=Gtk.ButtonsType.OK,
				text=msg,
			)
			dialog.format_secondary_text(msg_sec)
			dialog.set_decorated(False)
			dialog.run()
			dialog.destroy()
			self.clear_remote_tree_view(self.remote_treeview)
			self.enable_remote_buttons(False)
			self.put_button.set_sensitive(False)
			return -1
		
	def on_port_change(self,port,event):
		self.ampy_args[0]=port.get_text()
		if self.check_for_device() != -1:
			self.update_ampy_command()
			self.debug_print("Port Changed")
	def on_baud_change(self,baud):
		selected = baud.get_active()
		self.ampy_args[1]= self.baud_rates[selected]
		self.update_ampy_command()
		self.debug_print("Baud Changed")
	def on_delay_change(self,delay):
		value = delay.get_value()
		self.ampy_args[2]=str(value)
		self.update_ampy_command()
		self.debug_print("Delay Changed")

	def setup_local_tree_view(self, local_treeview):
		column = Gtk.TreeViewColumn.new()
		column.set_title("Local File Browser")
  
		renderer = Gtk.CellRendererPixbuf.new()
		column.pack_start(renderer, False)
		column.add_attribute(renderer, "pixbuf", self.ICON)
  
		renderer = Gtk.CellRendererText.new()
		column.pack_start(renderer, True)
		column.add_attribute(renderer, "text", self.FILENAME)
  
		local_treeview.append_column(column)

	def setup_remote_tree_view(self, remote_treeview):
		column = Gtk.TreeViewColumn.new()
		column.set_title("Remote File Browser")

		renderer = Gtk.CellRendererPixbuf.new()
		column.pack_start(renderer, False)
		column.add_attribute(renderer, "pixbuf", self.ICON)
  
		renderer = Gtk.CellRendererText.new()
		column.pack_start(renderer, True)
		column.add_attribute(renderer, "text", self.FILENAME)

		renderer = Gtk.CellRendererText.new()
		column.pack_start(renderer, True)
		column.add_attribute(renderer, "text", self.TYPE)
		renderer.set_visible(False)
  
		remote_treeview.append_column(column)

	def clear_remote_tree_view(self, remote_treeview):
		remote_treeview.get_model().clear()

	def setup_local_tree_model(self, local_treeview):
		local_store = Gtk.ListStore(GdkPixbuf.Pixbuf, GObject.TYPE_STRING)
		local_treeview.set_model(local_store)

		self.populate_local_tree_model(local_treeview)

	def setup_remote_tree_model(self, remote_treeview):
		remote_store = Gtk.ListStore(GdkPixbuf.Pixbuf, GObject.TYPE_STRING, GObject.TYPE_STRING)
		remote_treeview.set_model(remote_store)

	def populate_local_tree_model(self, local_treeview):
		self.debug_print("Populating local tree model")

		# Build the tree path out of current_local_path.
		store = local_treeview.get_model()
		store.clear()

		# Add the '..' directory
		iterator = store.append()
		pixbuf = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.progpath, "directory.png"))
		store.set(iterator, self.ICON, pixbuf, self.FILENAME, "..")

		# Parse through the directory, adding all of its contents to the model.
		filelst = os.listdir(self.current_local_path)
		filelst.sort(key=lambda v: (v.upper(), v))
		for file in filelst:
			if file in ignore_files:
				continue
			temp = os.path.join(self.current_local_path, file)
			if os.path.isdir(temp):
				pixbuf = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.progpath, "directory.png"))
				iterator = store.append()
				store.set(iterator, self.ICON, pixbuf, self.FILENAME, file)

		for file in filelst:
			if file in ignore_files:
				continue
			temp = os.path.join(self.current_local_path, file)
			if os.path.isfile(temp):
				pixbuf = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.progpath, "file.png"))
				iterator = store.append()
				store.set(iterator, self.ICON, pixbuf, self.FILENAME, file)

		local_treeview.columns_autosize()

		if self.put_button:
			self.put_button.set_sensitive(False)

	def populate_remote_tree_model(self, remote_treeview):
		self.debug_print("Populating remote tree model")

		self.remote_dirs.clear()
		self.remote_files.clear()

		if self.current_remote_path.strip("/") == "":
			# Much faster method, but only works for the root directory...

			## Fetch the files
			files = self.load_remote_root_files()
			self.debug_print(f"Remote file(s) fetched: {str(files)}")

			## Fetch the directories
			directories = self.load_remote_root_directories()
			self.debug_print(f"Remote directories fetched: {str(directories)}")

			# Add the directories and files to the treeview
			if directories:
				for d in directories:
					if d == '': continue
					self.remote_dirs.append(d)
			if files:
				for f in files:
					if f == '': continue
					self.remote_files.append(f)
		else:
			# Much slower method, but works for sub-directories of root...

			## Get all the files and directories from remote
			nondirs = []
			filelist=self.load_remote_directory(self.current_remote_path)
			for f in filelist:
				if self.is_remote_dir(self.current_remote_path+'/'+f):
					self.remote_dirs.append(f)
				else:
					nondirs.append(f)
			for f in range(len(nondirs)):
				self.remote_files.append(nondirs[f])

		self.fill_remote_treeview(remote_treeview)

	def fill_remote_treeview(self, remote_treeview):
		# Clear the treeview
		remote_store = remote_treeview.get_model()
		remote_store.clear()

		# Make sure the files are sorted alphabetically
		self.remote_dirs.sort(key=lambda v: (v.upper(), v))
		self.remote_files.sort(key=lambda v: (v.upper(), v))

		# Add '..' to directory
		iterator = remote_store.append()
		pixbuf = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.progpath, "directory.png"))
		remote_store.set(iterator, self.ICON, pixbuf, self.FILENAME, "..", self.TYPE, 'd')

		# Fill the treeview with the directories and files
		for d in self.remote_dirs:
			iterator = remote_store.append()
			pixbuf = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.progpath, "directory.png"))
			remote_store.set(iterator, self.ICON, pixbuf, self.FILENAME, d, self.TYPE, 'd')
		for f in self.remote_files:
			iterator = remote_store.append()
			pixbuf = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.progpath, "file.png"))
			remote_store.set(iterator, self.ICON, pixbuf, self.FILENAME, f, self.TYPE, 'f')

		remote_treeview.columns_autosize()
		self.enable_remote_file_buttons(False)

	def is_remote_dir(self, path):
		args=['ls',path]
		output=subprocess.run(self.ampy_command + args,capture_output=True)
		if output.returncode == 0:
			return True
		else:
			return False

	def load_remote_root_files(self):
		""" Returns an array of files in the root directory of the remote device by running a python script to the device.
		This method is much faster than running the 'ls' command and then parsing every file to check whether it is
		a file or a directory...
		"""
		files = None
		run_file = os.path.join(
			os.path.join(self.progpath, "util", "print_files.py"))
		args = ['run', run_file]
		output = subprocess.run(self.ampy_command + args, capture_output=True)
		if output.returncode == 0:
			files = output.stdout.decode("UTF-8").split("\r\n")
			files.sort(key=lambda v: (v.upper(), v))  # Make sure the files are sorted alphabetically
		else:
			error = output.stderr.decode("UTF-8")
			self.print_and_terminal(self.terminal_buffer, "ERROR: " + error, MsgType.ERROR)

		return files

	def load_remote_root_directories(self):
		""" Returns an array of directories in the root directory of the remote device by running a python script to the device.
		This method is much faster than running the 'ls' command and then parsing every file to check whether it is
		a file or a directory...
		"""
		directories = None
		run_file = os.path.join(
			os.path.join(self.progpath, "util", "print_directories.py"))
		args = ['run', run_file]
		output = subprocess.run(self.ampy_command + args, capture_output=True)
		if output.returncode == 0:
			directories = output.stdout.decode("UTF-8").split("\r\n")
			directories.sort(key=lambda v: (v.upper(), v))  # Make sure the directories are sorted alphabetically
		else:
			error = output.stderr.decode("UTF-8")
			self.print_and_terminal(self.terminal_buffer, "ERROR: " + error, MsgType.ERROR)

		return directories

	def load_remote_directory(self,path):
		response=self.check_for_device()
		if response == 0:
			args=['ls', path]
			output=subprocess.run(self.ampy_command + args, capture_output=True)
			if output.stderr.decode("utf-8") == "":
				filestring = output.stdout.decode("utf-8")
				filelist = filestring.split('\n')
				returnlist = []
				for fname in filelist:
					if fname != "" :
						head,tail = os.path.split(fname)
						returnlist.append(tail)
				return returnlist
			else:
				return []
			
	def remote_rows_selected(self, remote_treeview):
		tree_selection = remote_treeview.get_selection()
		model, paths = tree_selection.get_selected_rows()

		if paths and len(paths) > 0:
			files = []
			for fpath in paths:
				iterator = model.get_iter(fpath)
				fname = model.get_value(iterator, self.FILENAME)
				ftype = model.get_value(iterator, self.TYPE)
				file = (fname, ftype)
				files.append(file)
			return files
		else:
			return None
			
	def local_rows_selected(self, local_treeview):
		tree_selection = local_treeview.get_selection()
		model, paths = tree_selection.get_selected_rows()
		if paths and len(paths) > 0:
			files = []
			for fpath in paths:
				iterator = model.get_iter(fpath)
				file = model.get_value(iterator, self.FILENAME)
				files.append(file)
			return files
		else:
			return None

	def get_button_clicked(self,button, local_treeview, remote_treeview, terminal_buffer):
		""" Retrieves a file from the remote device
		"""
		response=self.check_for_device()
		if response == 0:
			rows_selected = self.remote_rows_selected(remote_treeview)
			if rows_selected is None or len(rows_selected) == 0:
				self.print_and_terminal(terminal_buffer,
										"No file selected",
										MsgType.WARNING)
				return
			else:
				for row_selected in rows_selected:
					fname, ftype = row_selected
					if ftype == 'f':
						os.chdir(self.current_local_path)
						self.get_file(local_treeview, terminal_buffer,
										self.current_remote_path + "/" + fname,
									   	os.path.join(self.current_local_path, fname))
				self.populate_local_tree_model(local_treeview)

	def get_file(self, local_treeview, terminal_buffer, src_remote_file, dest_local_file, print=True):
		args = ['get', src_remote_file, dest_local_file]
		output = subprocess.run(self.ampy_command + args, capture_output=True)
		if output.returncode == 0:
			if print:
				self.print_and_terminal(terminal_buffer,
									"File '{}' successfully fetched from device".format(src_remote_file),
									MsgType.INFO)
		else:
			if print:
				self.print_and_terminal(terminal_buffer,
									"Error fetching file from device: '{}'".format(output.stderr.decode("utf-8"),
																				   MsgType.ERROR))

	def put_button_clicked(self, button, local_treeview, remote_treeview, terminal_buffer):
		""" Uploads a file to the remote device
		"""
		response = self.check_for_device()
		if response == 0:
			files_selected = self.local_rows_selected(local_treeview)
			if files_selected is None or len(files_selected) == 0:
				self.print_and_terminal(terminal_buffer,
										"No file selected", MsgType.WARNING)
				return
			else:
				for file in files_selected:
					source = os.path.join(self.current_local_path, file)
					dest = self.current_remote_path + '/' + file
		
					args = ['put', source, dest]
					output = subprocess.run(self.ampy_command + args, capture_output=True)
					if output.returncode != 0:
						self.print_and_terminal(terminal_buffer,
												"Error uploading file from device: '{}'".format(output.stderr.decode("utf-8")),
												MsgType.ERROR)
						return
					self.debug_print("File '{}' successfully uploaded to device".format(file))

					if os.path.isdir(source) and not file in self.remote_dirs:
						self.remote_dirs.append(file)
					elif os.path.isfile(source) and not file in self.remote_files:
						self.remote_files.append(file)
					self.fill_remote_treeview(remote_treeview)

				self.populate_remote_tree_model(remote_treeview)
				msg = "File(s) '{}' successfully uploaded to remote device".format(", ".join(files_selected))
				self.print_and_terminal(terminal_buffer, msg, MsgType.INFO)


	def delete_button_clicked(self, button, remote_treeview, terminal_buffer):
		""" Deletes the selected remote files/directories from the remote device.
		"""
		response = self.check_for_device()
		if response == 0:
			rows_selected = self.remote_rows_selected(remote_treeview)
			if rows_selected is None or len(rows_selected) == 0:
				return
			else:
				if len(rows_selected) == 1:
					msg = "Are you sure you want to delete '{}'?".format(rows_selected[0][0])
				else:
					msg = "Are you sure you want to delete these {} files?".format(len(rows_selected))
				# Confirmation dialog
				dialog = Gtk.MessageDialog(
					transient_for=self,
					flags=0,
					message_type=Gtk.MessageType.QUESTION,
					buttons=Gtk.ButtonsType.YES_NO,
					text=msg,
				)
				dialog.set_decorated(False)
				response = dialog.run()
				dialog.destroy()

				if response == Gtk.ResponseType.NO:
					self.debug_print("File deletion canceled")
					return

				file_in_selection = False
				directory_in_selection = False
				for row_selected in rows_selected:
					fname, ftype = row_selected
					args = None
					if ftype == 'f':
						args=['rm', self.current_remote_path + '/' + fname]
						file_in_selection = True
						self.remote_files.remove(fname)
					elif ftype == 'd':
						args = ['rmdir', self.current_remote_path + '/' + fname]
						directory_in_selection = True
						self.remote_dirs.remove(fname)
					if args is None:
						self.print_and_terminal(terminal_buffer, "Invalid file type detected", MsgType.ERROR)
						return
					output=subprocess.run(self.ampy_command + args, capture_output=True)
					if output.returncode != 0:
						error = output.stderr.decode("UTF-8")
						self.print_and_terminal(self.terminal_buffer, "ERROR: " + error, MsgType.ERROR)

				# File deletion done
				if len(rows_selected) == 1:
					if file_in_selection:
						preamb = "File"
					elif directory_in_selection:
						preamb = "Directory"
					else:
						self.print_and_terminal(terminal_buffer, "No file, nor directory deleted?", MsgType.ERROR)
						return
					msg = "{} '{}' successfully deleted from device".format(preamb, rows_selected[0][0])
				else:
					files = rows_selected[0][0]
					for i in range(1, len(rows_selected)):
						files += ", {}".format(rows_selected[i][0])
					if file_in_selection:
						preamb = "Files"
					elif directory_in_selection:
						preamb = "Directories"
					else:
						self.print_and_terminal(terminal_buffer, "No files, nor directories deleted?", MsgType.ERROR)
						return
					msg = "{} '{}' successfully deleted from device".format(preamb, files)
				self.fill_remote_treeview(remote_treeview)
				self.print_and_terminal(terminal_buffer, msg, MsgType.INFO)

	def mkdir_button_clicked(self,button, remote_treeview, terminal_buffer):
		""" Creates a new directory on the remote device.
		"""
		response=self.check_for_device()
		if response == 0:
			dirname = ''
			dialog=PopUp(self)
			response = dialog.run()

			if response == Gtk.ResponseType.OK:
				dirname = dialog.get_result()
			dialog.destroy()
			if dirname != '':
				if dirname in self.remote_dirs:
					self.print_and_terminal(self.terminal_buffer, "Remote directory already exists", MsgType.WARNING)
				args=['mkdir',self.current_remote_path+'/'+dirname]
				output=subprocess.run(self.ampy_command+args,capture_output=True)
				if output.returncode == 0:
					self.remote_dirs.append(dirname)
					self.fill_remote_treeview(remote_treeview)
				else:
					error = output.stderr.decode("UTF-8")
					self.print_and_terminal(self.terminal_buffer, "ERROR: " + error, MsgType.ERROR)

	def reset_button_clicked(self,button, remote_treeview,terminal_buffer):
		""" Performs a soft reset/reboot of the remote device.
		"""
		response=self.check_for_device()
		if response == 0:
			args=['reset']
			output=subprocess.run(self.ampy_command+args,capture_output=True)
			if output.returncode == 0:
				self.current_remote_path=""
				self.populate_remote_tree_model(remote_treeview)
			else:
				error = output.stderr.decode("UTF-8")
				self.print_and_terminal(self.terminal_buffer, "ERROR: " + error, MsgType.ERROR)

	def run_local_button_clicked(self, button, local_treeview, terminal_buffer):
		response = self.check_for_device()
		if response == 0:
			rows_selected = self.local_rows_selected(local_treeview)
			if rows_selected is None or len(rows_selected) == 0:
				return
			else:
				for row_selected in rows_selected:
					usepath = os.path.join(self.current_local_path, row_selected)
					if os.path.isfile(usepath):
						self.run_local_file(usepath, terminal_buffer)

	def run_local_file(self, local_path, terminal_buffer):
		args = ['run', local_path]
		try:
			output = subprocess.run(self.ampy_command + args, capture_output=True)
			if output.returncode == 0:
				self.print_and_terminal(terminal_buffer, "---------Running local file {}---------".format(os.path.basename(local_path)),
										MsgType.INFO)
				self.print_and_terminal(terminal_buffer, output.stdout.decode("UTF-8"), MsgType.INFO)
				self.print_and_terminal(terminal_buffer, "----------------------------", MsgType.INFO)
			else:
				error = output.stderr.decode("UTF-8")
				self.print_and_terminal(terminal_buffer, error, MsgType.ERROR)
		except PyboardError as e:
			self.print_and_terminal(terminal_buffer, e, MsgType.ERROR)

	def run_remote_button_clicked(self,button, remote_treeview, terminal_buffer):
		response=self.check_for_device()
		if response == 0:
			rows_selected = self.remote_rows_selected(remote_treeview)
			if rows_selected is None or len(rows_selected) == 0:
				return
			else:
				# Check if tmp dir exists, if not, create it
				if not os.path.exists(os.path.join(self.progpath, "tmp")):
					os.mkdir(os.path.join(self.progpath, "tmp"))
				for row_selected in rows_selected:
					fname,ftype = row_selected
					if ftype == 'f':
						usepath = self.current_remote_path +'/' + fname

						# Fetch the file to be run from the remote device as a temp file, run that local temp file, then delete the temp file
						tmp_file = os.path.join(self.progpath, "tmp", fname)
						self.get_file(terminal_buffer, usepath, tmp_file, print=False)
						self.run_local_file(tmp_file, terminal_buffer)
						os.remove(tmp_file)

	def on_local_row_selected(self, tree_selection):
		model, paths = tree_selection.get_selected_rows()
		if self.connected and paths and len(paths) > 0:
			self.put_button.set_sensitive(True)
			all_files = True	# Checks whether only files are selected
			for fpath in paths:
				iterator = model.get_iter(fpath)
				file = model.get_value(iterator, self.FILENAME)
				if file == "..":
					all_files = False
					self.put_button.set_sensitive(False)
					break
				elif os.path.isdir(os.path.join(self.current_local_path, file)):
					all_files = False
					break
			self.run_local_button.set_sensitive(all_files)
		else:
			self.put_button.set_sensitive(False)
			self.run_local_button.set_sensitive(False)

	def on_local_row_activated(self, local_treeview, fpath, column):
		model = local_treeview.get_model()
		iterator = model.get_iter(fpath)
		if iterator:
			file = model.get_value(iterator, self.FILENAME)
			location = os.path.join(self.current_local_path, file)
			if file == "..":
				head,tail = os.path.split(self.current_local_path)
				self.current_local_path = head
				location = self.current_local_path
			if os.path.isdir(location):
				self.current_local_path = location
				self.populate_local_tree_model(local_treeview)

	def enable_remote_buttons(self, value: bool):
		if value:
			# The other buttons need a file or directory to be selected first
			self.remote_refresh_button.set_sensitive(True)
			self.mkdir_button.set_sensitive(True)
			self.reset_button.set_sensitive(True)
			self.run_remote_button.set_sensitive(True)
		else:
			self.remote_refresh_button.set_sensitive(False)
			self.get_button.set_sensitive(False)
			self.mkdir_button.set_sensitive(False)
			self.delete_button.set_sensitive(False)
			self.reset_button.set_sensitive(False)
			self.run_remote_button.set_sensitive(False)
	def enable_remote_file_buttons(self, value: bool):
		self.get_button.set_sensitive(value)
		self.run_remote_button.set_sensitive(value)
		self.delete_button.set_sensitive(value)

	def on_remote_row_selected(self, tree_selection):
		response = self.check_for_device()
		if response == 0:
			model, paths = tree_selection.get_selected_rows()
			only_files_selected = True
			for fpath in paths:
				iterator = model.get_iter(fpath)
				ftype = model.get_value(iterator, self.TYPE)

				if ftype == 'd':
					only_files_selected = False

			self.enable_remote_file_buttons(True)
			if not only_files_selected:
				self.run_remote_button.set_sensitive(False)
		else:
			self.enable_remote_file_buttons(False)

	def on_remote_row_activated(self, remote_treeview, fpath, column):
		response=self.check_for_device()
		if response == 0:
			model = remote_treeview.get_model()
			iterator = model.get_iter(fpath)
			if iterator:
				fname = model.get_value(iterator, self.FILENAME)
				ftype = model.get_value(iterator, self.TYPE)
				

				location = self.current_remote_path  + '/' + fname
				
				if fname == "..":
					head,tail = os.path.split(self.current_remote_path)
					self.current_remote_path = head
					self.populate_remote_tree_model(remote_treeview)
				else:
					if ftype == 'd':
						self.current_remote_path = location
						self.populate_remote_tree_model(remote_treeview)

	def clear_terminal(self, button, textbuffer):
		textbuffer.delete(textbuffer.get_start_iter(), textbuffer.get_end_iter())

	def set_terminal_text(self,textbuffer, inString,  msgType: MsgType):
		if textbuffer is None:
			return
		end_iterator = textbuffer.get_end_iter()
		textbuffer.insert_markup(end_iterator, "<span color='{}'>>>> {}</span>".format(msgType.value, inString), -1)

	def debug_print(self, inString):
		if self.debug:
			print(inString)

	def print_and_terminal(self, textbuffer, inString, msgType = MsgType.INFO):
		self.debug_print(inString)
		self.set_terminal_text(textbuffer, inString + "\n", msgType)

	def on_refresh_local_button_clicked(self, button, local_treeview):
		self.populate_local_tree_model(local_treeview)

	def on_refresh_remote_button_clicked(self, button, remote_treeview):
		response=self.check_for_device()
		if response == 0:
			self.populate_remote_tree_model(remote_treeview)

	def on_local_dir_chooser_button_clicked(self, button, local_treeview):
		dialog = Gtk.FileChooserDialog(title="Please choose the local parent directory", parent=self,
									   action=Gtk.FileChooserAction.SELECT_FOLDER)
		dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
										Gtk.STOCK_OPEN, Gtk.ResponseType.OK)

		response = dialog.run()
		if response == Gtk.ResponseType.OK:
			dir = dialog.get_filename()
			self.current_local_path = dir
			self.debug_print(f"Switched to new local directory: {dir}")
			self.populate_local_tree_model(local_treeview)

		dialog.destroy()
		
class PopUp(Gtk.Dialog):
	def __init__(self,parent):
		Gtk.Dialog.__init__(self, "", parent, 0)
		self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
			Gtk.STOCK_OK, Gtk.ResponseType.OK)

             
		self.connect("response", self.on_response)
		self.set_default_size(200,100)
		self.set_border_width(10)

		area = self.get_content_area()
		self.entry = Gtk.Entry()
		self.label = Gtk.Label()
		self.label.set_text("Enter Directory Name")
		self.entry.connect("activate",self.entry_go)
		area.add(self.label)
		area.add(self.entry)
		
		self.show_all()

	def entry_go(self, widget):
		self.response(Gtk.ResponseType.OK)
		
	def on_response(self, widget, response_id):
		self.result = self.entry.get_text ()

	def get_result(self):
		return self.result

class SelectPortPopUp(Gtk.Dialog):
	def __init__(self, parent):
		Gtk.Dialog.__init__(self, "Select port", parent, 0)
		self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
						 Gtk.STOCK_OK, Gtk.ResponseType.OK)

		self.connect("response", self.on_response)
		self.set_default_size(500, 400)
		self.set_border_width(10)

		# Init the treeview
		self.treeview = Gtk.TreeView.new()
		liststore = Gtk.ListStore(str)
		self.treeview.set_model(liststore)
		column = Gtk.TreeViewColumn.new()
		column.set_title("Available serial ports")

		renderer = Gtk.CellRendererText.new()
		column.pack_start(renderer, True)
		column.add_attribute(renderer, "text", 0)
		self.treeview.append_column(column)
		self.treeview.connect("row-activated", self.on_row_activated)

		# Fill the treeview
		self.refresh_ports(None, self.treeview)

		# Button for refreshing the table
		refresh_button = Gtk.Button.new_with_label("Refresh")
		refresh_button.set_tooltip_text("Refresh the list of available ports")
		refresh_button.connect("clicked", self.refresh_ports, self.treeview)

		# Info label
		info_label = Gtk.Label.new("Tip: don't know which port your remote device uses?\n\tUnplug your remote device, click the 'Refresh' button, plug it in again, and click the 'Refresh' button again.\n\tYour device port should now be displayed in the list..")

		# Add the widgets to the dialog
		area = self.get_content_area()
		area.pack_start(self.treeview, True, True, 4)
		area.pack_start(refresh_button, False, False, 4)
		area.pack_start(info_label, False, False, 4)

		self.show_all()

	def refresh_ports(self, button, treeview):
		# Get all the ports
		ports = self.get_ports()

		remote_store = treeview.get_model()
		remote_store.clear()

		for port in ports:
			iterator = remote_store.append()
			remote_store.set(iterator, 0, port)

	def on_response(self, widget, response_id):
		selected = self.treeview.get_selection()
		model, iterator = selected.get_selected()
		if iterator:
			self.result = model.get_value(iterator, 0)
		else:
			self.result = None

	def on_row_activated(self, treeview, path, column):
		self.response(Gtk.ResponseType.OK)

	def get_result(self):
		return self.result

	def get_ports(self):
		if sys.platform.startswith('darwin'):
			return glob.glob('/dev/tty.*')
		ports = serial.tools.list_ports.comports(include_links=True)
		devices = []
		for port in sorted(ports):
			devices.append(port.device)
		return devices
		
class Application(Gtk.Application):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, application_id="org.example.myapp",
						 **kwargs)
		self.window = None

	def do_activate(self):
		if not self.window:
			self.window = AppWindow(application=self, title="AMPY-GUI",
									debug=self.debug, use_timeout=self.use_timeout, timeout_delay=self.timeout_delay)
		self.window.debug = self.debug
		self.window.use_timeout = self.use_timeout
		self.window.timeout_delay = self.timeout_delay
		self.window.show_all()
		self.window.present()

if __name__ == "__main__":
	# Before anything, check if ampy is installed
	try:
		subprocess.run(["ampy", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	except FileNotFoundError:
		print("Error: Adafruit ampy is not installed. Please install it and try again.")
		sys.exit(1)

	# Handle command-line arguments
	debug = False
	use_timeout = True
	timeout_delay = 120
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hdnt:", ["help", "debug", "notimeout", "timedelay="])
		for opt, arg in opts:
			if opt in ['-h', '--help']:
				print("Possible command line arguments:")
				print("\t-h or --help : prints help info.")
				print("\t-d or --debug : enables debug printing in the console that you ran the script in.")
				print(
					"\t-n or --notimeout : disables device connection timeout checking (if the device does not respond after a certain timeout delay, the connection is automatically broken).")
				print(
					"\t-t <timeout delay> or --timedelay <time delay> : specifies the timeout delay in seconds after which the device connection should be checked. Default delay is 120 seconds")
				sys.exit(2)
			elif opt in ['-d', '--debug']:
				debug = True
			elif opt in ['-n', '--notimeout']:
				use_timeout = False
			elif opt in ['-t', '--timedelay']:
				try:
					timeout_delay = int(arg)
				except ValueError:
					print("Wrong formatting of timeout delay, falling back to default delay")
	except Exception as e:
		print("Could not parse command line : {}".format(e))

	app = Application()
	app.debug = debug
	app.use_timeout = use_timeout
	app.timeout_delay = timeout_delay
	app.run()
