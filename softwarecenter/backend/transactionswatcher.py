# Copyright (C) 2009 Canonical
#
# Authors:
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

from gi.repository import GObject

class BaseTransaction(GObject.GObject):
    """
    wrapper class for install backend dbus Transaction objects
    """
    @property
    def tid(self):
        pass
    @property
    def status_details(self):
        pass
    @property
    def meta_data(self):
        return {}
    @property
    def cancellable(self):
        return False
    @property
    def progress(self):
        return False

    def get_role_description(self, role=None):
        pass

    def get_status_description(self, status=None):
        pass

    def is_waiting(self):
        return False

    def is_downloading(self):
        return False

    def cancel(self):
        pass

class BaseTransactionsWatcher(GObject.GObject):
    """ 
    base class for objects that need to watch the install backend 
    for transaction changes.

    provides a "lowlevel-transactions-changed" signal
    """

    __gsignals__ = {'lowlevel-transactions-changed': (GObject.SIGNAL_RUN_FIRST,
                                                     GObject.TYPE_NONE,
                                                     (str,GObject.TYPE_PYOBJECT)),
                    }

    def get_transaction(self, tid):
        """ should return a _Transaction object """
        return None


# singleton
_tw = None
def get_transactions_watcher():
    global _tw
    if _tw is None:
        from aptd import AptdaemonTransactionsWatcher
        _tw = AptdaemonTransactionsWatcher()
    return _tw
