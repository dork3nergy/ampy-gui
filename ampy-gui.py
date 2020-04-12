#!/usr/bin/python3

import sys, os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, GdkPixbuf
from gi.repository import Gdk
import subprocess
import math

class AppWindow(Gtk.ApplicationWindow):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.set_border_width(10)
		self.set_size_request(700, 600)
		
		#Numbers are Column Numbers in Model
		self.ICON = 0
		self.FILENAME = 1
		self.TYPE = 2

		
		self.current_local_path = os.getcwd()

		self.progpath = os.path.dirname(sys.argv[0])        
	
		self.current_remote_path = ''

		css = b"""
			textview text {
				background-color: black;
				color:#45ffc1;
			 }
			textview.view {
				padding-left:4px;
				background-color:black;
			}
			frame {
				background-color:#b2b2b2;
				padding:12px;
			}
			"""

		
		provider = Gtk.CssProvider()
		screen = Gdk.Screen.get_default()
		provider.load_from_data(css)
		style_context = Gtk.StyleContext()
		style_context.add_provider_for_screen(
			screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
		)


		self.ampy_args=['/dev/ttyUSB0', '115200', '0']
		self.update_ampy_command()
		
		self.baud_rates=["300", "600", "1200", "2400", "4800", "9600", "14400", "19200", "28800", "38400", "57600","115200"]

		box_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
		box_outer.set_homogeneous(False)
		self.add(box_outer)

		#SETTINGS PANEL SETUP

		port_label = Gtk.Label.new("Port")
		delay_label = Gtk.Label.new("Delay")
		baud_label= Gtk.Label.new("Baud Rate")
		
		port_entry = Gtk.Entry()
		baud_button= Gtk.ComboBoxText.new()
		delay_spin = Gtk.SpinButton.new_with_range(0, 10, 1)
		
		#LOAD BAUD RATES INTO COMBO BOX
		i=0
		while i < len(self.baud_rates):
			baud_button.append_text(self.baud_rates[i])
			i +=1
	
		baud_button.set_active(11)
		delay_spin.set_digits(0)
		port_entry.set_text(self.ampy_args[0])

		#SET EVENT TRIGGERS for SETTINGS
		port_entry.connect("focus-out-event",self.on_port_change)
		baud_button.connect("changed",self.on_baud_change)
		delay_spin.connect("changed",self.on_delay_change)


		#Pack each setting into a box
		port_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
		baud_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
		delay_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

		connect_button = Gtk.Button.new_with_label("Connect")

		port_box.pack_start(port_label,False,False,0)
		port_box.pack_start(port_entry,False,False,0)
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
		local_treeview = Gtk.TreeView.new()
		
		self.setup_local_tree_view(local_treeview)
		self.setup_local_tree_model(local_treeview)
		local_treeview.connect("row-activated", self.on_local_row_activated)

		# CREATE REMOTE TREEVIEW
		remote_treeview = Gtk.TreeView.new()

		self.setup_remote_tree_view(remote_treeview)
		self.setup_remote_tree_model(remote_treeview)
		remote_treeview.connect("row-activated", self.on_remote_row_activated)

		#CREATE SCROLLED WINDOWS
		local_scrolled_win = Gtk.ScrolledWindow(valign="fill", halign="fill")
		local_scrolled_win.set_policy(Gtk.PolicyType.AUTOMATIC, 
								Gtk.PolicyType.AUTOMATIC)
		remote_scrolled_win = Gtk.ScrolledWindow()
		remote_scrolled_win.set_policy(Gtk.PolicyType.AUTOMATIC, 
								Gtk.PolicyType.AUTOMATIC)


		#Create Frame for Local Fileview
		local_scrolled_frame = Gtk.Frame()
		local_scrolled_frame.set_shadow_type(0)
		
		#ADD TREEVIEWS TO SCROLLED WINDOWS
		local_scrolled_win.add(local_treeview)

		local_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,halign="fill")
		local_box.pack_start(local_scrolled_win,True,True,0)
		local_refresh_button = Gtk.Button.new_with_label("Refresh")
		local_refresh_button.connect("clicked", self.refresh_local,local_treeview)
		local_box.pack_start(local_refresh_button,False,False,0)
		local_scrolled_frame.add(local_box)

		remote_scrolled_win.add(remote_treeview)

		remote_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,halign="fill")
		remote_box.pack_start(remote_scrolled_win,True,True,0)
		remote_refresh_button = Gtk.Button.new_with_label("Refresh")
		remote_refresh_button.connect("clicked", self.refresh_remote,remote_treeview)
		remote_box.pack_start(remote_refresh_button,False,False,0)

		#DEFINE TRANSFER BUTTONS
		putget_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,valign="center")
		get_button = Gtk.Button.new_with_label("<< GET <<")
		put_button = Gtk.Button.new_with_label(">> PUT >>")

		putget_box.pack_start(get_button,False,False,0)
		putget_box.pack_start(put_button,False,False,0)

		#DEFINE REMOTE FUNCTION BOXES

		remote_buttons_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,valign="center")
		remote_services = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,halign="fill")


		mkdir_button = Gtk.Button.new_with_label("MKDIR")
		rmdir_button = Gtk.Button.new_with_label("RMDIR")
		run_button = Gtk.Button.new_with_label("RUN")
		reset_button = Gtk.Button.new_with_label("RESET")
		delete_button = Gtk.Button.new_with_label("DELETE")

		remote_buttons_box.pack_start(mkdir_button,False,False,0)
		remote_buttons_box.pack_start(rmdir_button,False,False,0)
		remote_buttons_box.pack_start(delete_button,False,False,0)
		remote_buttons_box.pack_start(reset_button,False,False,0)
		remote_buttons_box.pack_start(run_button,False,False,0)

		#PACK IT UP
		#Create Frame for Remote Services
		remote_services_frame = Gtk.Frame()
		remote_services_frame.add(remote_services)
		remote_services_frame.set_shadow_type(0)

		filebrowser_box.pack_start(local_scrolled_frame,True, True, 4)
		filebrowser_box.pack_start(putget_box,False,False,4)
		remote_services.pack_start(remote_box,True,True,2)
		remote_services.pack_start(remote_buttons_box,False,False,0)
		filebrowser_box.pack_start(remote_services_frame,True,True,6)


		#CREATE TERMINAL WINDOW
		terminal_window = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,halign="fill")
		terminal_window.set_homogeneous(False)
		box_outer.pack_start(terminal_window,True, True,6)
		
		terminal_view = Gtk.TextView()
		terminal_buffer = terminal_view.get_buffer()

		#MAkE TERMINAL READ ONLY
		terminal_view.set_property('editable',False)
		terminal_view.set_property('cursor-visible',False)

		terminal_scroll = Gtk.ScrolledWindow()
		terminal_scroll.add(terminal_view)
		terminal_window.pack_start(terminal_scroll,True,True,6)

		put_button.connect("clicked",self.put_button_clicked, local_treeview, remote_treeview,terminal_buffer)
		get_button.connect("clicked",self.get_button_clicked, local_treeview, remote_treeview,terminal_buffer)
		connect_button.connect("clicked",self.connect_device, remote_treeview,terminal_buffer)
		run_button.connect("clicked",self.run_button_clicked, remote_treeview,terminal_buffer)
		mkdir_button.connect("clicked",self.mkdir_button_clicked, remote_treeview,terminal_buffer)
		rmdir_button.connect("clicked",self.rmdir_button_clicked, remote_treeview,terminal_buffer)
		reset_button.connect("clicked",self.reset_button_clicked,remote_treeview,terminal_buffer)
		delete_button.connect("clicked",self.delete_button_clicked, remote_treeview,terminal_buffer)

		#SET FOCUS TO LOCAL FILELIST
		local_treeview.grab_focus()
		
	def force_refresh(self):
		while Gtk.events_pending():     #   this forces GTK to refresh the screen
			Gtk.main_iteration() 


	def connect_device(self, button, remote_treeview,terminal_buffer):
		response = self.check_for_device()
		if(response == 0):
			self.populate_remote_tree_model(remote_treeview)

	def update_ampy_command(self):
		self.ampy_command = ['ampy', '-p', self.ampy_args[0], '-b',self.ampy_args[1], '-d',self.ampy_args[2]]

	def check_for_device(self):
		try:
			os.stat(self.ampy_args[0])
			return 0
		except OSError:
			dialog=Warning(self,"Can't Find Your Remote Device\nCheck the Port Settings")
			response = dialog.run()
			dialog.destroy()
			return -1
		
	def on_port_change(self,port,event):
			self.ampy_args[0]=port.get_text()
			self.check_for_device()
	def on_baud_change(self,baud):
			selected = baud.get_active()
			self.ampy_args[1]= self.baud_rates[selected]
			self.update_ampy_command()

	def on_delay_change(self,delay):
			value = delay.get_value()
			value = math.trunc(value)
			self.ampy_args[2]=str(value)
			self.update_ampy_command()

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

	def setup_local_tree_model(self, local_treeview):
		local_store = Gtk.ListStore(GdkPixbuf.Pixbuf, GObject.TYPE_STRING)
		local_treeview.set_model(local_store)

		self.populate_local_tree_model(local_treeview)

	def setup_remote_tree_model(self, remote_treeview):
		remote_store = Gtk.ListStore(GdkPixbuf.Pixbuf, GObject.TYPE_STRING, GObject.TYPE_STRING)
		remote_treeview.set_model(remote_store)

	def populate_local_tree_model(self, local_treeview):
		store = local_treeview.get_model()
		store.clear()
		location = self.current_local_path
		# Build the tree path out of current_local_path.

		iter = store.append()
		pixbuf = GdkPixbuf.Pixbuf.new_from_file (self.progpath+"/"+"directory.png")
		store.set(iter, self.ICON, pixbuf, self.FILENAME, "..")

		# Parse through the directory, adding all of its contents to the model.

		filelst = os.listdir(location)
		filelst.sort()
		for file in filelst:
			temp = location + "/" + file
			if os.path.isdir(temp):
				pixbuf = GdkPixbuf.Pixbuf.new_from_file (self.progpath+"/"+"directory.png")
				iter = store.append()
				store.set(iter, self.ICON, pixbuf, self.FILENAME, file)

		for file in filelst:
			temp = location + "/" + file
			if os.path.isfile(temp):
				pixbuf = GdkPixbuf.Pixbuf.new_from_file (self.progpath+"/"+"file.png")
				iter = store.append()
				store.set(iter, self.ICON, pixbuf, self.FILENAME, file)

	def populate_remote_tree_model(self, remote_treeview):

		remote_store = remote_treeview.get_model()
		remote_store.clear()
		nondirs = []
		#Add .. to directory
		iter = remote_store.append()
		pixbuf = GdkPixbuf.Pixbuf.new_from_file (self.progpath+"/"+"directory.png")
		remote_store.set(iter, self.ICON, pixbuf,self.FILENAME, "..",self.TYPE,'d')
		filelist=self.load_remote_directory(self.current_remote_path)
		for f in filelist:
			if self.is_remote_dir(self.current_remote_path+'/'+f):
				iter = remote_store.append()
				pixbuf = GdkPixbuf.Pixbuf.new_from_file (self.progpath+"/"+"directory.png")
				isdir = 'd'
				remote_store.set(iter, self.ICON, pixbuf,self.FILENAME, f,self.TYPE, isdir)
			else:
				nondirs.append(f)
		for f in range(len(nondirs)):
			iter = remote_store.append()
			pixbuf = GdkPixbuf.Pixbuf.new_from_file (self.progpath+"/"+"file.png")
			remote_store.set(iter, self.ICON, pixbuf,self.FILENAME, nondirs[f],self.TYPE,'f')


	def is_remote_dir(self,path):
		args=['ampy', '-p', self.ampy_args[0], '-b',self.ampy_args[1], '-d',self.ampy_args[2] ,'ls',path]
		output=subprocess.run(args,capture_output=True)
		if output.returncode == 0:
			return True
		else:
			return False
			
	def load_remote_directory(self,path):
		response=self.check_for_device()
		if (response == 0):
			args=['ampy', '-p', self.ampy_args[0], '-b',self.ampy_args[1], '-d',self.ampy_args[2] ,'ls',path]
			output=subprocess.run(args,capture_output=True)
			if output.stderr.decode("utf-8") == "":
				filestring = output.stdout.decode("utf-8")
				filelist=filestring.split('\n')
				i=0
				returnlist = []
				for fname in filelist:
					if fname != "" :
						head,tail = os.path.split(fname)
						returnlist.append(tail)
						i += 1
				return returnlist
			else:
				return []
			
	def remote_row_selected(self, remote_treeview):
		selected = remote_treeview.get_selection()
		model, iter = selected.get_selected()
		if(iter is not None):
			fname = model.get_value(iter, self.FILENAME)
			ftype = model.get_value(iter, self.TYPE)
			row_selected=(fname,ftype)
			return row_selected
		else:
			return 0
			
	def local_row_selected(self, local_treeview):
		selected = local_treeview.get_selection()
		model, iter = selected.get_selected()
		if(iter is not None):
			fname = model.get_value(iter, self.FILENAME)
			return fname
		else:
			return 0

	def get_button_clicked(self,button, local_treeview, remote_treeview,terminal_buffer):
		response=self.check_for_device()
		if (response == 0):
			row_selected = self.remote_row_selected(remote_treeview)
			if row_selected == 0:
				return
			else:
				fname,ftype = row_selected
				if ftype == 'f':
					os.chdir(self.current_local_path)
					args=['get',fname,self.current_local_path+'/'+fname]
					output=subprocess.run(self.ampy_command+args,capture_output=True)
					if output.returncode == 0:
						self.populate_local_tree_model(local_treeview)
			

	def put_button_clicked(self,button, local_treeview, remote_treeview,terminal_buffer):
		response=self.check_for_device()
		if (response == 0):
			file_selected = self.local_row_selected(local_treeview)
			if file_selected == 0:
				return
			else:
				source=self.current_local_path+'/'+file_selected
				dest = self.current_remote_path+'/'+file_selected
		
				args=['put',source,dest]
				output=subprocess.run(self.ampy_command+args,capture_output=True)
				if output.returncode == 0:
					self.populate_remote_tree_model(remote_treeview)

	def delete_button_clicked(self,button, remote_treeview,terminal_buffer):
		response=self.check_for_device()
		if (response == 0):
			row_selected = self.remote_row_selected(remote_treeview)
			if row_selected == 0:
				return
			else:
				fname,ftype = row_selected
				if ftype == 'f':
					args=['rm',self.current_remote_path+'/'+fname]
					output=subprocess.run(self.ampy_command+args,capture_output=True)
					if output.returncode == 0:
						self.populate_remote_tree_model(remote_treeview)
					else:
						error = output.stderr.decode("UTF-8")
						index=error.find("RuntimeError:")
						self.set_terminal_text(terminal_buffer,error[index:]+"\n\n")

	def rmdir_button_clicked(self,button, remote_treeview, terminal_buffer):
		response=self.check_for_device()
		if (response == 0):
			row_selected = self.remote_row_selected(remote_treeview)
			if row_selected == 0:
				return
			else:
				fname,ftype = row_selected
				if ftype == 'd':
					args=['rmdir',self.current_remote_path+'/'+fname]
					output=subprocess.run(self.ampy_command+args,capture_output=True)
					if output.returncode == 0:
						self.populate_remote_tree_model(remote_treeview)
					else:
						error = output.stderr.decode("UTF-8")
						index=error.find("RuntimeError:")
						self.set_terminal_text(terminal_buffer,error[index:]+"\n\n")
					
	def mkdir_button_clicked(self,button, remote_treeview, terminal_buffer):
		response=self.check_for_device()
		if (response == 0):
			dirname = ''
			dialog=PopUp(self)
			response = dialog.run()

			if response == Gtk.ResponseType.OK:
				dirname = dialog.get_result()
			dialog.destroy()
			if (dirname != ''):
				args=['mkdir',self.current_remote_path+'/'+dirname]
				output=subprocess.run(self.ampy_command+args,capture_output=True)
				if output.returncode == 0:
					self.populate_remote_tree_model(remote_treeview)
				else:
					error = output.stderr.decode("UTF-8")
					index=error.find("RuntimeError:")
					self.set_terminal_text(terminal_buffer,error[index:]+"\n\n")

	def reset_button_clicked(self,button, remote_treeview,terminal_buffer):
		response=self.check_for_device()
		if (response == 0):
			args=['reset']
			output=subprocess.run(self.ampy_command+args,capture_output=True)
			if output.returncode == 0:
				self.current_remote_path=""
				self.populate_remote_tree_model(remote_treeview)
			else:
				error = output.stderr.decode("UTF-8")
				index=error.find("RuntimeError:")
				self.set_terminal_text(terminal_buffer,error[index:]+"\n\n")

	def run_button_clicked(self,button, remote_treeview, terminal_buffer):
		response=self.check_for_device()
		if (response == 0):
			row_selected = self.remote_row_selected(remote_treeview)
			if row_selected == 0:
				return
			else:
				fname,ftype = row_selected
				if ftype == 'f':
					usepath = self.current_remote_path +'/'+fname
					usepath=usepath.strip('/')
						
					args=['run',usepath]
					output=subprocess.run(self.ampy_command+args,capture_output=True)
					if output.returncode == 0:
						self.set_terminal_text(terminal_buffer,"---------Run Output---------\n")
						self.set_terminal_text(terminal_buffer,output.stdout.decode("UTF-8")+"\n")
						self.set_terminal_text(terminal_buffer,"----------------------------\n")
					else:
						error = output.stderr.decode("UTF-8")
						index=error.find("RuntimeError:")
						self.set_terminal_text(terminal_buffer,error[index:]+"\n\n")

	def on_local_row_activated(self, local_treeview, fpath, column):
		model = local_treeview.get_model()
		iter = model.get_iter(fpath)
		if iter:
			file = model.get_value(iter, self.FILENAME)
			location = self.current_local_path + "/" + file
			if file == "..":
				head,tail = os.path.split(self.current_local_path)
				self.current_local_path = head
				location = self.current_local_path
			if os.path.isdir(location):
				self.current_local_path = location
				self.populate_local_tree_model(local_treeview)

	def on_remote_row_activated(self, remote_treeview, fpath, column):
		response=self.check_for_device()
		if (response == 0):
			model = remote_treeview.get_model()
			iter = model.get_iter(fpath)
			if iter:
				fname = model.get_value(iter, self.FILENAME)
				icon = model.get_value(iter, self.ICON)
				ftype = model.get_value(iter, self.TYPE)
				

				location = self.current_remote_path  + '/' + fname
				
				if(fname == ".."):
					head,tail = os.path.split(self.current_remote_path)
					self.current_remote_path = head
					self.populate_remote_tree_model(remote_treeview)
				else:
					if(ftype == 'd'):
						self.current_remote_path=location
						self.populate_remote_tree_model(remote_treeview)
				
	def set_terminal_text(self,textbuffer,inString):
		end_iter = textbuffer.get_end_iter()
		textbuffer.insert(end_iter, inString)

	def refresh_local(self, button,local_treeview):
		self.populate_local_tree_model(local_treeview)

	def refresh_remote(self,button, remote_treeview):
		response=self.check_for_device()
		if (response == 0):
			self.populate_remote_tree_model(remote_treeview)

class Warning(Gtk.Dialog):
	def __init__(self,parent,msg):
		Gtk.Dialog.__init__(self, "Error", parent, 0)

		self.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)


		self.set_default_size(300,50)
		self.set_decorated(False)
		self.set_border_width(2)

		action_area= self.get_action_area()
		action_area.set_halign(3)

		box = self.get_content_area()
		box.set_homogeneous(True)
		box.set_border_width(6)
		label = Gtk.Label()
		label.set_text(msg)
		label.set_justify(2)
		box.pack_start(label,True,True,0)
		self.show_all()
		
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
		
class Application(Gtk.Application):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, application_id="org.example.myapp",
						 **kwargs)
		self.window = None

	def do_activate(self):
		if not self.window:
			self.window = AppWindow(application=self, title="AMPY-GUI")
		self.window.show_all()
		self.window.present()

if __name__ == "__main__":
	app = Application()
	app.run(sys.argv)
