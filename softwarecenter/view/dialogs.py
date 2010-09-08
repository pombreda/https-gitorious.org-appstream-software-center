# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#  Andrew Higginson (rugby471)
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

from softwarecenter.distro import get_distro
from softwarecenter.enums import MISSING_APP_ICON

class SimpleGtkbuilderDialog(object):
    def __init__(self, datadir):
        # setup ui
        self.builder = gtk.Builder()
        self.builder.add_from_file(datadir+"/ui/dialogs.ui")
        self.builder.connect_signals(self)
        for o in self.builder.get_objects():
            if issubclass(type(o), gtk.Buildable):
                name = gtk.Buildable.get_name(o)
                setattr(self, name, o)
            else:
                print >> sys.stderr, "WARNING: can not get name for '%s'" % o

def confirm_install(parent, datadir, app, db, icons):
    """Confirm install of the given app
       
       (currently only shows a dialog if a installed app needs to be removed
        in order to install the application)
    """
    cache = db._aptcache
    distro = get_distro()
    appdetails = app.get_details(db)
    (primary, button_text) = distro.get_install_warning_text(cache, appdetails.pkg, app.name)
    depends = []
    deps_remove = cache.get_all_deps_removing(appdetails.pkg)
    for dep in deps_remove:
        if cache[dep].installed != None:
            depends.append(dep)
    return _confirm_remove_internal(parent, datadir, app, db, icons, primary, button_text, depends)

def confirm_remove(parent, datadir, app, db, icons):
    """ Confirm removing of the given app """
    cache = db._aptcache
    distro = get_distro()
    appdetails = app.get_details(db)
    (primary, button_text) = distro.get_removal_warning_text(
        db._aptcache, appdetails.pkg, app.name)
    depends = db._aptcache.get_installed_rdepends(appdetails.pkg)
    return _confirm_remove_internal(parent, datadir, app, db, icons, primary, button_text, depends)

def _confirm_remove_internal(parent, datadir, app, db, icons, primary, button_text, depends):
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

def confirm_repair_broken_cache(parent, datadir):
    glade_dialog = SimpleGtkbuilderDialog(datadir)
    dialog = glade_dialog.dialog_broken_cache
    dialog.set_default_size(380, -1)
    dialog.set_transient_for(parent)

    result = dialog.run()
    dialog.destroy()
    if result == gtk.RESPONSE_ACCEPT:
        return True
    return False

class DetailsMessageDialog(gtk.MessageDialog):
    """Message dialog with optional details expander"""
    def __init__(self,
                 parent=None, 
                 title="", 
                 primary=None, 
                 secondary=None, 
                 details=None,
                 buttons=gtk.BUTTONS_OK, 
                 type=gtk.MESSAGE_INFO):
        gtk.MessageDialog.__init__(self, parent, 0, type, buttons, primary)
        self.set_title(title)
        if secondary:
            self.format_secondary_markup(secondary)
        if details:
            textview = gtk.TextView()
            textview.set_size_request(500, 300)
            textview.get_buffer().set_text(details)
            scroll = gtk.ScrolledWindow()
            scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            scroll.add(textview)
            expand = gtk.Expander(_("Details"))
            expand.add(scroll)
            expand.show_all()
            self.get_content_area().pack_start(expand)
        if parent:
            self.set_modal(True)
            self.set_property("skip-taskbar-hint", True)

def messagedialog(parent=None, 
                  title="", 
                  primary=None, 
                  secondary=None, 
                  details=None,
                  buttons=gtk.BUTTONS_OK, 
                  type=gtk.MESSAGE_INFO):
    """ run a dialog """
    dialog = DetailsMessageDialog(parent=parent, title=title,
                                  primary=primary, secondary=secondary,
                                  details=details, type=type, 
                                  buttons=buttons)
    result = dialog.run()
    dialog.destroy()
    return result

def error(parent, primary, secondary, details=None):
    """ show a untitled error dialog """
    return messagedialog(parent=parent,
                         primary=primary, 
                         secondary=secondary,
                         details=details,
                         type=gtk.MESSAGE_ERROR)


if __name__ == "__main__":
    print "Running remove dialog"
    
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
                   
    print "Running broken apt-cache dialog"               
    confirm_repair_broken_cache(None, "./data")
                   
    print "Showing message dialog"
    messagedialog(None, primary="first, no second")
    print "showing error"
    error(None, "first", "second")
    error(None, "first", "second", "details ......")
     
