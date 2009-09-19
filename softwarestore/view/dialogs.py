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

def error(parent, primary, secondary, details=None):
    """ show a untitled error dialog """
    return messagedialog(parent=parent,
                         primary=primary, 
                         secondary=secondary,
                         details=details,
                         dialogtype=gtk.MESSAGE_ERROR)

def messagedialog(parent, 
                  title="", 
                  primary=None, 
                  secondary=None, 
                  details=None,
                  dialogbuttons=gtk.BUTTONS_OK, 
                  dialogtype=gtk.MESSAGE_INFO):
    """ run a dialog """
    dialog = gtk.MessageDialog(parent=None, flags=0, type=dialogtype, 
                               buttons=dialogbuttons, message_format=primary)
    dialog.set_title(title)
    if secondary:
        dialog.format_secondary_markup(secondary)
    if details:
        textview = gtk.TextView()
        textview.get_buffer().set_text(details)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(textview)
        expand = gtk.Expander(_("Details"))
        expand.add(scroll)
        expand.show_all()
        dialog.get_content_area().pack_start(expand)
    result = dialog.run()
    dialog.hide()
    return result


def confirm_remove(parent, primary, cache, button_text, icon_path, depends=[]):
    """Confirm removing of the given app with the given depends"""
    dialog = gtk.MessageDialog(parent=parent, flags=0, 
                               type=gtk.MESSAGE_QUESTION, 
                               message_format=None)
    dialog.set_resizable(True)
    dialog.add_button(_("Cancel"), gtk.RESPONSE_CANCEL)
    dialog.add_button(button_text, gtk.RESPONSE_ACCEPT)
    dialog.get_image().set_from_file(icon_path)
    dialog.set_markup(primary)
    # add the dependencies
    if depends:
        vbox = dialog.get_content_area()
        # FIXME: make this a generic pkgview widget
        view = PkgNamesView(_("Dependency"), cache, depends)
        view.set_headers_visible(False)
        scrolled = gtk.ScrolledWindow()
        scrolled.set_size_request(-1, 200)
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        scrolled.add(view)
        scrolled.show_all()
        vbox.pack_start(scrolled)
    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_ACCEPT:
        return True
    return False
    
