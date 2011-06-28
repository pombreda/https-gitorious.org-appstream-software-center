# Copyright (C) 2009-2010 Canonical
#
# Authors:
#  Alex Eftimie
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

import gobject
import logging
import dbus
import dbus.mainloop.glib
import os
from gettext import gettext as _

from gi.repository import PackageKitGlib as packagekit

from softwarecenter.enums import TransactionTypes
from softwarecenter.backend.transactionswatcher import BaseTransactionsWatcher, BaseTransaction
from softwarecenter.backend.installbackend import InstallBackend

# temporary, must think of better solution
from softwarecenter.db.pkginfo import get_pkg_info

class PackagekitTransaction(BaseTransaction):
    _tlist = []
    
    def __init__(self, trans):
        """ trans -- a PkProgress object """
        gobject.GObject.__init__(self)
        self._trans = trans
        PackagekitTransaction._tlist.append(self)

    @staticmethod
    def get_transaction_for_tid(tid):
        """ how can I do this better? """
        for t in PackagekitTransaction._tlist:
            if t.tid == tid:
                return t
        return None

    @property
    def tid(self):
        return self._trans.get_property('transaction-id')
    @property
    def status_details(self):
        return self._trans.get_property('status') # FIXME
    @property
    def meta_data(self):
        return {} # FIXME
    @property
    def cancellable(self):
        return self._trans.get_property('allow-cancel')
    @property
    def progress(self):
        return self._trans.get_property('percentage')

    def get_role_description(self, role=None):
        role = role if role is not None else self._trans.get_property('role')
        return packagekit.role_enum_to_string(role)

    def get_status_description(self, status=None):
        status = status if status is not None else self._trans.get_property('status')
        return packagekit.status_enum_to_string(status)

    def is_waiting(self):
        return self._trans.get_property('status') == packagekit.StatusEnum.WAIT

    def is_downloading(self):
        return self._trans.get_property('status') == packagekit.StatusEnum.DOWNLOAD

    def cancel(self):
        logging.error("Cancel not implemented") # FIXME

class PackagekitTransactionsWatcher(BaseTransactionsWatcher):
    def __init__(self):
        super(PackagekitTransactionsWatcher, self).__init__()
        self.client = packagekit.Client()

        bus = dbus.SystemBus()
        proxy = bus.get_object('org.freedesktop.PackageKit', '/org/freedesktop/PackageKit')
        daemon = dbus.Interface(proxy, 'org.freedesktop.PackageKit')
        daemon.connect_to_signal("TransactionListChanged", 
                                     self._on_transactions_changed)
        queued = daemon.GetTransactionList()
        self._on_transactions_changed(queued)

    def _on_transactions_changed(self, queued):
        if len(queued) > 0:
            current = queued[0]
            queued = queued[1:] if len(queued) > 1 else []
        else:
            current = None
        self.emit("lowlevel-transactions-changed", current, queued)

    def get_transaction(self, tid):
        trans = self.client.get_progress(tid, None)
        return PackagekitTransaction(trans)

