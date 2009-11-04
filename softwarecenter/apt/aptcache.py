# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# Parts taken from gnome-app-install:utils.py (also written by Michael Vogt)
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
import apt_pkg
import datetime
import locale
import gettext
import glib
import gobject
import gtk
import os
import subprocess
import time

from gettext import gettext as _

class GtkMainIterationProgress(apt.progress.OpProgress):
    """Progress that just runs the main loop"""
    def update(self, percent):
        while gtk.events_pending():
            gtk.main_iteration()

class AptCache(gobject.GObject):
    """ 
    A apt cache that opens in the background and keeps the UI alive
    """

    # dependency types we are about
    DEPENDENCY_TYPES = ("PreDepends", "Depends")
    RECOMMENDS_TYPES = ("Recommends")

    __gsignals__ = {'cache-ready':  (gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    'cache-invalid':(gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    }

    def __init__(self):
        gobject.GObject.__init__(self)
        self._cache = None
        self._ready = False
        glib.timeout_add(100, self.open)
    @property
    def ready(self):
        return self._ready
    def open(self):
        self._ready = False
        self.emit("cache-invalid")
        if self._cache == None:
            self._cache = apt.Cache(GtkMainIterationProgress())
        else:
            self._cache.open(GtkMainIterationProgress())
        self._ready = True
        self.emit("cache-ready")
    def __getitem__(self, key):
        return self._cache[key]
    def __iter__(self):
        return self._cache.__iter__()
    def __contains__(self, k):
        return self.cache.__contains__(k)
    def has_key(self, key):
        return self._cache.has_key(key)
    def _get_installed_rdepends_by_type(self, pkg, type):
        installed_rdeps = set()
        for rdep in pkg._pkg.RevDependsList:
            if rdep.DepType in self.DEPENDENCY_TYPES:
                rdep_name = rdep.ParentPkg.Name
                if (self._cache.has_key(rdep_name) and
                    self._cache[rdep_name].isInstalled):
                    installed_rdeps.add(rdep.ParentPkg.Name)
        return installed_rdeps
    def get_installed_rdepends(self, pkg):
        return self._get_installed_rdepends_by_type(pkg, self.DEPENDENCY_TYPES)
    def get_installed_rrecommends(self, pkg):
        return self._get_installed_rdepends_by_type(pkg, self.RECOMMENDS_TYPES)

if __name__ == "__main__":
    c = AptCache()
    c.open()
    print c.get_maintenance_status("synaptic app", "synaptic", "main", None)
    print c.get_maintenance_status("3dchess app", "3dchess", "universe", None)
