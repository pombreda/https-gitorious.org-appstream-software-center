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
    """ A helper class for gwibber. ideally we would just use 
        from gi.repository import Gwibber
        accounts = Gwibbers.Accounts()
        accounts.list()
        ...
        instead of the dbus iface, but the gi stuff fails
        to export "Accounts.list()" (and possible more) currently
    """

    def accounts(self):
        """ returns accounts that are send_enabled """
        bus = dbus.SessionBus()
        proxy_obj = bus.get_object("com.Gwibber.Accounts",
                                   "/com/gwibber/Accounts")
        accounts_iface = dbus.Interface(proxy_obj, "com.Gwibber.Accounts")
        accounts = []
        for account in simplejson.loads(accounts_iface.List()):
            if account["send_enabled"]:
                accounts.append(account)
        return accounts

    def send_message(self, message, account_id=None):
        """ send message to all accounts with send_enabled """
        bus = dbus.SessionBus()
        proxy_obj = bus.get_object("com.Gwibber.Service",
                                   "/com/gwibber/Service")
        service_iface = dbus.Interface(proxy_obj, "com.Gwibber.Service")
        service_iface.SendMessage(message)

    @staticmethod
    def has_accounts_in_sqlite():
        """ return if there are accounts for gwibber in sqlite """
        # don't use dbus, triggers a gwibber start each time we call this
        import sqlite3
        dbpath = "%s/gwibber/gwibber.sqlite" % xdg.xdg_config_home
        if not os.path.exists(dbpath):
            return False
        with sqlite3.connect(dbpath) as db:
            results = db.execute("SELECT data FROM accounts")
            if len(results.fetchall()) > 0:
                return True
        return False

class GwibberHelperMock(object):
        
    fake_gwibber_accounts_one = [{u'username': u'randomuser', u'user_id': u'2323434224', u'service': u'twitter', u'secret_token': u':some-token', u'color': u'#729FCF', u'receive_enabled': True, u'access_token': u'some_access_token', u'send_enabled': True, u'id': u'600eafsdsf12c61a2111e095e90015af8bddb6'}]
    fake_gwibber_accounts_multiple = [{u'username': u'random1', u'user_id': u'2342342313', u'service': u'twitter', u'secret_token': u':some-token', u'color': u'#729FCF', u'receive_enabled': True, u'access_token': u'some_access_token', u'send_enabled': True, u'id': u'600e12c61a21sdfdsaf8bddb6'}, {u'username': u'mpt', u'user_id': u'23safdsaf5', u'service': u'twitter', u'secret_token': u':some_otken', u'color': u'#729FCF', u'receive_enabled': True, u'access_token': u'some_access_token', u'send_enabled': True, u'id': u'afsdfdsa32fafsdfsa'}]

    def accounts(self):
        num = os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_USERS"]
        if int(num) == 0:
            return []
        elif int(num) == 1:
            return self.fake_gwibber_accounts_one
        else:
            return self.fake_gwibber_accounts_multiple

    def send_message(self, message, account_id):
        sys.stderr.write("sending '%s' to '%s'" % (message, account_id))
    
    def has_accounts_in_sqlite():
        return True


GWIBBER_SERVICE_AVAILABLE = GwibberHelper.has_accounts_in_sqlite() and os.path.exists("/usr/bin/gwibber-poster")


