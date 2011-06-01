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
        self.name = name
        self.pkginfo = pkginfo

    @property
    def installed(self):
        if not self.pkginfo.is_installed(self.name):
            return None
        return self.pkginfo.get_installed(self.name)
    @property
    def candidate(self):
        return self.pkginfo.get_candidate(self.name)
    @property
    def versions(self):
        """ a list of available versions to install """
        return self.pkginfo.get_versions(self.name)

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
    def website(self):
        return self.pkginfo.get_website(self.name)
    @property
    def installed_files(self):
        return self.pkginfo.get_installed_files(self.name)
    @property
    def size(self):
        return self.pkginfo.get_size(self.name)
    @property
    def installed_size(self):
        return self.pkginfo.get_installed_size(self.name)
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

    @staticmethod
    def version_compare(v1, v2):
        """ compare two versions """
        return cmp(v1, v2)
    @staticmethod
    def upstream_version_compare(v1, v2):
        """ compare two versions, but ignore the distro specific revisions """
        return cmp(v1, v2)
    @staticmethod
    def upstream_version(v):
        """ Return the "upstream" version number of the given version """
        return v

    def is_installed(self, pkgname):
        pass
    def is_available(self, pkgname):
        pass
    def get_installed(self, pkgname):
        pass
    def get_candidate(self, pkgname):
        pass
    def get_versions(self, pkgname):
        return []

    def get_section(self, pkgname):
        pass
    def get_summary(self, pkgname):
        pass
    def get_description(self, pkgname):
        pass
    def get_website(self, pkgname):
        pass
    def get_installed_files(self, pkgname):
        return []
    def get_size(self, pkgname):
        return -1
    def get_installed_size(self, pkgname):
        return -1
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
