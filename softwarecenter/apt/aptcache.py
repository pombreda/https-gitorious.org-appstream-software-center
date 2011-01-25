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
import logging
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
from softwarecenter.utils import ExecutionTime

LOG = logging.getLogger(__name__)

class GtkMainIterationProgress(apt.progress.base.OpProgress):
    """Progress that just runs the main loop"""
    def update(self, percent=0):
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

    LANGPACK_PKGDEPENDS = "/usr/share/language-selector/data/pkg_depends"

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
        # FIXME: measure if idle_add() or timeout_add(100, self.open)
        #        make a difference on slow hardware
        glib.idle_add(self.open)
        # setup monitor watch for install/remove changes
        self.apt_finished_stamp=gio.File(self.APT_FINISHED_STAMP)
        self.apt_finished_monitor = self.apt_finished_stamp.monitor_file(
            gio.FILE_MONITOR_NONE)
        self.apt_finished_monitor.connect(
            "changed", self._on_apt_finished_stamp_changed)
        # this is fast, so ok
        self._language_packages = self._read_language_pkgs()
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
        """ (re)open the cache, this sends cache-invalid, cache-ready signals
        """
        self._ready = False
        self.emit("cache-invalid")
        with ExecutionTime("open the apt cache (in event loop)"):
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

    # FIXME: there are cleaner ways to do this than below

    # pkg relations
    def get_depends(self, pkg):
        return self._get_depends_by_type_str(pkg, self.DEPENDENCY_TYPES)
    def get_recommends(self, pkg):
        return self._get_depends_by_type_str(pkg, self.RECOMMENDS_TYPES)
    def get_suggests(self, pkg):
        return self._get_depends_by_type_str(pkg, self.SUGGESTS_TYPES)
    def get_enhances(self, pkg):
        return self._get_depends_by_type_str(pkg, self.ENHANCES_TYPES)
    def get_provides(self, pkg):
        provides_list = pkg.candidate._cand.provides_list
        provides = []
        for provided in provides_list:
            provides.append(provided[0]) # the package name
        return provides

    # reverse pkg relations
    def get_rdepends(self, pkg):
        return self._get_rdepends_by_type(pkg, self.DEPENDENCY_TYPES, False)
    def get_rrecommends(self, pkg):
        return self._get_rdepends_by_type(pkg, self.RECOMMENDS_TYPES, False)
    def get_rsuggests(self, pkg):
        return self._get_rdepends_by_type(pkg, self.SUGGESTS_TYPES, False)
    def get_renhances(self, pkg):
        return self._get_rdepends_by_type(pkg, self.ENHANCES_TYPES, False)
    def get_renhances_lowlevel_apt_pkg(self, pkg):
        """ takes a apt_pkg.Package and returns a list of pkgnames that 
            enhance this package - this is needed to support enhances
            for virtual packages
        """
        renhances = []
        for dep in pkg.rev_depends_list:
            if dep.dep_type_untranslated == "Enhances":
                renhances.append(dep.parent_pkg.name)
        return renhances
    def get_rprovides(self, pkg):
        return self._get_rdepends_by_type(pkg, self.PROVIDES_TYPES, False)

    # installed reverse pkg relations
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

    # language pack stuff
    def _is_language_pkg(self, addon):
        # a simple "addon in self._language_packages" is not enough
        for template in self._language_packages:
            if addon.startswith(template):
                return True
        return False
    def _read_language_pkgs(self):
        language_packages = set()
        if not os.path.exists(self.LANGPACK_PKGDEPENDS):
            return language_packages
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
        
    # these are used for calculating the total size
    def _get_changes_without_applying(self, pkg):
        try:
            if pkg.installed == None:
                pkg.mark_install()
            else:
                pkg.mark_delete()
        except SystemError:
            # TODO: ideally we now want to display an error message
            #       and block the install button
            LOG.warning("broken packages encountered while getting deps for %s"
                      % pkg.name)
            return {}
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
    def try_install_and_get_all_deps_installed(self, pkg):
        """ Return all dependencies of pkg that will be marked for install """
        changes = self._get_changes_without_applying(pkg)
        installing_deps = []
        for change in changes.keys():
            if change != pkg.name and changes[change] == PKG_STATE_INSTALLING:
                installing_deps.append(change)
        return installing_deps
    def try_install_and_get_all_deps_removed(self, pkg):
        """ Return all dependencies of pkg that will be marked for remove"""
        changes = self._get_changes_without_applying(pkg)
        removing_deps = []
        for change in changes.keys():
            if change != pkg.name and changes[change] == PKG_STATE_REMOVING:
                removing_deps.append(change)
        return removing_deps
    def get_all_deps_upgrading(self, pkg):
        changes = self._get_changes_without_applying(pkg)
        upgrading_deps = []
        for change in changes.keys():
            if change != pkg.name and changes[change] == PKG_STATE_UPGRADING:
                upgrading_deps.append(change)
        return upgrading_deps

    # determine the addons for a given package
    def get_addons(self, pkgname, ignore_installed=True):
        """ get the list of addons for the given pkgname

            The optional parameter "ignore_installed" controls if the output
            should be filtered and pkgs already installed should be ignored
            in the output (e.g. useful for testing).

            :return: a tuple of pkgnames (recommends, suggests)
        """
        logging.debug("get_addons for '%s'" % pkgname)
        def _addons_filter(addon):
            """ helper for get_addons that filters out unneeded ones """
            # we don't know about this one (prefectly legal for suggests)
            if not addon in self._cache:
                LOG.debug("not in cache %s" % addon)
                return False
            # can happen via "lonley" depends
            if addon == pkg.name:
                LOG.debug("circular %s" % addon)
                return False
            # child pkg is addon of parent pkg, not the other way around.
            if addon == '-'.join(pkgname.split('-')[:-1]):
                LOG.debug("child > parent %s" % addon)
                return False
            # get the pkg
            addon_pkg = self._cache[addon]
            # we don't care for essential or important (or refrences
            # to ourself)
            if (addon_pkg.essential or
                addon_pkg._pkg.important):
                LOG.debug("essential or important %s" % addon)
                return False
            # we have it in our dependencies already
            if addon in deps:
                LOG.debug("already a dependency %s" % addon)
                return False
            # its a language-pack, language-selector should deal with it
            if self._is_language_pkg(addon):
                LOG.debug("part of language pkg rdepends %s" % addon)
                return False
            # something on the system depends on it
            rdeps = self.get_installed_rdepends(addon_pkg)
            if rdeps and ignore_installed:
                LOG.debug("already has a installed rdepends %s" % addon)
                return False
            # looks good
            return True
        #----------------------------------------------------------------
        def _addons_filter_slow(addon):
            """ helper for get_addons that filters out unneeded ones """
            # this addon would get installed anyway (e.g. via indirect
            # dependency) so it would be misleading to show it
            if addon in all_deps_if_installed:
                LOG.debug("would get installed automatically %s" % addon)
                return False
            return True
        #----------------------------------------------------------------
        # deb file, or pkg needing source, etc
        if (not pkgname in self._cache or
            not self._cache[pkgname].candidate):
            return ([],[])

        # initial setup
        pkg = self._cache[pkgname]

        # recommended addons
        addons_rec = self.get_recommends(pkg)
        LOG.debug("recommends: %s" % addons_rec)
        # suggested addons and renhances
        addons_sug = self.get_suggests(pkg)
        LOG.debug("suggests: %s" % addons_sug)
        renhances = self.get_renhances(pkg)
        LOG.debug("renhances: %s" % renhances)
        addons_sug += renhances
        provides = self.get_provides(pkg)
        LOG.debug("provides: %s" % provides)
        for provide in provides:
            virtual_aptpkg_pkg = self._cache._cache[provide]
            renhances = self.get_renhances_lowlevel_apt_pkg(virtual_aptpkg_pkg)
            LOG.debug("renhances of %s: %s" % (provide, renhances))
            addons_sug += renhances

        # get more addons, the idea is that if a package foo-data
        # just depends on foo we want to get the info about
        # "recommends, suggests, enhances" for foo-data as well
        # 
        # FIXME: find a good package where this is actually the case and
        #        replace the existing test 
        #        (arduino-core -> avrdude -> avrdude-doc) with that
        # FIXME2: if it turns out we don't have good/better examples,
        #         kill it
        deps = self.get_depends(pkg)
        for dep in deps:
            if dep in self._cache:
                pkgdep = self._cache[dep]
                if len(self.get_rdepends(pkgdep)) == 1:
                    # pkg is the only known package that depends on pkgdep
                    pkgdep_rec =  self.get_recommends(pkgdep)
                    LOG.debug("recommends from lonley dependency %s: %s" % (
                            pkgdep, pkgdep_rec))
                    addons_rec += pkgdep_rec
                    pkgdep_sug =  self.get_suggests(pkgdep)
                    LOG.debug("suggests from lonley dependency %s: %s" % (
                            pkgdep, pkgdep_sug))
                    addons_sug += pkgdep_sug
                    pkgdep_enh = self.get_renhances(pkgdep)
                    LOG.debug("renhances from lonley dependency %s: %s" % (
                            pkgdep, pkgdep_enh))
                    addons_sug += pkgdep_enh

        # remove duplicates from suggests (sets are great!)
        addons_sug = list(set(addons_sug)-set(addons_rec))

        # filter out stuff we don't want
        addons_rec = filter(_addons_filter, addons_rec)
        addons_sug = filter(_addons_filter, addons_sug)

        # this is not integrated into the filter above, as it is quite expensive
        # to run this call, so we only run it if we actually have addons
        if addons_rec or addons_sug:
            # now get all_deps if the package would be installed
            try:
                all_deps_if_installed = self.try_install_and_get_all_deps_installed(pkg)
            except:
                # if we have broken packages, then we return no addons
                LOG.warn("broken packages encountered while getting deps for %s" % pkgname)
                return ([],[])
            # filter out stuff we don't want
            addons_rec = filter(_addons_filter_slow, addons_rec)
            addons_sug = filter(_addons_filter_slow, addons_sug)
        
        return (addons_rec, addons_sug)

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
