# Copyright (C) 2009-2010 Canonical
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

import aptsources.sourceslist
import dbus
import gobject
import logging
import os
import subprocess
import sys
from softwarecenter.utils import *

from aptdaemon import client
from aptdaemon import enums
from aptdaemon.gtkwidgets import AptMediumRequiredDialog, \
                                 AptConfigFileConflictDialog

from aptsources.sourceslist import SourceEntry

try:
    from aptdaemon.defer import inline_callbacks
except ImportError:
    logging.getLogger("softwarecenter.backend").exception("aptdaemon import failed")
    print 'Need the latest aptdaemon, try "sudo apt-add-repository ppa:software-store-developers/ppa" to get the PPA'
    sys.exit(1)

import gtk

from softwarecenter.backend.transactionswatcher import TransactionsWatcher
from softwarecenter.utils import get_http_proxy_string_from_gconf
from softwarecenter.view import dialogs

from gettext import gettext as _

# we use this instead of just exposing the aptdaemon Transaction object
# so that we have a easier time porting it to a different backend
class TransactionFinishedResult(object):
    """ represents the result of a transaction """
    def __init__(self, trans, enum):
        self.success = (enum != enums.EXIT_FAILED)
        self.pkgname = trans.meta_data.get("sc_pkgname")
        self.meta_data = trans.meta_data

class TransactionProgress(object):
    """ represents the progress of the transaction """
    def __init__(self, trans):
        self.pkgname = trans.meta_data.get("sc_pkgname")
        self.meta_data = trans.meta_data
        self.progress = trans.progress

