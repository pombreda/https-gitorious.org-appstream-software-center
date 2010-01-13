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

# FIXME: fix in python-apt API
def apt_i18n(s):
    return gettext.dgettext("libapt-pkg4.8", s)

class AptCache(gobject.GObject):
    """ 
    A apt cache that opens in the background and keeps the UI alive
    """

    # dependency types we are about
    DEPENDENCY_TYPES = (apt_i18n("PreDepends"), apt_i18n("Depends"))
    RECOMMENDS_TYPES = (apt_i18n("Recommends"),)
    SUGGESTS_TYPES = (apt_i18n("Suggests"),)

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
            if rdep.DepType in type:
                rdep_name = rdep.ParentPkg.Name
                if (self._cache.has_key(rdep_name) and
                    self._cache[rdep_name].isInstalled):
                    installed_rdeps.add(rdep.ParentPkg.Name)
        return installed_rdeps
    def _installed_dependencies(self, pkg_name, all_deps=None):
        """ recursively return all installed dependencies of a given pkg """
        #print "_installed_dependencies", pkg_name, all_deps
        if not all_deps:
            all_deps = set()
        if not self._cache.has_key(pkg_name):
            return all_deps
        cur = self._cache[pkg_name]._pkg.CurrentVer
        if not cur:
            return all_deps
        for t in self.DEPENDENCY_TYPES+self.RECOMMENDS_TYPES:
            try:
                for dep in cur.DependsList[t]:
                    dep_name = dep[0].TargetPkg.Name
                    if not dep_name in all_deps:
                        all_deps.add(dep_name)
                        all_deps |= self._installed_dependencies(dep_name, all_deps)
            except KeyError:
                pass
        return all_deps
    def get_installed_automatic_depends_for_pkg(self, pkg):
        """ Get the installed automatic dependencies for this given package
            only.

            Note that the package must be marked for removal already for
            this to work
        """
        installed_auto_deps = set()
        deps = self._installed_dependencies(pkg.name)
        for dep_name in deps:
            if self._cache.has_key(dep_name):
                pkg = self._cache[dep_name]
                if (pkg.isInstalled and 
                    pkg.isAutoRemovable):
                    installed_auto_deps.add(dep_name)
        return installed_auto_deps
    def get_installed_rdepends(self, pkg):
        return self._get_installed_rdepends_by_type(pkg, self.DEPENDENCY_TYPES)
    def get_installed_rrecommends(self, pkg):
        return self._get_installed_rdepends_by_type(pkg, self.RECOMMENDS_TYPES)
    def get_installed_rsuggests(self, pkg):
        return self._get_installed_rdepends_by_type(pkg, self.SUGGESTS_TYPES)

if __name__ == "__main__":
    c = AptCache()
    c.open()
    print "deps of unrar"
    print c._installed_dependencies(c["unrar"].name)

    print "unused deps of 4g8"
    pkg = c["4g8"]
    pkg.markDelete()
    print c.get_installed_automatic_depends_for_pkg(pkg)

    pkg = c["unace"]
    print c.get_installed_automatic_depends_for_pkg(pkg)
    print c.get_installed_rdepends(pkg)
    print c.get_installed_rrecommends(pkg)
    print c.get_installed_rsuggests(pkg)
