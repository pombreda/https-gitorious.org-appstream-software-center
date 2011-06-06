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
import gtk
import logging

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

from login import LoginBackend
from test.fake_review_settings import FakeReviewSettings

LOG = logging.getLogger(__name__)

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
        LOG.debug("login()")
        # alternatively use:
        #  login_or_register_to_get_credentials(appname, tc, help, xid)
        self.proxy.login_to_get_credentials(
            self.appname, self.login_text,
            self._window_id)
        
    def login_or_register(self):
        LOG.debug("login_or_register()")
        self.proxy.login_or_register_to_get_credentials(
            self.appname, "", self.login_text,
            self._window_id)

    def _on_credentials_found(self, app_name, credentials):
        if app_name != self.appname:
            return
        self.emit("login-successful", credentials)

    def _on_credentials_error(self, app_name, error, detailed_error):
        LOG.error("_on_credentails_error for %s: %s (%s)" % (
                app_name, error, detailed_error))
        if app_name != self.appname:
            return
        # FIXME: do something useful with the error
        self.emit("login-failed")

    def _on_authorization_denied(self, app_name):
        LOG.error("_on_authorization_denied: %s" % app_name)
        if app_name != self.appname:
            return
        self.cancel_login()


class LoginBackendDbusSSOFake(LoginBackend):

    def __init__(self, window_id, appname, login_text):
        super(LoginBackendDbusSSO, self).__init__()
        self.appname = appname
        self.login_text = login_text
        self._window_id = window_id
        
    def login(self, username=None, password=None):
        response = FakeReviewSettings.login_response
            
        if response == "successful":
            self.emit("login-successful", self._return_credentials)
        elif response == "failed":
            self.emit("login-failed")
        elif response == "denied":
            self.cancel_login()
        
        return
        
    def login_or_register(self):
        pass
                
    def _random_string(self, length):
        retval = ''
        for i in range(0,length):
            retval = retval + random.choice(string.letters + string.digits)
        return retval
 
    def _return_credentials(self):
        c =  {
              'consumer_secret': self._random_string(30),
              'token' : self._random_string(50),
              'consumer_key' : self._random_string(7),
              'name' : 'Ubuntu Software Center @ ' + self._random_string(6),
              'token_secret' : self._random_string(50)
             }
        return c


sso_class = None
def get_sso_class(window_id, appname, login_text):
    """ 
    factory that returns an sso loader singelton
    """
    global sso_class
    if not sso_class:
        if "SOFTWARE_CENTER_FAKE_REVIEW_API" in os.environ:
            sso_class = LoginBackendDbusSSOFake(window_id, appname, login_text)
            LOG.warn('Using fake login SSO functionality. Only meant for testing purposes')
        else:
            sso_class = LoginBackendDbusSSO(window_id, appname, login_text)
    return sso_class
   
if __name__ == "__main__":
    login = LoginBackendDbusSSO()
    login.login()

    gtk.main()
