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


from gi.repository import GObject

import logging
import os

import softwarecenter.paths
from softwarecenter.paths import PistonHelpers
from softwarecenter.backend.login_sso import get_sso_backend

# mostly for testing
from fake_review_settings import FakeReviewSettings, network_delay
from spawn_helper import SpawnHelper

from softwarecenter.enums import (SOFTWARE_CENTER_NAME_KEYRING,
                                  SOFTWARE_CENTER_SSO_DESCRIPTION,
                                  )
from softwarecenter.utils import clear_token_from_ubuntu_sso

from gettext import gettext as _

LOG = logging.getLogger(__name__)

class SSOLoginHelper(object):
    def __init__(self, xid=0):
        self.oauth = None
        self.xid = xid
        self.loop = GObject.MainLoop(GObject.main_context_default())
    
    def _login_successful(self, sso_backend, oauth_result):
        LOG.debug("_login_successful")
        self.oauth = oauth_result
        # FIXME: actually verify the token against ubuntu SSO
        self.loop.quit()

    def verify_token(self, token):
        LOG.debug("verify_token")
        def _whoami_done(sso, me):
            self._whoami = me
            self.loop.quit()
        self._whoami = None
        sso = UbuntuSSOAPI(token)
        sso.connect("whoami", _whoami_done)
        sso.connect("error", lambda sso, err: self.loop.quit())
        sso.whoami()
        self.loop.run()
        LOG.debug("verify_token finished")
        # check if the token is valid
        if self._whoami is None:
            return False
        else:
            return True

    def clear_token(self):
        clear_token_from_ubuntu_sso(SOFTWARE_CENTER_NAME_KEYRING)

    def get_oauth_token_sync(self):
        self.oauth = None
        sso = get_sso_backend(
            self.xid, 
            SOFTWARE_CENTER_NAME_KEYRING,
            _(SOFTWARE_CENTER_SSO_DESCRIPTION))
        sso.connect("login-successful", self._login_successful)
        sso.connect("login-failed", lambda s: self.loop.quit())
        sso.connect("login-canceled", lambda s: self.loop.quit())
        sso.login_or_register()
        self.loop.run()
        return self.oauth


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

    else:
        print "unknown option"
        sys.exit(1)


