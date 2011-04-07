# Copyright (C) 2011 Canonical
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

    def __init__(self, supplied_servers, pkgname, parent=None):
        gtk.Dialog.__init__(self)
        self.set_has_separator(False)

        # find parent window for the dialog
        if not parent:
            parent = self.get_parent()
            while parent:
                parent = w.get_parent()

        # servers
        self.servers_vbox=gtk.VBox(False, 0)

        # Merge duplicate servers, keep the one with the most space
        servers=[]
        for server in supplied_servers:
            duplicate=False
            for otherserver in servers:
                if server.title == otherserver.title:
                    percent_server=((float(server.current_users)/float(server.userlimit))*100.0)
                    percent_otherserver=((float(otherserver.current_users)/float(otherserver.userlimit))*100.0)
                    for package in server.packages:
                        if package.pkgname == pkgname:
                            autoinstall_server=package.autoinstall

                    for package in otherserver.packages:
                        if package.pkgname == pkgname:
                            autoinstall_otherserver=package.autoinstall

                    # Replace existing server if:
                    #  current server has more free slots and we don't switch to a server requiring autoinstall
                    #  or doesn't need autoinstall but existing one does
                    if (percent_otherserver > percent_server and not autoinstall_otherserver < autoinstall_server) or autoinstall_otherserver > autoinstall_server:
                        servers.remove(otherserver)
                        servers.append(server)
                    duplicate=True

            if duplicate:
                continue

            servers.append(server)

        if len(servers) == 1:
            self.show_dialog=False
        else:
            self.show_dialog=True

        button=None
        for server in sorted(servers, key=lambda server: server.title):
            button=gtk.RadioButton(button, "%s - %s" % (server.title, server.description))
            button.serverid=server.name
            self.servers_vbox.pack_start(button, True, True, 0)

        # dialog
        self.set_transient_for(parent)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.get_content_area().add(self.servers_vbox)
        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.set_resizable(False)
        self.set_title(_("Choose your distribution"))
        self.set_border_width(8)

    def run(self):
        if self.show_dialog == False:
            return gtk.RESPONSE_OK

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
