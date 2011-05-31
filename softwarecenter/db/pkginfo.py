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

import gobject

class _Package:
    def __init__(self, name, pkginfo):
        self.name, self.pkginfo = name, pkginfo
    @property
    def installed(self):
        if not self.pkginfo.is_installed(self.name):
            return None
        return self.pkginfo.get_installed(self.name)
    @property
    def candidate(self):
        return self.pkginfo.get_candidate(self.name)
    @property
    def available(self):
        """ a list of available versions to install """
        return self.pkginfo.get_available(self.name)

    @property
    def is_installed(self):
        return self.pkginfo.is_installed(self.name)
    @property
    def section(self):
        return self.pkginfo.get_section(self.name)
    @property
    def summary(self):
        return self.pkginfo.get_summary(self.name)
    @property
    def description(self):
        return self.pkginfo.get_description(self.name)
    @property
    def origins(self):
        return self.pkginfo.get_origins(self.name)

class PackageInfo(gobject.GObject):
    """ abstract interface for the packageinfo information """

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

    def __getitem__(self, k):
        return _Package(k, self)
    def __contains__(self, pkgname):
        return False

    def is_installed(self, pkgname):
        pass
    def is_available(self, pkgname):
        pass
    def get_installed(self, pkgname):
        pass
    def get_candidate(self, pkgname):
        pass
    def get_available(self, pkgname):
        return []

    def get_section(self, pkgname):
        pass
    def get_summary(self, pkgname):
        pass
    def get_description(self, pkgname):
        pass
    def get_origins(self, pkgname):
        return []
    def get_addons(self, pkgname, ignore_installed):
        pass
    def open(self):
        """ 
        (re)open the cache, this sends cache-invalid, cache-ready signals
        """
        pass
    @property
    def ready(self):
        pass

# singleton
pkginfo = None
def get_pkg_info():
    global pkginfo
    if pkginfo is None:
        from softwarecenter.db.pkginfo_impl.aptcache import AptCache
        pkginfo = AptCache()
    return pkginfo
