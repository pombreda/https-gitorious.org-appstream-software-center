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

class SimpleGtkbuilderDialog(object):
    def __init__(self, datadir, domain):
        # setup ui
        self.builder = gtk.Builder()
        self.builder.set_translation_domain(domain)
        self.builder.add_from_file(datadir+"/ui/dialogs.ui")
        self.builder.connect_signals(self)
        for o in self.builder.get_objects():
            if issubclass(type(o), gtk.Buildable):
                name = gtk.Buildable.get_name(o)
                setattr(self, name, o)
            else:
                print >> sys.stderr, "WARNING: can not get name for '%s'" % o


def confirm_repair_broken_cache(parent, datadir):
    glade_dialog = SimpleGtkbuilderDialog(datadir, domain="software-center")
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
                  type=gtk.MESSAGE_INFO,
                  alternative_action=None):
    """ run a dialog """
    dialog = DetailsMessageDialog(parent=parent, title=title,
                                  primary=primary, secondary=secondary,
                                  details=details, type=type, 
                                  buttons=buttons)
    if alternative_action:
        dialog.add_button(alternative_action, gtk.RESPONSE_YES)
    result = dialog.run()
    dialog.destroy()
    return result

def error(parent, primary, secondary, details=None, alternative_action=None):
    """ show a untitled error dialog """
    return messagedialog(parent=parent,
                         primary=primary, 
                         secondary=secondary,
                         details=details,
                         type=gtk.MESSAGE_ERROR,
                         alternative_action=alternative_action)


class FullsizeScreenshotDialog(gtk.Dialog):

    def __init__(self, parent):
        gtk.Dialog.__init__(self,
                            '',
                            parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT))

        self.image = gtk.Image()
        self.vbox.pack_start(self.image)
        return

    def set_pixbuf(self, pb):
        self.image.set_from_pixbuf(pb)
        self.show_all()
        return


if __name__ == "__main__":
    print "Running remove dialog"
    
                   
    print "Running broken apt-cache dialog"               
    confirm_repair_broken_cache(None, "./data")
                   
    print "Showing message dialog"
    messagedialog(None, primary="first, no second")
    print "showing error"
    error(None, "first", "second")
    error(None, "first", "second", "details ......")
     
