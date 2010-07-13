# Copyright (C) 2010 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import glib
import gobject
import dbus
gobject.threads_init()
import gtk
import logging
import sys

from gettext import gettext as _
import subprocess

from softwarecenter.backend.launchpad import GLaunchpad
from softwarecenter.backend.restfulclient import UbuntuSSOlogin
import softwarecenter

class LoginDialog(object):

    (ACTION_LOGIN, ACTION_REGISTER, ACTION_RETRIEVE_PASSWORD) = range(3)

    def __init__(self, loginbackend, datadir, parent=None):
        self.action = self.ACTION_LOGIN
        
        # launchpad
        self.loginbackend = loginbackend
        self.loginbackend.connect("need-username-password", 
                                self.cb_need_username_password)
        self.loginbackend.connect("login-successful", self.cb_login_successful)
        self.loginbackend.connect("login-failed", self.cb_login_failure)

        # setup ui
        self.builder = gtk.Builder()
        self.builder.add_from_file(datadir+"/ui/login.ui")
        self.builder.connect_signals(self)
        for o in self.builder.get_objects():
            if issubclass(type(o), gtk.Buildable):
                name = gtk.Buildable.get_name(o)
                setattr(self, name, o)
            else:
                print >> sys.stderr, "WARNING: can not get name for '%s'" % o
        # parent
        if parent:
            self.dialog_login.set_transient_for(parent)

        ## Dialog
        # Put our own bottom in...
        self.dialog_login_action_area.destroy()
        self.dialog_login_internal_vbox.pack_start(self.alignment_bottom)
        
        self.dialog_login.set_default_size(420, 315)

        # ..and then show it
        self.alignment_bottom.show_all()

    def login(self):
        self.loginbackend.login()
        return False

    def cb_need_username_password(self, lp):
        res = self.dialog_login.run()
        self.dialog_login.hide()
        if res != gtk.RESPONSE_OK:
            self.on_button_cancel_clicked()
            return 
        self._enter_user_name_password_finished()

    def cb_login_successful(self, lp, token):
        """ callback when the login was successful """
        logging.info("Login was successful %s" % token)

    def cb_login_failure(self, lp):
        """ callback when the login failed """
        
        #softwarecenter.view.dialogs.error(self.parent,
        #                                  _("Authentication failure"),
        #                                  _("Sorry, please try again"))
        self.cb_need_username_password(None)

    def on_button_cancel_clicked(self, button=None):
        self.loginbackend.cancel_login()
        self.dialog_login.hide()
        while gtk.events_pending():
            gtk.main_iteration()
            
    def on_radiobutton_review_toggled(self, radio_button_review):
        if not radio_button_review.get_active():
            # Ignore the just untoggled radiobutton
            pass
        else:
            radio_button_group = radio_button_review.get_group()
            # They are reversed for some reason
            radio_button_group.reverse()
            index = radio_button_group.index(radio_button_review)
            # Find where the radiobutton is in the window..
            # and set the action appropriately
            self.action = index
            
            # Make the widgets under the first radiobutton 
            # insensitive if appropriate
            for widget in [self.label_review_login_password, 
                            self.entry_review_login_password, 
                            self.checkbutton_remember_password]:
                widget.set_sensitive(index == self.ACTION_LOGIN)
                
            
    def on_button_login_continue_clicked(self, button_login_continue):
        self._do_frontend_action()
        self._do_backend_action()
        
    def _do_frontend_action(self):
        if self.action == self.ACTION_LOGIN:
            self._change_login_status(gtk.Spinner(), _("Signing in..."))
            self.button_login_continue.set_sensitive(False)
            self.button_login_cancel.set_label(_("Stop"))
        if self.action == self.ACTION_REGISTER or self.action == self.ACTION_RETRIEVE_PASSWORD:
            self._change_login_status(gtk.Spinner(), _("Opening web browser..."))
            gobject.timeout_add(5000, self.clear_status)

    def clear_status(self):
        self._change_login_status("", (""))

    def _do_backend_action(self):
        """ run when the user finished with the login dialog box
            this checks the users choices and sets the appropriate state
        """
        if self.action == self.ACTION_LOGIN:
            logging.info("Logging in...")
            username = self.entry_review_login_email.get_text()
            password = self.entry_review_login_password.get_text()
            self.loginbackend.login(username, password)
        elif self.action == self.ACTION_REGISTER:
            logging.info("Registering new account...")
            subprocess.call(["xdg-open", self.loginbackend.new_account_url])
        elif self.action == self.ACTION_RETRIEVE_PASSWORD:
            logging.info("Retrieving forgotten password...")
            subprocess.call(["xdg-open", self.loginbackend.forgot_password_url])
     
    def _change_login_status(self, image, label):
        # Remove image
        self.image_login_status.destroy()
        
        # If we have a string, use it as a stock id for a Gtkimage
        if isinstance(image, str):
            self.image_login_status = gtk.Image()
            self.image_login_status.set_from_stock(image, gtk.ICON_SIZE_MENU)
        # Else if we have a gtk.Spinner, just use it
        elif isinstance(image, gtk.Spinner):
            self.image_login_status = image
            self.image_login_status.start()
        else:
            raise TypeError
            
        # Set the label
        self.label_login_status.set_text(label)
            
        # Pack the image/spinner and make it first in order
        self.hbox_login_status.pack_start(self.image_login_status, False, False)
        self.hbox_login_status.reorder_child(self.image_login_status, 0)
        
        self.hbox_login_status.show_all()
     
    def on_network_manager_state_changed(self):
        #if has_active_internet_connection(self):
        pass
            
    def has_active_internet_connection(self):
            bus = dbus.SystemBus()

            proxy = bus.get_object("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
            manager = dbus.Interface(proxy, "org.freedesktop.NetworkManager")

            # Get ActiveConnections array
            manager_prop_iface = dbus.Interface(proxy, "org.freedesktop.DBus.Properties")
            active = manager_prop_iface.Get("org.freedesktop.NetworkManager", "ActiveConnections")
            # Check each one's status
            for a in active:
                ac_proxy = bus.get_object("org.freedesktop.NetworkManager", a)
                prop_iface = dbus.Interface(ac_proxy, "org.freedesktop.DBus.Properties")
                state = prop_iface.Get("org.freedesktop.NetworkManager.ActiveConnection", "State")
                # If at least one is activated
                if state == 2:
                    return True
            return False
        



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # glaunchpad
    #loginbackend = GLaunchpad()
    loginbackend = UbuntuSSOlogin()
    d = LoginDialog(loginbackend, datadir="./data")
    res = d.login()

    try:
        gtk.main()
    except KeyboardInterrupt:
        # FIXME: port shutdown?!?
        #glaunchpad.shutdown() 
        pass




