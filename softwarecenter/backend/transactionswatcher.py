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

import dbus
import gobject

class BaseTransactionsWatcher(gobject.GObject):
    """ 
    base class for objects that need to watch the install backend 
    for transaction changes.

    provides a "lowlevel-transactions-changed" signal
    """

    __gsignals__ = {'lowlevel-transactions-changed': (gobject.SIGNAL_RUN_FIRST,
                                                     gobject.TYPE_NONE,
                                                     (str,gobject.TYPE_PYOBJECT)),
                    }



# singleton
_tw = None
def get_transactions_watcher():
    global _tw
    if _tw is None:
        from aptd import AptdaemonTransactionsWatcher
        _tw = AptdaemonTransactionsWatcher()
    return _tw
