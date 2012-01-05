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

import os

from gi.repository import GObject
from oauth.oauth import OAuthToken

import logging

import softwarecenter.paths
from softwarecenter.paths import PistonHelpers, SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.enums import SSO_LOGIN_HOST

# mostly for testing
from fake_review_settings import FakeReviewSettings, network_delay
from spawn_helper import SpawnHelper
from login import LoginBackend

LOG = logging.getLogger(__name__)

class UbuntuSSOAPI(GObject.GObject):

    __gsignals__ = {
        "whoami" : (GObject.SIGNAL_RUN_LAST,
                    GObject.TYPE_NONE, 
                    (GObject.TYPE_PYOBJECT,),
                    ),
        "error" : (GObject.SIGNAL_RUN_LAST,
                    GObject.TYPE_NONE, 
                    (GObject.TYPE_PYOBJECT,),
                    ),

        }
       
    def __init__(self, token):
        GObject.GObject.__init__(self)
        binary = os.path.join(
            softwarecenter.paths.datadir, PistonHelpers.GENERIC_HELPER)
        self.HELPER_CMD = [binary, "--needs-auth"]
        # FIXME: the token is not currently used as the helper will 
        #        query the keyring again
        self.token = token
        
    def _on_whoami_data(self, spawner, piston_whoami):
        self.emit("whoami", piston_whoami)

    def whoami(self):
        LOG.debug("whoami called")
        cmd = self.HELPER_CMD[:] + ["whoami"]
        spawner = SpawnHelper()
        spawner.connect("data-available", self._on_whoami_data)
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.run(cmd)

class UbuntuSSOAPIFake(UbuntuSSOAPI):

    def __init__(self, token):
        GObject.GObject.__init__(self)
        self._fake_settings = FakeReviewSettings()

    @network_delay
    def whoami(self):
        if self._fake_settings.get_setting('whoami_response') == "whoami":
            self.emit("whoami", self._create_whoami_response())
        elif self._fake_settings.get_setting('whoami_response') == "error": 
            self.emit("error", self._make_error())
    
    def _create_whoami_response(self):
        username = self._fake_settings.get_setting('whoami_username') or "anyuser"
        response = {
                    u'username': username.decode('utf-8'), 
                    u'preferred_email': u'user@email.com', 
                    u'displayname': u'Fake User', 
                    u'unverified_emails': [], 
                    u'verified_emails': [], 
                    u'openid_identifier': u'fnerkWt'
                   }
        return response
    
    def _make_error():
        return 'HTTP Error 401: Unauthorized'

def get_ubuntu_sso_backend(token):
    """ 
    factory that returns an ubuntu sso loader singelton
    """
    if "SOFTWARE_CENTER_FAKE_REVIEW_API" in os.environ:
        ubuntu_sso_class = UbuntuSSOAPIFake(token)
        LOG.warn('Using fake Ubuntu SSO API. Only meant for testing purposes')
    else:
        ubuntu_sso_class = UbuntuSSOAPI(token)
    return ubuntu_sso_class


class UbuntuSSOlogin(LoginBackend):

    NEW_ACCOUNT_URL = "https://login.launchpad.net/+standalone-login"
    FORGOT_PASSWORD_URL = "https://login.ubuntu.com/+forgot_password"

    SSO_AUTHENTICATE_FUNC = "authentications.authenticate"

    def __init__(self):
        LoginBackend.__init__(self)
        self.service = UBUNTU_SSO_SERVICE
        # we get a dict here with the following keys:
        #  token
        #  consumer_key (also the openid identifier)
        #  consumer_secret
        #  token_secret
        #  name (that is just 'software-center')
        self.oauth_credentials = None
        self._oauth_credentials = None
        self._login_failure = None
        self.worker_thread = None

    def shutdown(self):
        self.worker_thread.shutdown()

    def login(self, username=None, password=None):
        if not username or not password:
            self.emit("need-username-password")
            return
        authorizer = BasicHttpAuthorizer(username, password)
        self.worker_thread =  RestfulClientWorker(authorizer, self.service)
        self.worker_thread.start()
        kwargs = { "token_name" : "software-center", 
                 }
        self.worker_thread.queue_request(self.SSO_AUTHENTICATE_FUNC, (), kwargs,
                                         self._thread_authentication_done,
                                         self._thread_authentication_error)
        GObject.timeout_add(200, self._monitor_thread)

    def _monitor_thread(self):
        # glib bit of the threading, runs in the main thread
        if self._oauth_credentials:
            self.emit("login-successful", self._oauth_credentials)
            self.oauth_credentials = self._oauth_credentials
            self._oauth_credentials = None
        if self._login_failure:
            self.emit("login-failed")
            self._login_failure = None
        return True

    def _thread_authentication_done(self, result):
        # runs in the thread context, can not touch gui or glib
        #print "_authentication_done", result
        self._oauth_credentials = result

    def _thread_authentication_error(self, e):
        # runs in the thread context, can not touch gui or glib
        #print "_authentication_error", type(e)
        self._login_failure = e

    def __del__(self):
        #print "del"
        if self.worker_thread:
            self.worker_thread.shutdown()


# test code
def _login_success(lp, token):
    print "success", lp, token
def _login_failed(lp):
    print "fail", lp
def _login_need_user_and_password(sso):
    import sys
    sys.stdout.write("user: ")
    sys.stdout.flush()
    user = sys.stdin.readline().strip()
    sys.stdout.write("pass: ")
    sys.stdout.flush()
    password = sys.stdin.readline().strip()
    sso.login(user, password)

def _error(scaagent, errormsg):
    print "_error:", errormsg
def _whoami(sso, whoami):
    print "whoami: ", whoami

# interactive test code
if __name__ == "__main__":
    def _whoami(sso, result):
        print "res: ", result
        Gtk.main_quit()
    def _error(sso, result):
        print "err: ", result
        Gtk.main_quit()

    from gi.repository import Gtk
    import sys
    logging.basicConfig(level=logging.DEBUG)
    softwarecenter.paths.datadir = "./data"

    if len(sys.argv) < 2:
        print "need an argument, one of: 'sso', 'ssologin'"
        sys.exit(1)

    elif sys.argv[1] == "sso":
        def _dbus_maybe_login_successful(ssologin, oauth_result):
            sso = UbuntuSSOAPI(oauth_result)
            sso.connect("whoami", _whoami)
            sso.connect("error", _error)
            sso.whoami()
            
        from login_sso import get_sso_backend
        backend = get_sso_backend("", "appname", "help_text")
        backend.connect("login-successful", _dbus_maybe_login_successful)
        backend.login_or_register()
        Gtk.main()

    elif sys.argv[1] == "ssologin":
        ssologin = UbuntuSSOlogin()
        ssologin.connect("login-successful", _login_success)
        ssologin.connect("login-failed", _login_failed)
        ssologin.connect("need-username-password", _login_need_user_and_password)
        ssologin.login()
        
    else:
        print "unknown option"
        sys.exit(1)


