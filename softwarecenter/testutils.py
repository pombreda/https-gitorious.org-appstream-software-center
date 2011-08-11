# Copyright (C) 2011 Canonical
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

def get_test_gtk3_viewmanager():
    from gi.repository import Gtk
    from softwarecenter.ui.gtk3.session.viewmanager import (
        ViewManager, get_viewmanager)
    vm = get_viewmanager()
    if not vm:
        notebook = Gtk.Notebook()
        vm = ViewManager(notebook)
        vm.view_to_pane = {None : None}
    return vm

def get_test_db():
    from softwarecenter.db.database import StoreDatabase
    from softwarecenter.db.pkginfo import get_pkg_info
    import softwarecenter.paths
    cache = get_pkg_info()
    cache.open()
    db = StoreDatabase(softwarecenter.paths.XAPIAN_PATH, cache)
    db.open()
    return db

def get_test_gtk3_icon_cache():
    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    import softwarecenter.paths
    icons = get_sc_icon_theme(softwarecenter.paths.datadir)
    return icons

def get_test_pkg_info():
    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()
    return cache

def get_test_datadir():
    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    import softwarecenter.paths
    return softwarecenter.paths.datadir
