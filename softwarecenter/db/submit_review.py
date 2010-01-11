# -*- coding: utf-8 -*-

# Copyright (C) 2009 Canonical
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
import sys
import gtk

from gettext import gettext as _
from launchpadlib.launchpad import Launchpad
from launchpadlib.credentials import RequestTokenAuthorizationEngine
from launchpadlib import uris
from urlparse import urljoin

import softwarecenter.view.dialogs

# FIXME: make this (much) more async 
class AuthorizeRequestTokenWithGUI(RequestTokenAuthorizationEngine):

    def input_username(self, cached_username, suggested_message):
        """Collect the Launchpad username from the end-user.

        :param cached_username: A username from a previous entry attempt,
        to be presented as the default.
        """
        print "input username"
        d = self.gtk_builder.get_object("dialog_review_login")
        res = d.run()
        d.hide()
        if res == gtk.RESPONSE_OK:
            entry = self.gtk_builder.get_object("entry_review_login_email")
            return entry.get_text()
        else:
            self.user_canceled = True
            return ""

    def input_password(self, suggested_message):
        """Collect the Launchpad password from the end-user."""
        print "Input password"
        # we rely on that input_username was run before and presented
        # the dialog already
        entry = self.gtk_builder.get_object("entry_review_login_password")
        return entry.get_text()

    def input_access_level(self, available_levels, suggested_message,
                           only_one_option=None):
        """Collect the desired level of access from the end-user."""
        return "WRITE_PUBLIC"

    def _gtk_builder_init(self, datadir="./data", domain="software-center"):
        self.gtk_builder = gtk.Builder()
        self.gtk_builder.set_translation_domain(domain)
        self.gtk_builder.add_from_file(datadir+"/ui/reviews.ui")
        self.gtk_builder.connect_signals(self)
        for o in self.gtk_builder.get_objects():
            if issubclass(type(o), gtk.Buildable):
                name = gtk.Buildable.get_name(o)
                setattr(self, name, o)

    def startup(self, suggested_messages):
        # construct gtkbuilder stuff on statup
        self.user_canceled = False
        self._gtk_builder_init()

    def authentication_failure(self, suggested_message):
        """The user entered invalid credentials."""
        # do not show anything if the user canceled
        if self.user_canceled:
            return
        # show error
        softwarecenter.view.dialogs.error(self.dialog_review_login,
                                          _("Authentication failure"),
                                          _("I can not login with the "
                                            "the given credentials. "
                                            "Please try again."))
    # none of the below is needed
    def output(self, message):
        print self.text_wrapper.fill(message)

    def user_refused_to_authorize(self, suggested_message):
        """The user refused to authorize a request token."""
        self.output(suggested_message)
        self.output("\n")

    def user_authorized(self, access_level, suggested_message):
        """The user authorized a request token with some access level."""
        self.output(suggested_message)
        self.output("\n")

    def server_consumer_differs_from_client_consumer(
        self, client_name, real_name, suggested_message):
        """The client seems to be lying or mistaken about its name.

        When requesting a request token, the client told Launchpad
        that its consumer name was "foo". Now the client is telling the
        end-user that its name is "bar". Something is fishy and at the very
        least the end-user should be warned about this.
        """
        self.output("\n")
        self.output(suggested_message)
        self.output("\n")

    def success(self, suggested_message):
        """The token was successfully authorized."""
        self.output(suggested_message)
        
class ReviewApplicationOrPackage(object):
    """ review a given application or package """
    def __init__(self, launchpad, app, 
                 datadir="./data", domain="software-center"):
        self._launchpad = launchpad
        self.gtk_builder = gtk.Builder()
        self.gtk_builder.set_translation_domain(domain)
        self.gtk_builder.add_from_file(datadir+"/ui/reviews.ui")
        self.gtk_builder.connect_signals(self)
        for o in self.gtk_builder.get_objects():
            if issubclass(type(o), gtk.Buildable):
                name = gtk.Buildable.get_name(o)
                setattr(self, name, o)

    def run(self):
        res = self.dialog_review_app.run()
        print res
        if res == gtk.RESPONSE_OK:
            print "ok"
            # get a test bug
            test_bug = self._launchpad.bugs[505983]
            print test_bug.title
            text_buffer = self.textview_review.get_buffer()
            text = text_buffer.get_text(text_buffer.get_start_iter(),
                                        text_buffer.get_end_iter())
            print text
            test_bug.description = text
            test_bug.lp_save()


if __name__ == "__main__":

    # use cachedir
    cachedir = os.path.expanduser("~/.cache/software-center")
    if not os.path.exists(cachedir):
        os.makedirs(cachedir)
        
    # login into LP with GUI
    launchpad = Launchpad.login_with(
        'software-center', 'edge', cachedir,
        allow_access_levels = ['WRITE_PUBLIC'],
        authorizer_class=AuthorizeRequestTokenWithGUI)
    
    # FIXME: provide a package
    review_app = ReviewApplicationOrPackage(launchpad, None)
    review_app.run()

