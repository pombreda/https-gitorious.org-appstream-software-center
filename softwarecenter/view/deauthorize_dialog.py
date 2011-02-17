# Copyright (C) 2011 Canonical
#
# Authors:
#  Gary Lasker
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
import logging

from gettext import gettext as _

from dialogs import SimpleGtkbuilderDialog

from softwarecenter.db.application import Application
from softwarecenter.distro import get_distro
from softwarecenter.enums import MISSING_APP_ICON
from softwarecenter.view.widgets.packagenamesview import PackageNamesView

LOG = logging.getLogger(__name__)

#FIXME: These need to come from the main app
ICON_SIZE = 24

def deauthorize_my_computer(parent, datadir, db, icons):
    """ Display a dialog to deauthorize the current computer for purchases
    """
    cache = db._aptcache
    distro = get_distro()

    purchased_packages = set()
    purchased_packages.add('file-roller')
    purchased_packages.add('alarm-clock')
    purchased_packages.add('pitivi')
    purchased_packages.add('chromium-browser')
    purchased_packages.add('cheese')
    purchased_packages.add('aisleriot')

    account_name = "gary.lasker@canonical.com"
    (primary, button_text) = distro.get_deauthorize_text(account_name,
                                                         purchased_packages)
        
    # build the dialog
    glade_dialog = SimpleGtkbuilderDialog(datadir, domain="software-center")
    dialog = glade_dialog.dialog_deauthorize
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_default_size(360, -1)

    # use the icon for software-center in the dialog
    icon_name = "softwarecenter"
    if (icon_name is None or
        not icons.has_icon(icon_name)):
        icon_name = MISSING_APP_ICON
    glade_dialog.image_icon.set_from_icon_name(icon_name, 
                                               gtk.ICON_SIZE_DIALOG)

    # set the texts
    glade_dialog.label_deauthorize_primary.set_text("<span font_weight=\"bold\" font_size=\"large\">%s</span>" % primary)
    glade_dialog.label_deauthorize_primary.set_use_markup(True)
    glade_dialog.button_deauthorize_do.set_label(button_text)

    # add the packages to remove
    vbox = dialog.get_content_area()
    view = PackageNamesView(_("Deauthorize"), cache, purchased_packages, icons, ICON_SIZE, db)
    view.set_headers_visible(False)
    # FIXME: work out how not to select?/focus?/activate? first item
    glade_dialog.scrolledwindow_purchased_packages.add(view)
    glade_dialog.scrolledwindow_purchased_packages.show_all()
        
    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_ACCEPT:
        return True
    return False


if __name__ == "__main__":
    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()
    cache.open()

    from softwarecenter.db.database import StoreDatabase, Application
    pathname = "/var/cache/software-center/xapian"
    db = StoreDatabase(pathname, cache)
    db.open()

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    deauthorize_my_computer(None, 
                            "./data", 
                            db,
                            icons)

