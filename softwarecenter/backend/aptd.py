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
import re
import subprocess
import sys
from softwarecenter.utils import *
from softwarecenter.enums import *

from aptdaemon import client
from aptdaemon import enums
from aptdaemon import errors
from aptdaemon.gtkwidgets import AptMediumRequiredDialog, \
                                 AptConfigFileConflictDialog

from aptsources.sourceslist import SourceEntry
from aptdaemon import policykit1

# natty uses python-defer
try:
    from defer import inline_callbacks, return_value
except ImportError:
    # compat with maverick
    try:
        from aptdaemon.defer import inline_callbacks, return_value
    except ImportError:
        logging.getLogger("softwarecenter.backend").exception("aptdaemon import failed")
        print 'Need the latest aptdaemon, try "sudo apt-add-repository ppa:software-store-developers/ppa" to get the PPA'
        sys.exit(1)

import gtk
from softwarecenter.backend.transactionswatcher import TransactionsWatcher
from softwarecenter.utils import get_http_proxy_string_from_gconf
from softwarecenter.view import dialogs

from gettext import gettext as _

class FakePurchaseTransaction(object):
    def __init__(self, app, iconname):
        self.pkgname = app.pkgname
        self.appname = app.appname
        self.iconname = iconname
        self.progress = 0

# we use this instead of just exposing the aptdaemon Transaction object
# so that we have a easier time porting it to a different backend
class TransactionFinishedResult(object):
    """ represents the result of a transaction """
    def __init__(self, trans, enum):
        self.success = (enum != enums.EXIT_FAILED)
        if trans:
            self.pkgname = trans.meta_data.get("sc_pkgname")
            self.meta_data = trans.meta_data
        else:
            self.pkgname = None
            self.meta_data = None

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
        TransactionsWatcher.__init__(self)
        self.aptd_client = client.AptClient()
        self.pending_transactions = {}
        # dict of pkgname -> FakePurchaseTransaction
        self.pending_purchases = {}
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
        axi.update_async(True, False)

    @inline_callbacks
    def fix_broken_depends(self):
        try:
            trans = yield self.aptd_client.fix_broken_depends(defer=True)
            self.emit("transaction-started", "", "", trans.tid, TRANSACTION_TYPE_REPAIR)
            yield self._run_transaction(trans, None, None, None)
        except Exception, error:
            self._on_trans_error(error)

    # FIXME: upgrade add-ons here
    @inline_callbacks
    def upgrade(self, pkgname, appname, iconname, addons_install=[], addons_remove=[], metadata=None):
        """ upgrade a single package """
        try:
            trans = yield self.aptd_client.upgrade_packages([pkgname],
                                                            defer=True)
            self.emit("transaction-started", pkgname, appname, trans.tid, TRANSACTION_TYPE_UPGRADE)
            yield self._run_transaction(trans, pkgname, appname, iconname, metadata)
        except Exception, error:
            self._on_trans_error(error, pkgname)

