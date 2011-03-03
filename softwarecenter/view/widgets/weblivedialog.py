# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#  Stephane Graber
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

import gtk, sys

class ShowWebLiveServerChooserDialog(gtk.Dialog):
    """A dialog to choose between multiple server"""

    def __init__(self, servers, parent=None):
        gtk.Dialog.__init__(self)
        self.set_has_separator(False)

        # find parent window for the dialog
        if not parent:
            parent = self.get_parent()
            while parent:
                parent = w.get_parent()

        # servers
        self.servers_vbox=gtk.VBox(False, 0)
        button=None

        for server in servers:
            button=gtk.RadioButton(button, server.title)
            button.serverid=server.name
            self.servers_vbox.pack_start(button, True, True, 0)

        # dialog
        self.set_transient_for(parent)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.get_content_area().add(self.servers_vbox)
        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.set_resizable(False)
        self.set_title("WebLive server chooser")

    def run(self):
        self.show_all()

        # and run the real thing
        return gtk.Dialog.run(self)

if __name__ == "__main__":
    sys.path.append('../../../')

    from softwarecenter.backend.weblive_pristine import WebLive
    weblive=WebLive('https://weblive.stgraber.org/weblive/json',True)
    servers=weblive.list_everything()

    d = ShowWebLiveServerChooserDialog(servers)
    if d.run() == gtk.RESPONSE_OK:
        for server in d.servers_vbox:
            if server.get_active():
                print server.serverid
                break
    d.destroy()
