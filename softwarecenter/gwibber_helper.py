# Copyright (C) 2010 Matthew McGowan
#
# Authors:
#  Matthew McGowan
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

import dbus
from xdg import BaseDirectory as xdg
import os.path
import simplejson

class GwibberHelper(object):

    def __init__(self):
        bus = dbus.SessionBus()
        # accounts
        proxy_obj = bus.get_object("com.Gwibber.Accounts",
                                   "/com/gwibber/Accounts")
        self.accounts_iface = dbus.Interface(proxy_obj, "com.Gwibber.Accounts")
        # system
        proxy_obj = bus.get_object("com.Gwibber.Service",
                                   "/com/gwibber/Service")
        self.service_iface = dbus.Interface(proxy_obj, "com.Gwibber.Service")

    def accounts(self):
        """ returns accounts that are send_enabled """
        accounts = []
        for account in simplejson.loads( self.accounts_iface.List()):
            if account["send_enabled"]:
                accounts.append(account)
        return accounts

    def send_message(self, message):
        """ send message to all accounts with send_enabled """
        self.service_iface.SendMessage(message)

# don't use dbus, triggers a gwibber start each time we call this
def gwibber_has_accounts_in_sqlite():
    import sqlite3
    dbpath = "%s/gwibber/gwibber.sqlite" % xdg.xdg_config_home
    if not os.path.exists(dbpath):
        return False
    with sqlite3.connect(dbpath) as db:
        results = db.execute("SELECT data FROM accounts")
        if len(results.fetchall()) > 0:
            return True
    return False

GWIBBER_SERVICE_AVAILABLE = gwibber_has_accounts_in_sqlite() and os.path.exists("/usr/bin/gwibber-poster")