class AptdaemonBackend(gobject.GObject, TransactionsWatcher):
    """ software center specific code that interacts with aptdaemon """

    __gsignals__ = {'transaction-started':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            ()),
                    # emits a TransactionFinished object
                    'transaction-finished':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            (gobject.TYPE_PYOBJECT, )),
                    'transaction-stopped':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            (str,)),                    
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
        TransactionsWatcher.__init__(self)
        self.aptd_client = client.AptClient()
        self.pending_transactions = {}
        self.pending_purchases = set()
        self._progress_signal = None
        self._logger = logging.getLogger("softwarecenter.backend")
    
    def _axi_finished(self, res):
        self.emit("channels-changed", res)

    # public methods
    def update_xapian_index(self):
        self._logger.debug("update_xapian_index")
        system_bus = dbus.SystemBus()
        axi = dbus.Interface(
            system_bus.get_object("org.debian.AptXapianIndex","/"),
            "org.debian.AptXapianIndex")
        axi.connect_to_signal("UpdateFinished", self._axi_finished)
        # we don't really care for updates at this point
        #axi.connect_to_signal("UpdateProgress", progress)
        # first arg is force, second update_only
        axi.update_async(True, True)

    @inline_callbacks
    def fix_broken_depends(self):
        self.emit("transaction-started")
        try:
            trans = yield self.aptd_client.fix_broken_depends(defer=True)
            yield self._run_transaction(trans, None, None, None)
        except Exception, error:
            self._on_trans_error(error)

    # FIXME: upgrade add-ons here
    @inline_callbacks
    def upgrade(self, pkgname, appname, iconname, addons_install=[], addons_remove=[], metadata=None):
        """ upgrade a single package """
        self.emit("transaction-started")
        try:
            trans = yield self.aptd_client.upgrade_packages([pkgname],
                                                            defer=True)
            yield self._run_transaction(trans, pkgname, appname, iconname, metadata)
        except Exception, error:
            self._on_trans_error(error, pkgname)

    @inline_callbacks
    def remove(self, pkgname, appname, iconname, addons_install=[], addons_remove=[], metadata=None):
        """ remove a single package """
        self.emit("transaction-started")
        try:
            trans = yield self.aptd_client.remove_packages([pkgname],
                                                           defer=True)
            yield self._run_transaction(trans, pkgname, appname, iconname, metadata)
        except Exception, error:
            self._on_trans_error(error, pkgname)

    @inline_callbacks
    def remove_multiple(self, pkgnames, appnames, iconnames, addons_install=[], addons_remove=[], metadatas=None):
        """ queue a list of packages for removal  """
        if metadatas == None:
            metadatas = []
            for item in pkgnames:
                metadatas.append(None)
        for pkgname, appname, iconname, metadata in zip(pkgnames, appnames, iconnames, metadatas):
            yield self.remove(pkgname, appname, iconname, metadata)

    @inline_callbacks
    def install(self, pkgname, appname, iconname, filename=None, addons_install=[], addons_remove=[], metadata=None):
        """Install a single package from the archive
           If filename is given a local deb package is installed instead.
        """
        self.emit("transaction-started")
        try:
            if filename:
                trans = yield self.aptd_client.install_file(filename,
                                                            defer=True)
            else:
                trans = yield self.aptd_client.commit_packages([pkgname] + addons_install, [], addons_remove, [], [])
            yield self._run_transaction(trans, pkgname, appname, iconname, metadata)
        except Exception, error:
            self._on_trans_error(error, pkgname)

    @inline_callbacks
    def install_multiple(self, pkgnames, appnames, iconnames, addons_install=[], addons_remove=[], metadatas=None):
        """ queue a list of packages for install  """
        if metadatas == None:
            metadatas = []
            for item in pkgnames:
                metadatas.append(None)
        for pkgname, appname, iconname, metadata in zip(pkgnames, appnames, iconnames, metadatas):
            yield self.install(pkgname, appname, iconname, metadata=metadata)
            
    @inline_callbacks
    def apply_changes(self, pkgname, appname, iconname, addons_install=[], addons_remove=[], metadata=None):
        """ install and remove add-ons """
        self.emit("transaction-started")
        try:
            trans = yield self.aptd_client.commit_packages(addons_install, [], addons_remove, [], [])
            yield self._run_transaction(trans, pkgname, appname, iconname)
        except Exception, error:
            self._on_trans_error(error)

    @inline_callbacks
    def reload(self, metadata=None):
        """ reload package list """
        try:
            trans = yield self.aptd_client.update_cache(defer=True)
            yield self._run_transaction(trans, None, None, None, metadata)
        except Exception, error:
            self._on_trans_error(error)

    @inline_callbacks
    def enable_component(self, component):
        self._logger.debug("enable_component: %s" % component)
        try:
            yield self.aptd_client.enable_distro_component(component, defer=True)
        except Exception, error:
            self._on_trans_error(error, component)
            return
        # now update the cache
        yield self.reload()

    @inline_callbacks
    def enable_channel(self, channelfile):
        # read channel file and add all relevant lines
        for line in open(channelfile):
            line = line.strip()
            if not line:
                continue
            entry = SourceEntry(line)
            if entry.invalid:
                continue
            sourcepart = os.path.basename(channelfile)
            yield self.add_sources_list_entry(entry, sourcepart)
        yield self.reload()

    @inline_callbacks
    def add_vendor_key_from_keyserver(self, keyid, 
                                      keyserver="keyserver.ubuntu.com",
                                      metadata=None):
        # strip the keysize
        if "/" in keyid:
            keyid = keyid.split("/")[1]
        if not keyid.startswith("0x"):
            keyid = "0x%s" % keyid
        try:
            trans = yield self.aptd_client.add_vendor_key_from_keyserver(
                keyid, keyserver)
            yield self._run_transaction(trans, None, None, None, metadata)
        except Exception, error:
            self._on_trans_error(error)

    @inline_callbacks
    def add_sources_list_entry(self, source_entry, sourcepart=None):
        if isinstance(source_entry, basestring):
            entry = SourceEntry(source_entry)
        elif isinstance(source_entry, SourceEntry):
            entry = source_entry
        else:
            raise ValueError, "Unsupported entry type %s" % type(source_entry)

        if not sourcepart:
            sourcepart = sources_filename_from_ppa_entry(entry)

        args = (entry.type, entry.uri, entry.dist, entry.comps,
                "Added by software-center", sourcepart)
        try:
            yield self.aptd_client.add_repository(*args)
        except dbus.DBusException, err:
            if err.get_dbus_name() == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                self._logger.error("add_repository: '%s'" % err)
                return
                
    def add_repo_add_key_and_install_app(self,
                                         deb_line,
                                         signing_key_id,
                                         app,
                                         purchase=True):
        """ 
        a convenience method that combines all of the steps needed
        to install a for-pay application, including adding the
        source entry and the vendor key, reloading the package list,
        and finally installing the specified application once the
        package list reload has completed.
        """
        self.emit("transaction-started")

        if purchase:
            self.pending_purchases.add(app.pkgname)

        # metadata so that we know those the add-key and reload transactions
        # are part of a group
        trans_metadata = {'sc_add_repo_and_install_appname' : app.appname, 
                          'sc_add_repo_and_install_pkgname' : app.pkgname,
                         }
        # TODO:  add error checking as needed
        self.add_sources_list_entry(deb_line)
        self.add_vendor_key_from_keyserver(signing_key_id, 
                                           metadata=trans_metadata)
        self.emit("channels-changed", True)
        # reload to ensure we have the new package data
        self.reload(metadata=trans_metadata)
        # and then queue the install only when the reload finished
        # otherwise the daemon will fail because he does not know
        # the new package name yet
        self._reload_signal_id = self.connect(
            "reload-finished", self._on_reload_for_add_repo_and_install_app_finished, trans_metadata, app)
            
    @inline_callbacks
    def _on_reload_for_add_repo_and_install_app_finished(self, backend, trans, result, metadata, app):
        """ 
        callback that is called once after reload was queued
        and will trigger the install of the for-pay package itself
        (after that it will automatically de-register)
        """
        #print trans, result, backend

        # check if this is the transaction we waiting for
        key = "sc_add_repo_and_install_pkgname"
        if not (key in trans.meta_data and trans.meta_data[key] == app.pkgname):
            return

        # disconnect again, this is only a one-time operation
        self.handler_disconnect(self._reload_signal_id)
        self._reload_signal_id = None

        # run install action if the repo was added successfully 
        if result:
            # we use aptd_client.install_packages() here instead
            # of just 
            #  self.install(app.pkgname, app.appname, "", metadata=metadata)
            # go get less authentication prompts (because of the 03_auth_me_less
            # patch in aptdaemon)
            try:
                trans = yield self.aptd_client.install_packages(
                    [app.pkgname], defer=True)
                yield self._run_transaction(trans, app.pkgname, app.appname,
                                            "", metadata)
            except Exception, error:
                self._on_trans_error(error, app.pkgname)


    # internal helpers
    def on_transactions_changed(self, current, pending):
        # cleanup progress signal (to be sure to not leave dbus matchers around)
        if self._progress_signal:
            gobject.source_remove(self._progress_signal)
            self._progress_signal = None
        # attach progress-changed signal for current transaction
        if current:
            trans = client.get_transaction(current, 
                                           error_handler=lambda x: True)
            self._progress_signal = trans.connect("progress-changed", self._on_progress_changed)
        # now update pending transactions
        self.pending_transactions.clear()
        for tid in [current] + pending:
            if not tid:
                continue
            trans = client.get_transaction(tid, error_handler=lambda x: True)
            trans_progress = TransactionProgress(trans)
            try:
                self.pending_transactions[trans_progress.pkgname] = trans_progress
            except KeyError:
                # if its not a transaction from us (sc_pkgname) still
                # add it with the tid as key to get accurate results
                # (the key of pending_transactions is never directly
                #  exposed in the UI)
                self.pending_transactions[trans.tid] = trans_progress
        self.emit("transactions-changed", self.pending_transactions)

    def _on_progress_changed(self, trans, progress):
        """ 
        internal helper that gets called on our package transaction progress 
        (only showing pkg progress currently)
        """
        try:
            pkgname = trans.meta_data["sc_pkgname"]
            self.pending_transactions[pkgname].progress = progress
            self.emit("transaction-progress-changed", pkgname, progress)
        except KeyError:
            pass

    def _on_trans_finished(self, trans, enum):
        """callback when a aptdaemon transaction finished"""
        self._logger.debug("_on_transaction_finished: %s %s %s" % (
                trans, enum, trans.meta_data))
        if enum == enums.EXIT_FAILED:
            # daemon died are messages that result from broken
            # cancel handling in aptdaemon (LP: #440941)
            # FIXME: this is not a proper fix, just a workaround
            if trans.error_code == enums.ERROR_DAEMON_DIED:
                self._logger.warn("daemon dies, ignoring: %s" % excep)
            else:
                msg = "%s: %s\n%s\n\n%s" % (
                    _("Error"),
                    enums.get_error_string_from_enum(trans.error_code),
                    enums.get_error_description_from_enum(trans.error_code),
                    trans.error_details)
                self._logger.error("error in _on_trans_finished '%s'" % msg)
                # show dialog to the user and exit (no need to reopen
                # the cache)
                dialogs.error(
                    None, 
                    enums.get_error_string_from_enum(trans.error_code),
                    enums.get_error_description_from_enum(trans.error_code),
                    trans.error_details)
        # send finished signal, use "" here instead of None, because
        # dbus mangles a None to a str("None")
        pkgname = ""
        try:
            pkgname = trans.meta_data["sc_pkgname"]
            del self.pending_transactions[pkgname]
            self.emit("transaction-progress-changed", pkgname, 100)
        except KeyError:
            pass
        # if it was a cache-reload, trigger a-x-i update
        if trans.role == enums.ROLE_UPDATE_CACHE:
            self.update_xapian_index()
            self.emit("reload-finished", trans, enum != enums.EXIT_FAILED)
        # send appropriate signals
        self.emit("transactions-changed", self.pending_transactions)
        self.emit("transaction-finished", TransactionFinishedResult(trans, enum))

    def _config_file_conflict(self, transaction, old, new):
        dia = AptConfigFileConflictDialog(old, new)
        res = dia.run()
        dia.hide()
        dia.destroy()
        # send result to the daemon
        if res == gtk.RESPONSE_YES:
            transaction.resolve_config_file_conflict(old, "replace")
        else:
            transaction.resolve_config_file_conflict(old, "keep")

    def _medium_required(self, transaction, medium, drive):
        dialog = AptMediumRequiredDialog(medium, drive)
        res = dialog.run()
        dialog.hide()
        if res == gtk.RESPONSE_OK:
            transaction.provide_medium(medium)
        else:
            transaction.cancel()

    @inline_callbacks
    def _run_transaction(self, trans, pkgname, appname, iconname, metadata=None):
        # connect signals
        trans.connect("config-file-conflict", self._config_file_conflict)
        trans.connect("medium-required", self._medium_required)
        trans.connect("finished", self._on_trans_finished)
        try:
            # set appname/iconname/pkgname only if we actually have one
            if appname:
                yield trans.set_meta_data(sc_appname=appname, defer=True)
            if iconname:
                yield trans.set_meta_data(sc_iconname=iconname, defer=True)
            # we do not always have a pkgname, e.g. "cache_update" does not
            if pkgname:
                yield trans.set_meta_data(sc_pkgname=pkgname, defer=True)
                # setup debconf only if we have a pkg
                yield trans.set_debconf_frontend("gnome", defer=True)
                # set this once the new aptdaemon 0.2.x API can be used
                trans.set_remove_obsoleted_depends(True, defer=True)
            # generic metadata
            if metadata:
                yield trans.set_meta_data(**metadata)
            # set proxy and run
            http_proxy = get_http_proxy_string_from_gconf()
            if http_proxy:
                trans.set_http_proxy(http_proxy, defer=True)
            yield trans.run(defer=True)
        except Exception, error:
            self._on_trans_error(pkgname, error)
            # on error we need to clean the pending purchases
            self._clean_pending_purchases(pkgname)
        # on success the pending purchase is cleaned when the package
        # that was purchased finished installing
        if trans.role == enums.ROLE_INSTALL_PACKAGES:
            self._clean_pending_purchases(pkgname)


    def _clean_pending_purchases(self, pkgname):
        if pkgname and pkgname in self.pending_purchases:
            self.pending_purchases.remove(pkgname)

    def _on_trans_error(self, error, pkgname=None):
        self._logger.warn("_on_trans_error: %s", error)
        # re-enable the action button again if anything went wrong
        self.emit("transaction-stopped", pkgname)
        if isinstance(error, dbus.DBusException):
            name = error.get_dbus_name()
            if name in ["org.freedesktop.PolicyKit.Error.NotAuthorized",
                        "org.freedesktop.DBus.Error.NoReply"]:
                pass
        else:
            logging.exception("_on_trans_error")
            #raise error

if __name__ == "__main__":
    #c = client.AptClient()
    #c.remove_packages(["4g8"], remove_unused_dependencies=True)
    backend = AptdaemonBackend()
    backend.reload()