class PackagekitBackend(gobject.GObject, InstallBackend):
    
    __gsignals__ = {'transaction-started':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            (str,str,str,str)),
                    # emits a TransactionFinished object
                    'transaction-finished':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            (gobject.TYPE_PYOBJECT, )),
                    'transaction-stopped':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            (gobject.TYPE_PYOBJECT,)),
                    'transactions-changed':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            (gobject.TYPE_PYOBJECT, )),
                    'transaction-progress-changed':(gobject.SIGNAL_RUN_FIRST,
                                                    gobject.TYPE_NONE,
                                                    (str,int,)),
                    # the number/names of the available channels changed
                    'channels-changed':(gobject.SIGNAL_RUN_FIRST,
                                        gobject.TYPE_NONE,
                                        (bool,)),
                    # cache reload emits this specific signal as well
                    'reload-finished':(gobject.SIGNAL_RUN_FIRST,
                                       gobject.TYPE_NONE,
                                       (gobject.TYPE_PYOBJECT, bool,)),
                    }

    def __init__(self):
        gobject.GObject.__init__(self)
        InstallBackend.__init__(self)

        self.client = packagekit.Client()
        self.pkginfo = get_pkg_info()
        self.pkginfo.open()

        self._transactions_watcher = PackagekitTransactionsWatcher()
        self._logger = logging.getLogger("softwarecenter.backend.packagekitd")

    def upgrade(self, pkgname, appname, iconname, addons_install=[],
                addons_remove=[], metadata=None):
        pass # FIXME
    def remove(self, pkgname, appname, iconname, addons_install=[],
                addons_remove=[], metadata=None):
        self.remove_multiple((pkgname,), (appname,), (iconname,),
                addons_install, addons_remove, metadata
        )

    def remove_multiple(self, pkgnames, appnames, iconnames,
                addons_install=[], addons_remove=[], metadatas=None):

        # temporary hack
        pkgnames = self._fix_pkgnames(pkgnames)

        self.client.remove_packages(pkgnames,
                    False, # allow deps
                    False, # autoremove
                    None, # cancellable
                    self._on_progress_changed,
                    None # progress data
        )
        self.emit("transaction-started", pkgnames[0], appnames[0], 0, TransactionTypes.REMOVE)

    def install(self, pkgname, appname, iconname, filename=None,
                addons_install=[], addons_remove=[], metadata=None):
        if filename is not None:
            self._logger.error("Filename not implemented") # FIXME
        else:
            self.install_multiple((pkgname,), (appname,), (iconname,),
                 addons_install, addons_remove, metadata
            )

    def install_multiple(self, pkgnames, appnames, iconnames,
        addons_install=[], addons_remove=[], metadatas=None):

        # temporary hack
        pkgnames = self._fix_pkgnames(pkgnames)

        self.client.install_packages_async(False, # only trusted
                    pkgnames,
                    None, # cancellable
                    self._on_progress_changed,
                    None, # progress data
                    self._on_install_ready, # GAsyncReadyCallback
                    None  # ready data
        )
        self.emit("transaction-started", pkgnames[0], appnames[0], 0, TransactionTypes.INSTALL)

    def apply_changes(self, pkgname, appname, iconname,
        addons_install=[], addons_remove=[], metadata=None):
        pass
    def reload(self, sources_list=None, metadata=None):
        """ reload package list """
        pass

    def _on_progress_changed(self, status, ptype, data=None):
        """ de facto callback on transaction's progress change """
        trans = PackagekitTransaction.get_transaction_for_tid(
                                status.get_property('transaction-id')
        )
        if trans is None:
            logging.error("Getting progress changed from unknown transaction")
            return

        if ptype == packagekit.ProgressType.ROLE:
            trans.emit('role-changed', status.get_property('role'))
        elif ptype == packagekit.ProgressType.STATUS:
            trans.emit('status-changed', status.get_property('status'))
        elif ptype == packagekit.ProgressType.PERCENTAGE:
            trans.emit('progress-changed', status.get_property('percentage'))
        else:
            print "Unimplemented ",
            print status.get_property('transaction-id'),status.get_property('status'),
            print ptype

    def _on_install_ready(self, source, result, data=None):
        print "install done", source, result # FIXME

    def _fix_pkgnames(self, pkgnames):
        is_pk_id = lambda a: ';' in a
        res = []
        for p in pkgnames:
            if not is_pk_id(p):
                version = self.pkginfo[p].candidate.version
                p = '{name};{version};{arch};{source}'.format(name=p,
                            version=version, arch='', source=''
                )
            res.append(p)
        return res

if __name__ == "__main__":
    package = 'firefox'

    loop = dbus.mainloop.glib.DBusGMainLoop()
    dbus.set_default_main_loop(loop)
    
    backend = PackagekitBackend()
    pkginfo = get_pkg_info()
    if pkginfo[package].is_installed:
        backend.remove(package, package, '')
        backend.install(package, package, '')
    else:
        backend.install(package, package, '')
        backend.remove(package, package, '')
    import gtk;gtk.main()
    #print backend._fix_pkgnames(('cheese',))

