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

    def is_installed(self, pkgname):
        pass
    def is_available(self, pkgname):
        pass
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
