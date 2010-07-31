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

    def __init__(self, loginbackend, datadir, parent=None):
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

        # create spinner
        #self.login_spinner = gtk.Spinner()
        #self.dialog_action_area_login.pack_start(self.login_spinner)
        #self.dialog_action_area_login.reorder_child(self.login_spinner, 0)
        #self.login_spinner.start()
        #self.login_spinner.show()

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



if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)
    # glaunchpad
    if sys.argv[1] == "launchpad":
        loginbackend = GLaunchpad()
    elif sys.argv[1] == "sso":
        loginbackend = UbuntuSSOlogin()
    else:
        print "need either 'sso' or 'launchpad' as arguments"
    d = LoginDialog(loginbackend, datadir="./data")
    res = d.login()

    try:
        gtk.main()
    except KeyboardInterrupt:
        # FIXME: port shutdown?!?
        #glaunchpad.shutdown() 
        pass




