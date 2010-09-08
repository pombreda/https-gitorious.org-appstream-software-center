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

import gtk
from gettext import gettext as _

from pkgview import PkgNamesView
from dialogs import SimpleGtkbuilderDialog

from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro
from softwarecenter.enums import MISSING_APP_ICON

from aptdaemon.defer import inline_callbacks

def confirm_install(parent, datadir, app, db, icons):
    """Confirm install of the given app
       
       (currently only shows a dialog if a installed app needs to be removed
        in order to install the application)
    """
    cache = db._aptcache
    distro = get_distro()
    appdetails = app.get_details(db)
    # FIXME: use 
    depends = set()
    deps_remove = cache.try_install_and_get_all_deps_removed(appdetails.pkg)
    for depname in deps_remove:
        if cache[depname].is_installed:
            depends.add(depname)
    (primary, button_text) = distro.get_install_warning_text(cache, appdetails.pkg, app.name, depends)
    return _confirm_remove_internal(parent, datadir, app, db, icons, primary, button_text, depends, cache)

def confirm_remove(parent, datadir, app, db, icons):
    """ Confirm removing of the given app """
    cache = db._aptcache
    distro = get_distro()
    appdetails = app.get_details(db)
    # FIXME: use 
    #  backend = get_install_backend()
    #  backend.simulate_remove(app.pkgname)
    # once it works
    depends = db._aptcache.get_installed_rdepends(appdetails.pkg)
    (primary, button_text) = distro.get_removal_warning_text(
        db._aptcache, appdetails.pkg, app.name, depends)
    return _confirm_remove_internal(parent, datadir, app, db, icons, primary, button_text, depends, cache)

def _confirm_remove_internal(parent, datadir, app, db, icons, primary, button_text, depends, cache):
    glade_dialog = SimpleGtkbuilderDialog(datadir)
    dialog = glade_dialog.dialog_dependency_alert
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_default_size(360, -1)

    # get icon for the app
    appdetails = app.get_details(db)
    icon_name = appdetails.icon
    if not icons.has_icon(icon_name):
        icon_name = MISSING_APP_ICON
    glade_dialog.image_package_icon.set_from_icon_name(icon_name, 
                                                       gtk.ICON_SIZE_DIALOG)

    # set the texts
    glade_dialog.label_dependency_primary.set_text("<span font_weight=\"bold\" font_size=\"large\">%s</span>" % primary)
    glade_dialog.label_dependency_primary.set_use_markup(True)
    glade_dialog.button_dependency_do.set_label(button_text)

    # add the dependencies
    vbox = dialog.get_content_area()
    # FIXME: make this a generic pkgview widget
    view = PkgNamesView(_("Dependency"), cache, depends, icons, db)
    view.set_headers_visible(False)
    # FIXME: work out how not to select?/focus?/activate? first item
    glade_dialog.scrolledwindow_dependencies.add(view)
    glade_dialog.scrolledwindow_dependencies.show_all()
        
    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_ACCEPT:
        return True
    return False


if __name__ == "__main__":
    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()

    from softwarecenter.db.database import StoreDatabase, Application
    pathname = "/var/cache/software-center/xapian"
    db = StoreDatabase(pathname, cache)
    db.open()

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    confirm_install(None, 
                   "./data", 
                   Application("", "gourmet"),
                   db,
                   icons)

    confirm_remove(None, 
                   "./data", 
                   Application("", "p7zip-full"),
                   db,
                   icons)

