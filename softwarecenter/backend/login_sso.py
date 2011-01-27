#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import dbus
import gobject
import gtk

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
from gettext import gettext as _

from login import LoginBackend

class LoginBackendDbusSSO(LoginBackend):

    def __init__(self, window_id, appname, login_text):
        super(LoginBackendDbusSSO, self).__init__()
        self.appname = appname
        self.login_text = login_text
        self.bus = dbus.SessionBus()
        self.proxy = self.bus.get_object('com.ubuntu.sso', '/credentials')
        self.proxy.connect_to_signal("CredentialsFound", 
                                     self._on_credentials_found)
        self.proxy.connect_to_signal("CredentialsError", 
                                     self._on_credentials_error)
        self.proxy.connect_to_signal("AuthorizationDenied", 
                                     self._on_authorization_denied)
        self._window_id = window_id

    def login(self, username=None, password=None):
        # alternatively use:
        #  login_or_register_to_get_credentials(appname, tc, help, xid)
        self.proxy.login_to_get_credentials(
            self.appname, self.login_text,
            self._window_id)
        
    def login_or_register(self):
        self.proxy.login_or_register_to_get_credentials(
            self.appname, "", self.login_text,
            self._window_id)

    def _on_credentials_found(self, app_name, credentials):
        if app_name != self.appname:
            return
        self.emit("login-successful", credentials)

    def _on_credentials_error(self, app_name, error, detailed_error):
        if app_name != self.appname:
            return
        # FIXME: do something useful with the error
        self.emit("login-failed")

    def _on_authorization_denied(self, app_name):
        if app_name != self.appname:
            return
        self.cancel_login()
    
if __name__ == "__main__":
    login = LoginBackendDbusSSO()
    login.login()

    gtk.main()
