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

class SimpleGladeDialog(object):
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

def confirm_remove(parent, datadir, primary, cache, button_text, icon_path, depends):
    """Confirm removing of the given app with the given depends"""
    glade_dialog = SimpleGladeDialog(datadir)
    dialog = glade_dialog.dialog_dependency_alert
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_default_size(360, -1)

    # fixes launchpad bug #560021
    pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(icon_path, 48, 48)
    glade_dialog.image_package_icon.set_from_pixbuf(pixbuf)

    glade_dialog.label_dependency_primary.set_text("<span font_weight=\"bold\" font_size=\"large\">%s</span>" % primary)
    glade_dialog.label_dependency_primary.set_use_markup(True)
    glade_dialog.button_dependency_do.set_label(button_text)

    # add the dependencies
    vbox = dialog.get_content_area()
    # FIXME: make this a generic pkgview widget
    view = PkgNamesView(_("Dependency"), cache, depends)
    view.set_headers_visible(False)
    glade_dialog.scrolledwindow_dependencies.add(view)
    glade_dialog.scrolledwindow_dependencies.show_all()
        
    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_ACCEPT:
        return True
    return False
    
def confirm_repair_broken_cache(parent, datadir):
    glade_dialog = SimpleGladeDialog(datadir)
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
    import apt
    cache = apt.Cache()
    
    confirm_remove(None, 
                   "./data", 
                   "To remove Package, these items must be removed as well",
                   cache,
                   "Remove", 
                   "./data/icons/48x48/apps/softwarecenter.png", 
                   depends=["apt"])
                   
    print "Running broken apt-cache dialog"               
    confirm_repair_broken_cache(None, "./data")
                   
    print "Showing message dialog"
    messagedialog(None, primary="first, no second")
    print "showing error"
    error(None, "first", "second")
    error(None, "first", "second", "details ......")
     
