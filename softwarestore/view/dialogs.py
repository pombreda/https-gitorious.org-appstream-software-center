# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#  Andrew Higginson (rugby471)
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
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

def error(parent, primary, secondary):
    """ show a untitled error dialog """
    return messagedialog(parent=parent,
                         primary=primary, secondary=secondary,
                         dialogtype=gtk.MESSAGE_ERROR)

def messagedialog(parent, title="", primary=None, secondary=None, 
                      dialogbuttons=gtk.BUTTONS_OK, 
                      dialogtype=gtk.MESSAGE_INFO):
    """ run a dialog """
    dialog = gtk.MessageDialog(parent=None, flags=0, type=dialogtype, 
                               buttons=dialogbuttons, message_format=primary)
    dialog.set_title(title)
    if secondary:
        dialog.format_secondary_markup(secondary)
    result = dialog.run()
    dialog.hide()
    return result


def confirm_remove(parent, primary, secondary, cache, depends=[]):
    """Confirm removing of the given app with the given depends"""
    dialog = gtk.MessageDialog(parent=parent, flags=0, 
                               type=gtk.MESSAGE_QUESTION, 
                               message_format=primary)
    dialog.set_resizable(True)
    dialog.format_secondary_markup(secondary)
    dialog.add_button(_("Cancel"), gtk.RESPONSE_CANCEL)
    dialog.add_button(_("Remove"), gtk.RESPONSE_ACCEPT)
    # add the dependencies
    if depends:
        vbox = dialog.get_content_area()
        # FIXME: make this a generic pkgview widget
        model = gtk.ListStore(str)
        view = PkgNamesView(_("Dependencies"), cache, depends)
        scrolled = gtk.ScrolledWindow()
        scrolled.set_size_request(-1, 200)
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled.add(view)
        scrolled.show_all()
        vbox.pack_start(scrolled)
    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_ACCEPT:
        return True
    return False
    
