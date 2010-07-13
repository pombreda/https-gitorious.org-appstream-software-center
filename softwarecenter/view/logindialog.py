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
        self.parent = parent

        self.dialog_login.set_default_size(420, 315)
        self.image_review_login.set_from_file(datadir+"/images/ubuntu_cof.svg")
        
        # Put our own bottom in
        self.dialog_internal_vbox = self.dialog_login.get_action_area().get_parent()
        self.dialog_login.get_action_area().destroy()
        self.dialog_internal_vbox.pack_start(self.alignment_bottom)

        # this is neccessary to show our new bottom stuff
        self.alignment_bottom.show_all()

    def login(self):
        self.loginbackend.login()

    def cb_need_username_password(self, lp):
        res = self.dialog_login.run()
        self.dialog_login.hide()
        if res != gtk.RESPONSE_OK:
            self.on_button_cancel_clicked()
            return 
        self._enter_user_name_password_finished()

    def cb_login_successful(self, lp, token):
        """ callback when the login was successful """
        print "login_successful", token

    def cb_login_failure(self, lp):
        """ callback when the login failed """
        softwarecenter.view.dialogs.error(self.parent,
                                          _("Authentication failure"),
                                          _("Sorry, please try again"))
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
            
            self.action = index
            
            if index != self.ACTION_LOGIN:
                for widget in [self.label_review_login_password, self.entry_review_login_password, self.checkbutton_remember_password]:
                    widget.set_sensitive(False)
            else:
                for widget in [self.label_review_login_password, self.entry_review_login_password, self.checkbutton_remember_password]:
                    widget.set_sensitive(True)
                
            
    def on_button_login_continue_clicked(self, button_login_continue):
        if self.action == self.ACTION_LOGIN:
            login
            self.spinner_login_status = gtk.Spinner()
            self.label_login_status.set_text(_("Signing in..."))
            # Remove first child
            self.hbox_login_status.get_children()[0]
                
            self.hbox_login_status.pack_start(self.spinner_login_status, False, False)
            self.hbox_login_status.reorder_child(self.spinner_login_status, 0)
            self.spinner_login_status.start()
            self.button_login_continue.set_sensitive(False)
            self.button_login_cancel.set_label(_("Stop"))
            
            self.hbox_login_status.show_all()

    def _enter_user_name_password_finished(self):
        """ run when the user finished with the login dialog box
            this checks the users choices and sets the appropriate state
        """
        has_account = self.radiobutton_review_login_have_account.get_active()
        new_account = self.radiobutton_review_login_register_new_account.get_active()
        forgotten_pw = self.radiobutton_review_login_forgot_password.get_active()
        if has_account:
            username = self.entry_review_login_email.get_text()
            password = self.entry_review_login_password.get_text()
            self.loginbackend.login(username, password)
        elif new_account:
            #print "new_account"
            subprocess.call(["xdg-open", self.loginbackend.new_account_url])
        elif forgotten_pw:
            #print "forgotten passowrd"
            subprocess.call(["xdg-open", self.loginbackend.forgot_password_url])
            
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




