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
import softwarecenter

# urls for login/forgotten passwords, launchpad for now, ubuntu SSO
# ones we have a API
# create new 
NEW_ACCOUNT_URL = "https://login.launchpad.net/+standalone-login"
#NEW_ACCOUNT_URL = "https://login.ubuntu.com/+new_account"
# forgotten PW 
FORGOT_PASSWORD_URL =  "https://login.launchpad.net/+standalone-login"
#FORGOT_PASSWORD_URL = "https://login.ubuntu.com/+forgot_password"

class LoginDialog(object):

    def __init__(self, glaunchpad, datadir, parent=None):
        # launchpad
        self.glaunchpad = glaunchpad
        self.glaunchpad.connect("need-username-password", 
                                self.cb_need_username_password)
        self.glaunchpad.connect("login-successful", self.cb_login_successful)
        self.glaunchpad.connect("login-failed", self.cb_login_failure)

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

    def cb_need_username_password(self, lp):
        res = self.dialog_login.run()
        self.dialog_login.hide()
        if res != gtk.RESPONSE_OK:
            self.on_button_cancel_clicked()
            return 
        self._enter_user_name_password_finished()

    def cb_login_successful(self, lp):
        """ callback when the login was successful """
        print "login_successful"

    def cb_login_failure(self, lp):
        """ callback when the login failed """
        softwarecenter.view.dialogs.error(self.parent,
                                          _("Authentication failure"),
                                          _("Sorry, please try again"))
        self.cb_need_username_password(None)

    def on_button_cancel_clicked(self, button=None):
        self.glaunchpad.cancel_login()
        self.glaunchpad.shutdown()
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
            self.glaunchpad.enter_username_password(username, password)
        elif new_account:
            #print "new_account"
            subprocess.call(["xdg-open", NEW_ACCOUNT_URL])
        elif forgotten_pw:
            #print "forgotten passowrd"
            subprocess.call(["xdg-open", FORGOT_PASSWORD_URL])



if __name__ == "__main__":
    def _cb_login_successful(lp):
        print "success"
    def _cb_login_failure(lp):        
        print "failure"

    logging.basicConfig(level=logging.DEBUG)
    # glaunchpad
    glaunchpad = GLaunchpad()
    # get dialog
    d = LoginDialog(glaunchpad, datadir="./data")

    # connect
    glaunchpad.connect_to_server()

    try:
        gtk.main()
    except KeyboardInterrupt:
        glaunchpad.shutdown()



