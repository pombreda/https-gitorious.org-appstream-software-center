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

import apt
import dbus
import gettext
import gio
import glib
import gobject
import gtk
import logging
import os
import re
import socket
import string
import subprocess
import sys
import tempfile
import urllib
import xapian

from gettext import gettext as _

if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")

from softwarecenter.db.application import Application, AppDetails
from softwarecenter.enums import *
from softwarecenter.utils import *
from softwarecenter.version import *
from softwarecenter.db.database import StoreDatabase
from softwarecenter.backend import get_install_backend


class AppDetailsViewBase(object):

    def __init__(self, db, distro, icons, cache, history, datadir):
        self.db = db
        self.distro = distro
        self.icons = icons
        self.cache = cache
        self.cache.connect("cache-ready", self._on_cache_ready)
        self.history = history
        self.datadir = datadir
        self.app = None
        self.appdetails = None
        # aptdaemon
        self.backend = get_install_backend()
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped)
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)
    def _draw(self):
        """ draw the current app into the window, maybe the function
            you need to overwrite
        """
        pass
    # public API
    def init_app(self, app):
        """ init the given Application object """
        # FIXME: init_app should really go
        self.app = app
        self.appdetails = AppDetails(self.db, application=app)
    def show_app(self, app):
        """ show the given application """
        if app is None:
            return
        self.app = app
        self.appdetails = AppDetails(self.db, application=app)
        self._draw()
        self.emit("selected", self.app)
    # public interface
    def reload(self):
        self.backend.reload()
    def install(self):
        self.backend.install(self.app.pkgname, self.app.appname, self.appdetails.icon)
    def remove(self):
        # generic removal text
        # FIXME: this text is not accurate, we look at recommends as
        #        well as part of the rdepends, but those do not need to
        #        be removed, they just may be limited in functionatlity
        (primary, button_text) = self.distro.get_removal_warning_text(self.cache, self.pkg, self.app.name)

        # ask for confirmation if we have rdepends
        depends = self.cache.get_installed_rdepends(self.pkg)
        if depends:
            iconpath = self.get_icon_filename(self.appdetails.icon, self.APP_ICON_SIZE)
            
            if not dialogs.confirm_remove(None, primary, self.cache,
                                        button_text, iconpath, depends):
                self._set_action_button_sensitive(True)
                self.backend.emit("transaction-stopped")
                return
        self.backend.remove(self.app.pkgname, self.app.appname, self.appdetails.icon)
    def upgrade(self):
        self.backend.upgrade(self.app.pkgname, self.app.appname, self.appdetails.icon)
    # internal callbacks
    def _on_cache_ready(self, cache):
        logging.debug("on_cache_ready")
        self.show_app(self.app)

