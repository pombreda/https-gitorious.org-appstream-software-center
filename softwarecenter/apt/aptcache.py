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
import gio
import glib
import gobject
import gtk
import os
import subprocess
import time

from gettext import gettext as _
from softwarecenter.enums import *

class GtkMainIterationProgress(apt.progress.base.OpProgress):
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
    RECOMMENDS_TYPES = ("Recommends",)
    SUGGESTS_TYPES = ("Suggests",)
    ENHANCES_TYPES = ("Enhances",)
    PROVIDES_TYPES = ("Provides",)

    # stamp file to monitor (provided by update-notifier via
    # APT::Update::Post-Invoke-Success)
    APT_FINISHED_STAMP = "/var/lib/update-notifier/dpkg-run-stamp"

    __gsignals__ = {'cache-ready':  (gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    'cache-invalid':(gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    'cache-broken':(gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    }

    def __init__(self):
        gobject.GObject.__init__(self)
        self._cache = None
        self._ready = False
        self._timeout_id = None
        # async open cache
        glib.timeout_add(10, self.open)
        # setup monitor watch for install/remove changes
        self.apt_finished_stamp=gio.File(self.APT_FINISHED_STAMP)
        self.apt_finished_monitor = self.apt_finished_stamp.monitor_file(
            gio.FILE_MONITOR_NONE)
        self.apt_finished_monitor.connect(
            "changed", self._on_apt_finished_stamp_changed)
    def _on_apt_finished_stamp_changed(self, monitor, afile, other_file, event):
        if not event == gio.FILE_MONITOR_EVENT_CHANGES_DONE_HINT:
            return 
        if self._timeout_id:
            glib.source_remove(self._timeout_id)
            self._timeout_id = None
        self._timeout_id = glib.timeout_add_seconds(10, self.open)
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
        if self._cache.broken_count > 0:
            self.emit("cache-broken")
    def __getitem__(self, key):
        return self._cache[key]
    def __iter__(self):
        return self._cache.__iter__()
    def __contains__(self, k):
        return self._cache.__contains__(k)
    def _get_rdepends_by_type(self, pkg, type, onlyInstalled):
        rdeps = set()
        for rdep in pkg._pkg.rev_depends_list:
            dep_type = rdep.dep_type_untranslated
            if dep_type in type:
                rdep_name = rdep.parent_pkg.name
                if rdep_name in self._cache and (not onlyInstalled or
                (onlyInstalled and self._cache[rdep_name].is_installed)):
                    rdeps.add(rdep.parent_pkg.name)
        return rdeps
    def _installed_dependencies(self, pkg_name, all_deps=None):
        """ recursively return all installed dependencies of a given pkg """
        #print "_installed_dependencies", pkg_name, all_deps
        if not all_deps:
            all_deps = set()
        if pkg_name not in self._cache:
            return all_deps
        cur = self._cache[pkg_name]._pkg.current_ver
        if not cur:
            return all_deps
        for t in self.DEPENDENCY_TYPES+self.RECOMMENDS_TYPES:
            try:
                for dep in cur.depends_list[t]:
                    dep_name = dep[0].target_pkg.name
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
            try:
                pkg = self._cache[dep_name]
            except KeyError:
                continue
            else:
                if (pkg.is_installed and 
                    pkg.is_auto_removable):
                    installed_auto_deps.add(dep_name)
        return installed_auto_deps
    def get_origins(self):
        """
        return a set of the current channel origins from the apt.Cache itself
        """
        origins = set()
        for pkg in self._cache:
            if not pkg.candidate:
                continue
            for item in pkg.candidate.origins:
                while gtk.events_pending():
                    gtk.main_iteration()
                if item.origin:
                    origins.add(item.origin)
        return origins
    def get_installed_rdepends(self, pkg):
        return self._get_rdepends_by_type(pkg, self.DEPENDENCY_TYPES, True)
    def get_installed_rrecommends(self, pkg):
        return self._get_rdepends_by_type(pkg, self.RECOMMENDS_TYPES, True)
    def get_installed_rsuggests(self, pkg):
        return self._get_rdepends_by_type(pkg, self.SUGGESTS_TYPES, True)
    def get_installed_renhances(self, pkg):
        return self._get_rdepends_by_type(pkg, self.ENHANCES_TYPES, True)
    def get_installed_rprovides(self, pkg):
        return self._get_rdepends_by_type(pkg, self.PROVIDES_TYPES, True)
    def component_available(self, distro_codename, component):
        """ check if the given component is enabled """
        # FIXME: test for more properties here?
        for it in self._cache._cache.file_list:
            if (it.component != "" and 
                it.component == component and
                it.archive != "" and 
                it.archive == distro_codename):
                return True
        return False
        
    def _get_depends_by_type(self, pkg, types):
        version = pkg.installed
        if version == None:
            version = max(pkg.versions)
        return version.get_dependencies(*types)
    def _get_depends_by_type_str(self, pkg, *types):
        def not_in_list(list, item):
            for i in list:
                if i == item:
                    return False
            return True
        deps = self._get_depends_by_type(pkg, *types)
        deps_str = []
        for dep in deps:
            for dep_ in dep.or_dependencies:
                if not_in_list(deps_str, dep_.name):
                    deps_str.append(dep_.name)
        return deps_str
    def get_depends(self, pkg):
        return self._get_depends_by_type_str(pkg, self.DEPENDENCY_TYPES)
    def get_recommends(self, pkg):
        return self._get_depends_by_type_str(pkg, self.RECOMMENDS_TYPES)
    def get_suggests(self, pkg):
        return self._get_depends_by_type_str(pkg, self.SUGGESTS_TYPES)
    def get_enhances(self, pkg):
        return self._get_depends_by_type_str(pkg, self.ENHANCES_TYPES)
    def get_provides(self, pkg):
        return self._get_depends_by_type_str(pkg, self.PROVIDES_TYPES)
        
    def get_rdepends(self, pkg):
        return self._get_rdepends_by_type(pkg, self.DEPENDENCY_TYPES, False)
    def get_rrecommends(self, pkg):
        return self._get_rdepends_by_type(pkg, self.RECOMMENDS_TYPES, False)
    def get_rsuggests(self, pkg):
        return self._get_rdepends_by_type(pkg, self.SUGGESTS_TYPES, False)
    def get_renhances(self, pkg):
        return self._get_rdepends_by_type(pkg, self.ENHANCES_TYPES, False)
    def get_rprovides(self, pkg):
        return self._get_rdepends_by_type(pkg, self.PROVIDES_TYPES, False)
        
    def _get_changes(self, pkg):
        if pkg.installed == None:
            pkg.mark_install()
        else:
            pkg.mark_delete()
        changes_tmp = self._cache.get_changes()
        changes = {}
        for change in changes_tmp:
            if change.marked_install or change.marked_reinstall:
                changes[change.name] = PKG_STATE_INSTALLING
            elif change.marked_delete:
                changes[change.name] = PKG_STATE_REMOVING
            elif change.marked_upgrade:
                changes[change.name] = PKG_STATE_UPGRADING
            else:
                changes[change.name] = PKG_STATE_UNKNOWN
        self._cache.clear()
        return changes
    def get_all_deps_installing(self, pkg):
        """ Return all dependencies of pkg that will be marked for install """
        changes = self._get_changes(pkg)
        installing_deps = []
        for change in changes.keys():
            if change != pkg.name and changes[change] == PKG_STATE_INSTALLING:
                installing_deps.append(change)
        return installing_deps
    def get_all_deps_removing(self, pkg):
        changes = self._get_changes(pkg)
        removing_deps = []
        for change in changes.keys():
            if change != pkg.name and changes[change] == PKG_STATE_REMOVING:
                removing_deps.append(change)
        return removing_deps
    def get_all_deps_upgrading(self, pkg):
        changes = self._get_changes(pkg)
        upgrading_deps = []
        for change in changes.keys():
            if change != pkg.name and changes[change] == PKG_STATE_UPGRADING:
                upgrading_deps.append(change)
        return upgrading_deps

class PackageAddonsManager(object):
    """ class that abstracts the addons handling """

    LANGPACK_PKGDEPENDS = "/usr/share/language-selector/data/pkg_depends"
    (RECOMMENDED, SUGGESTED) = range(2)
    
    def __init__(self, cache):
        self.cache = cache
        self._language_packages = self._read_language_pkgs()

    def _remove_important_or_langpack(self, addon_list):
        """ remove packages that are essential or important
            or langpacks
        """
        for addon in addon_list:
            try:
                pkg = self.cache[addon]
                if pkg.essential or pkg._pkg.important:
                    addon_list.remove(addon)
                    continue
                
                rdeps = self.cache.get_installed_rdepends(pkg)
                if (len(rdeps) > 0 or 
                    self._is_language_pkg(addon)):
                    addon_list.remove(addon)
                    continue
            except KeyError:
                addon_list.remove(addon)
    
    def _is_language_pkg(self, addon):
        # a simple "addon in self._language_packages" is not enough
        for template in self._language_packages:
            if addon.startswith(template):
                return True
        return False

    def _read_language_pkgs(self):
        language_packages = set()
        for line in open(self.LANGPACK_PKGDEPENDS):
            line = line.strip()
            if line.startswith('#'):
                continue
            try:
                (cat, code, dep_pkg, language_pkg) = line.split(':')
            except ValueError:
                continue
            language_packages.add(language_pkg)
        return language_packages
    
    def _addons_for_pkg(self, pkgname, type):
        pkg = self.cache[pkgname]
        deps = self.cache.get_depends(pkg)
        addons = []
        if type == self.RECOMMENDED:
            rrecommends = self.cache.get_rrecommends(pkg)
            if len(rrecommends) == 1:
                addons += rrecommends
        elif type == self.SUGGESTED:
            addons += self.cache.get_renhances(pkg)
        
        for dep in deps:
            try:
                pkgdep = self.cache[dep]
                if len(self.cache.get_rdepends(pkgdep)) == 1:
                    # pkg is the only known package that depends on pkgdep
                    if type == self.RECOMMENDED:
                        addons += self.cache.get_recommends(pkgdep)
                    elif type == self.SUGGESTED:
                        addons += self.cache.get_suggests(pkgdep)
                        addons += self.cache.get_renhances(pkgdep)
            except KeyError:
                pass # FIXME: should we handle that differently?
        self._remove_important_or_langpack(addons)
        for addon in addons:
            try:
                pkg_ = self.cache[addon]
            except KeyError:
                addons.remove(addon)
            else:
                can_remove = False
                for addon_ in addons:
                    try:
                        if addon in self.cache.get_provides(self.cache[addon_]) \
                        or addon in self.cache.get_depends(self.cache[addon_]) \
                        or addon in self.cache.get_recommends(self.cache[addon_]):
                            can_remove = True
                            break
                    except KeyError:
                        addons.remove(addon_)
                        break
                if can_remove or not pkg_.candidate or addons.count(addon) > 1 \
                or addon == pkg.name or self._is_language_pkg(addon):
                    addons.remove(addon)
        # FIXME: figure out why I have to call this function two times to get rid of important packages
		self._remove_important_or_langpack(addons)
        return addons
    
    def recommended_addons(self, pkgname):
        return self._addons_for_pkg(pkgname, self.RECOMMENDED)
    
    def suggested_addons(self, pkgname):
        return self._addons_for_pkg(pkgname, self.SUGGESTED)
    

if __name__ == "__main__":
    c = AptCache()
    c.open()
    print "deps of unrar"
    print c._installed_dependencies(c["unrar"].name)

    print "unused deps of 4g8"
    pkg = c["4g8"]
    pkg.mark_delete()
    print c.get_installed_automatic_depends_for_pkg(pkg)

    pkg = c["unace"]
    print c.get_installed_automatic_depends_for_pkg(pkg)
    print c.get_installed_rdepends(pkg)
    print c.get_installed_rrecommends(pkg)
    print c.get_installed_rsuggests(pkg)
    
    print "deps of gimp"
    pkg = c["gimp"]
    print c.get_depends(pkg)
    print c.get_recommends(pkg)
    print c.get_suggests(pkg)
    print c.get_enhances(pkg)
    print c.get_provides(pkg)
    
    print "rdeps of gimp"
    print c.get_rdepends(pkg)
    print c.get_rrecommends(pkg)
    print c.get_rsuggests(pkg)
    print c.get_renhances(pkg)
    print c.get_rprovides(pkg)