# broken
#    @inline_callbacks
#    def _simulate_remove_multiple(self, pkgnames):
#        try:
#            trans = yield self.aptd_client.remove_packages(pkgnames, 
#                                                           defer=True)
#            trans.connect("dependencies-changed", self._on_dependencies_changed)
#        except Exception:
#            logging.exception("simulate_remove")
#        return_value(trans)
#
#   def _on_dependencies_changed(self, *args):
#        print "_on_dependencies_changed", args
#        self.have_dependencies = True
#
#    @inline_callbacks
#    def simulate_remove_multiple(self, pkgnames):
#        self.have_dependencies = False
#        trans = yield self._simulate_remove_multiple(pkgnames)
#        print trans
#        while not self.have_dependencies:
#            while gtk.events_pending():
#                gtk.main_iteration()
#            time.sleep(0.01)

    
    @inline_callbacks
    def remove(self, pkgname, appname, iconname, addons_install=[], addons_remove=[], metadata=None):
        """ remove a single package """
        try:
            trans = yield self.aptd_client.remove_packages([pkgname],
                                                           defer=True)
            self.emit("transaction-started", pkgname, appname, trans.tid, TRANSACTION_TYPE_REMOVE)
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
        try:
            if filename:
                # force means on lintian failure
                trans = yield self.aptd_client.install_file(
                    filename, force=False, defer=True)
                self.emit("transaction-started", pkgname, appname, trans.tid, TRANSACTION_TYPE_INSTALL)
            else:
                install = [pkgname] + addons_install
                remove = addons_remove
                reinstall = remove = purge = upgrade =downgrade = []
                trans = yield self.aptd_client.commit_packages(
                    install, reinstall, remove, purge, upgrade, downgrade, 
                    defer=True)
                self.emit("transaction-started", pkgname, appname, trans.tid, TRANSACTION_TYPE_INSTALL)
            yield self._run_transaction(
                trans, pkgname, appname, iconname, metadata)
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
        try:
            install = addons_install
            remove = addons_remove
            reinstall = remove = purge = upgrade =downgrade = []
            trans = yield self.aptd_client.commit_packages(
                install, reinstall, remove, purge, upgrade, downgrade, 
                defer=True)
            self.emit("transaction-started", pkgname, appname, trans.tid, TRANSACTION_TYPE_APPLY)
            yield self._run_transaction(trans, pkgname, appname, iconname)
        except Exception, error:
            self._on_trans_error(error)

    @inline_callbacks
    def reload(self, sources_list=None, metadata=None):
        """ reload package list """
        # check if the sourcespart is there, if not, do a full reload
        # this can happen when the "partner" repository is added, it
        # will be in the main sources.list already and this means that
        # aptsources will just enable it instead of adding a extra 
        # sources.list.d file (LP: #666956)
        d = apt_pkg.config.find_dir("Dir::Etc::sourceparts")
        if (not sources_list or
            not os.path.exists(os.path.join(d, sources_list))):
            sources_list=""
        try:
            trans = yield self.aptd_client.update_cache(
                sources_list=sources_list, defer=True)
            yield self._run_transaction(trans, None, None, None, metadata)
        except Exception, error:
            self._on_trans_error(error)

    @inline_callbacks
    def enable_component(self, component):
        self._logger.debug("enable_component: %s" % component)
        try:
            yield self.aptd_client.enable_distro_component(component, wait=True, defer=True)
        except Exception, error:
            self._on_trans_error(error, component)
            return_value(None)
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
            keyfile = channelfile.replace(".list",".key")
            if os.path.exists(keyfile):
                yield self.aptd_client.add_vendor_key_from_file(keyfile, wait=True)
        yield self.reload(sourcepart)

    @inline_callbacks
    def add_vendor_key_from_keyserver(self, keyid, 
                                      keyserver="hkp://keyserver.ubuntu.com:80/",
                                      metadata=None):
        # strip the keysize
        if "/" in keyid:
            keyid = keyid.split("/")[1]
        if not keyid.startswith("0x"):
            keyid = "0x%s" % keyid
        try:
            trans = yield self.aptd_client.add_vendor_key_from_keyserver(
                keyid, keyserver, defer=True)
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
            trans = yield self.aptd_client.add_repository(*args, defer=True)
            yield self._run_transaction(trans, None, None, None)
        except errors.NotAuthorizedError, err:
            self._logger.error("add_repository: '%s'" % err)
            return_value(None)
        return_value(sourcepart)

    @inline_callbacks
    def authenticate_for_purchase(self):
        """ 
        helper that authenticates with aptdaemon for a purchase operation 
        """
        bus = dbus.SystemBus()
        name = bus.get_unique_name()
        action = policykit1.PK_ACTION_INSTALL_PURCHASED_PACKAGES
        flags = policykit1.CHECK_AUTH_ALLOW_USER_INTERACTION
        yield policykit1.check_authorization_by_name(name, action, flags=flags)

    @inline_callbacks
    def add_repo_add_key_and_install_app(self,
                                         deb_line,
                                         signing_key_id,
                                         app,
                                         iconname,
                                         purchase=True):
        """ 
        a convenience method that combines all of the steps needed
        to install a for-pay application, including adding the
        source entry and the vendor key, reloading the package list,
        and finally installing the specified application once the
        package list reload has completed.
        """
        self.emit("transaction-started", app.pkgname, app.appname, "FIXME-NEED-ID-HERE", TRANSACTION_TYPE_INSTALL)
        self._logger.info("add_repo_add_key_and_install_app() '%s' '%s' '%s'"% (
                # re.sub() out the password from the log
                re.sub("deb https://.*@", "", deb_line),
                signing_key_id, 
                app))

        if purchase:
            # pre-authenticate
            try:
                yield self.authenticate_for_purchase()
            except:
                self._logger.exception("authenticate_for_purchase failed")
                self._clean_pending_purchases(app.pkgname)
                result = TransactionFinishedResult(None, enums.EXIT_FAILED)
                result.pkgname = app.pkgname
                self.emit("transaction-stopped", result)
                return
            # done
            fake_trans = FakePurchaseTransaction(app, iconname)
            self.pending_purchases[app.pkgname] = fake_trans
        else:
            # FIXME: add authenticate_for_added_repo here
            pass

        # add the metadata early, add_sources_list_entry is a transaction
        # too
        trans_metadata = {'sc_add_repo_and_install_appname' : app.appname, 
                          'sc_add_repo_and_install_pkgname' : app.pkgname,
                          'sc_add_repo_and_install_deb_line' : deb_line,
                          'sc_iconname' : iconname,
                          'sc_add_repo_and_install_try' : "1",
                         }

        self._logger.info("add_sources_list_entry()")
        sourcepart = yield self.add_sources_list_entry(deb_line)
        trans_metadata['sc_add_repo_and_install_sources_list'] = sourcepart

        # metadata so that we know those the add-key and reload transactions
        # are part of a group
        self._logger.info("add_vendor_key_from_keyserver()")
        yield self.add_vendor_key_from_keyserver(signing_key_id,
                                                 metadata=trans_metadata)
        self._logger.info("reload_for_commercial_repo()")
        yield self._reload_for_commercial_repo(app, trans_metadata, sourcepart)

    @inline_callbacks
    def _reload_for_commercial_repo_defer(self, app, trans_metadata, sources_list):
        """ 
        helper that reloads and registers a callback for when the reload is
        finished
        """
        trans_metadata["sc_add_repo_and_install_ignore_errors"] = "1"
        # and then queue the install only when the reload finished
        # otherwise the daemon will fail because he does not know
        # the new package name yet
        self.connect("reload-finished",
                     self._on_reload_for_add_repo_and_install_app_finished, 
                     trans_metadata, app)
        # reload to ensure we have the new package data
        yield self.reload(sources_list=sources_list, metadata=trans_metadata)

    def _reload_for_commercial_repo(self, app, trans_metadata, sources_list):
        """ this reloads a commercial repo in a glib timeout
            See _reload_for_commercial_repo_inline() for the actual work
            that is done
        """
        self._logger.info("_reload_for_commercial_repo() %s" % app)
        # trigger inline_callbacked function
        self._reload_for_commercial_repo_defer(
            app, trans_metadata, sources_list)
        # return False to stop the timeout (one shot only)
        return False

    @inline_callbacks
    def _on_reload_for_add_repo_and_install_app_finished(self, backend, trans, 
                                                         result, metadata, app):
        """ 
        callback that is called once after reload was queued
        and will trigger the install of the for-pay package itself
        (after that it will automatically de-register)
        """
        #print "_on_reload_for_add_repo_and_install_app_finished", trans, result, backend, self._reload_signal_id
        self._logger.info("_on_reload_for_add_repo_and_install_app_finished() %s %s %s" % (trans, result, app))

        # check if this is the transaction we waiting for
        key = "sc_add_repo_and_install_pkgname"
        if not (key in trans.meta_data and trans.meta_data[key] == app.pkgname):
            return_value(None)

        # get the debline and check if we have a release.gpg file
        deb_line = trans.meta_data["sc_add_repo_and_install_deb_line"]
        release_filename = release_filename_in_lists_from_deb_line(deb_line)
        lists_dir = apt_pkg.config.find_dir("Dir::State::lists")
        release_signature = os.path.join(lists_dir, release_filename)+".gpg"
        self._logger.info("looking for '%s'" % release_signature)
        # no Release.gpg in the newly added repository, try again,
        # this can happen e.g. on odd network proxies
        if not os.path.exists(release_signature):
            self._logger.warn("no %s found, re-trying" % release_signature)
            result = False

        # disconnect again, this is only a one-time operation
        self.disconnect_by_func(
            self._on_reload_for_add_repo_and_install_app_finished)

        # FIXME: this logic will *fail* if the sources.list of the user
        #        was broken before

        # run install action if the repo was added successfully 
        if result:
            self.emit("channels-changed", True)

            # we use aptd_client.install_packages() here instead
            # of just 
            #  self.install(app.pkgname, app.appname, "", metadata=metadata)
            # go get less authentication prompts (because of the 03_auth_me_less
            # patch in aptdaemon)
            try:
                self._logger.info("install_package()")
                trans = yield self.aptd_client.install_packages(
                    [app.pkgname], defer=True)
                self._logger.info("run_transaction()")
                yield self._run_transaction(trans, app.pkgname, app.appname,
                                            "", metadata)
            except Exception, error:
                self._on_trans_error(error, app.pkgname)
        else:
            # download failure
            # ok, here is the fun! we can not reload() immediately, because
            # there is a delay of up to 5(!) minutes between s-c-agent telling
            # us that we can download software and actually being able to
            # download it
            retry = int(trans.meta_data['sc_add_repo_and_install_try'])
            if retry > 10:
                self._logger.error("failed to add repo after 10 tries")
                self._clean_pending_purchases(
                    trans.meta_data['sc_add_repo_and_install_pkgname'])
                self._show_transaction_failed_dialog(trans, result)
                return_value(False)
            # this just sets the meta_data locally, but that is ok, the
            # whole re-try machinery will not survive anyway if the local
            # s-c instance is closed
            self._logger.info("queuing reload in 30s")
            trans.meta_data["sc_add_repo_and_install_try"]= str(retry+1)
            sourcepart = trans.meta_data["sc_add_repo_and_install_sources_list"]
            glib.timeout_add_seconds(30, self._reload_for_commercial_repo,
                                     app, trans.meta_data, sourcepart)

    # internal helpers
    def on_transactions_changed(self, current, pending):
        # cleanup progress signal (to be sure to not leave dbus matchers around)
        if self._progress_signal:
            gobject.source_remove(self._progress_signal)
            self._progress_signal = None
        # attach progress-changed signal for current transaction
        if current:
            trans = client.get_transaction(current)
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
        # emit signal
        self.inject_fake_transactions_and_emit_changed_signal()

    def inject_fake_transactions_and_emit_changed_signal(self):
        """ 
        ensures that the fake transactions are considered and emits
        transactions-changed signal with the right pending transactions
        """
        # inject a bunch FakePurchaseTransaction into the transations dict
        for pkgname in self.pending_purchases:
            self.pending_transactions[pkgname] = self.pending_purchases[pkgname]
        # and emit the signal
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

    def _show_transaction_failed_dialog(self, trans, enum):
        # daemon died are messages that result from broken
        # cancel handling in aptdaemon (LP: #440941)
        # FIXME: this is not a proper fix, just a workaround
        if trans.error_code == enums.ERROR_DAEMON_DIED:
            self._logger.warn("daemon dies, ignoring: %s %s" % (trans, enum))
            return
        msg = "%s: %s\n%s\n\n%s" % (
            _("Error"),
            enums.get_error_string_from_enum(trans.error_code),
            enums.get_error_description_from_enum(trans.error_code),
            trans.error_details)
        self._logger.error("error in _on_trans_finished '%s'" % msg)
        # show dialog to the user and exit (no need to reopen the cache)
        if not trans.error_code:
            # sometimes aptdaemon doesn't return a value for error_code when the network
            # connection has become unavailable; in that case, we will assume it's a
            # failure during a package download because that is the only case where we
            # see this happening - this avoids display of an empty error dialog and
            # correctly prompts the user to check their network connection (see LP: #747172)
            trans.error_code = enums.ERROR_PACKAGE_DOWNLOAD_FAILED
        dialog_primary = enums.get_error_string_from_enum(trans.error_code)
        dialog_secondary = enums.get_error_description_from_enum(trans.error_code)
        dialog_details = trans.error_details
        dialogs.error(
            None, 
            dialog_primary,
            dialog_secondary,
            dialog_details)

    def _on_trans_finished(self, trans, enum):
        """callback when a aptdaemon transaction finished"""
        self._logger.debug("_on_transaction_finished: %s %s %s" % (
                trans, enum, trans.meta_data))

        # show error
        if enum == enums.EXIT_FAILED:
            if not "sc_add_repo_and_install_ignore_errors" in trans.meta_data:
                self._show_transaction_failed_dialog(trans, enum)

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
            if enum == enums.EXIT_SUCCESS:
                self.update_xapian_index()
            self.emit("reload-finished", trans, enum != enums.EXIT_FAILED)
        # send appropriate signals
        self.inject_fake_transactions_and_emit_changed_signal()
        self.emit("transaction-finished", TransactionFinishedResult(trans, enum))

    @inline_callbacks
    def _config_file_conflict(self, transaction, old, new):
        dia = AptConfigFileConflictDialog(old, new)
        res = dia.run()
        dia.hide()
        dia.destroy()
        # send result to the daemon
        if res == gtk.RESPONSE_YES:
            yield transaction.resolve_config_file_conflict(old, "replace",
                                                           defer=True)
        else:
            yield transaction.resolve_config_file_conflict(old, "keep",
                                                           defer=True)

    @inline_callbacks
    def _medium_required(self, transaction, medium, drive):
        dialog = AptMediumRequiredDialog(medium, drive)
        res = dialog.run()
        dialog.hide()
        if res == gtk.RESPONSE_OK:
            yield transaction.provide_medium(medium, defer=True)
        else:
            yield transaction.cancel(defer=True)

    @inline_callbacks
    def _run_transaction(self, trans, pkgname, appname, iconname,
                         metadata=None):
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
                trans.set_remove_obsoleted_depends(True, defer=True)
                self._progress_signal = trans.connect("progress-changed", self._on_progress_changed)
                self.pending_transactions[pkgname] = TransactionProgress(trans)
            # generic metadata
            if metadata:
                yield trans.set_meta_data(defer=True, **metadata)
            # FIXME: either use get_http_proxy_string_from_libproxy 
            #        (with target url) or eliminate entirely
            # do not set the http proxy by default (#628823)
            if os.environ.get("SOFTWARE_CENTER_USE_GCONF_PROXY"):
                http_proxy = get_http_proxy_string_from_gconf()
                if http_proxy:
                    trans.set_http_proxy(http_proxy, defer=True)
            yield trans.run(defer=True)
        except Exception, error:
            self._on_trans_error(error, pkgname)
            # on error we need to clean the pending purchases
            self._clean_pending_purchases(pkgname)
        # on success the pending purchase is cleaned when the package
        # that was purchased finished installing
        if trans.role == enums.ROLE_INSTALL_PACKAGES:
            self._clean_pending_purchases(pkgname)

    def _clean_pending_purchases(self, pkgname):
        if pkgname and pkgname in self.pending_purchases:
            del self.pending_purchases[pkgname]

    def _on_trans_error(self, error, pkgname=None):
        self._logger.warn("_on_trans_error: %s", error)
        # re-enable the action button again if anything went wrong
        result = TransactionFinishedResult(None, enums.EXIT_FAILED)
        result.pkgname = pkgname

        # clean up pending transactions
        try:
            del self.pending_transactions[pkgname]
        except:
            pass

        self.emit("transaction-stopped", result)
        if isinstance(error, dbus.DBusException):
            name = error.get_dbus_name()
            if name in ["org.freedesktop.PolicyKit.Error.NotAuthorized",
                        "org.freedesktop.DBus.Error.NoReply"]:
                pass
        else:
            self._logger.exception("_on_trans_error")
            #raise error

if __name__ == "__main__":
    #c = client.AptClient()
    #c.remove_packages(["4g8"], remove_unused_dependencies=True)
    backend = AptdaemonBackend()
    backend.reload()

