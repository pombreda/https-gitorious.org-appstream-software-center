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

class InstallBackend(object):
    def upgrade(self, pkgname, appname, iconname, addons_install=[], addons_remove=[], metadata=None):
        pass
    def remove(self, pkgname, appname, iconname, addons_install=[], addons_remove=[], metadata=None):
        pass
    def remove_multiple(self, pkgnames, appnames, iconnames, addons_install=[], addons_remove=[], metadatas=None):
        pass
    def install(self, pkgname, appname, iconname, filename=None, addons_install=[], addons_remove=[], metadata=None):
        pass
    def install_multiple(self, pkgnames, appnames, iconnames, addons_install=[], addons_remove=[], metadatas=None):
        pass
    def apply_changes(self, pkgname, appname, iconname, addons_install=[], addons_remove=[], metadata=None):
        pass
    def reload(self, sources_list=None, metadata=None):
        """ reload package list """
        pass

# singleton
install_backend = None
def get_install_backend():
    global install_backend
    if install_backend is None:
        from softwarecenter.backend.aptd import AptdaemonBackend
        install_backend = AptdaemonBackend()
    return install_backend

        
