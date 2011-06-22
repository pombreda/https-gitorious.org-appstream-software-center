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
import random
import string
import os

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

from login import LoginBackend

# mostly for testing
from fake_review_settings import FakeReviewSettings, network_delay

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
        super(LoginBackendDbusSSOFake, self).__init__()
        self.appname = appname
        self.login_text = login_text
        self._window_id = window_id
        self._fake_settings = FakeReviewSettings()
    
    @network_delay
    def login(self, username=None, password=None):
        response = self._fake_settings.get_setting('login_response')
            
        if response == "successful":
            self.emit("login-successful", self._return_credentials())
        elif response == "failed":
            self.emit("login-failed")
        elif response == "denied":
            self.cancel_login()
        
        return
    
    def login_or_register(self):
        #fake functionality for this is no different to fake login()
        self.login()
        return
                
    def _random_unicode_string(self, length):
        retval = ''
        for i in range(0,length):
            retval = retval + random.choice(string.letters + string.digits)
        return retval.decode('utf-8')
 
    def _return_credentials(self):
        c =  dbus.Dictionary(
            {
              dbus.String(u'consumer_secret'): dbus.String(self._random_unicode_string(30)),
              dbus.String(u'token') : dbus.String(self._random_unicode_string(50)),
              dbus.String(u'consumer_key') : dbus.String(self._random_unicode_string(7)),
              dbus.String(u'name') : dbus.String('Ubuntu Software Center @ ' + self._random_unicode_string(6)),
              dbus.String(u'token_secret') : dbus.String(self._random_unicode_string(50))
             }, 
             signature=dbus.Signature('ss')
             )
        return c

def get_sso_backend(window_id, appname, login_text):
    """ 
    factory that returns an sso loader singelton
    """
    if "SOFTWARE_CENTER_FAKE_REVIEW_API" in os.environ:
        sso_class = LoginBackendDbusSSOFake(window_id, appname, login_text)
        LOG.warn('Using fake login SSO functionality. Only meant for testing purposes')
    else:
        sso_class = LoginBackendDbusSSO(window_id, appname, login_text)
    return sso_class
   
if __name__ == "__main__":
    login = get_sso_backend()
    login.login()

    gtk.main()
