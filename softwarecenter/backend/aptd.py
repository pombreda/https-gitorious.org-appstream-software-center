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

import gobject
import os
import logging

from aptdaemon import policykit1
from aptdaemon import client
from aptdaemon import enums
from aptdaemon.gtkwidgets import AptMediumRequiredDialog

from softwarecenter.utils import get_http_proxy_string_from_gconf

class AptdaemonBackend(gobject.GObject):
    """ software center specific code that interacts with aptdaemon """

    __gsignals__ = {'transaction-finished':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            (bool,)),
                    'transaction-stopped':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            ()),                    
                    }

    def __init__(self):
        gobject.GObject.__init__(self)
        self.aptd_client = client.AptClient()

    # public methods
    def upgrade(self, pkgname, appname, iconname):
        trans = self.aptd_client.upgrade_packages([pkgname],
                                          exit_handler=self._on_trans_finished)
        self._run_transaction(trans, pkgname, appname, iconname)

    def remove(self, pkgname, appname, iconname):
        trans = self.aptd_client.remove_packages([pkgname],
                                          exit_handler=self._on_trans_finished)
        self._run_transaction(trans, pkgname, appname, iconname)

    def install(self, pkgname, appname, iconname):
        trans = self.aptd_client.install_packages([pkgname],
                                          exit_handler=self._on_trans_finished)
        self._run_transaction(trans, pkgname, appname, iconname)

    def enable_channel(self, channelfile):
        import aptsources.sourceslist

        # read channel file and add all relevant lines
        for line in open(channelfile):
            line = line.strip()
            if not line:
                continue
            entry = aptsources.sourceslist.SourceEntry(line)
            if entry.invalid:
                continue
            sourcepart = os.path.basename(channelfile)
            try:
                self.aptd_client.add_repository(
                    entry.type, entry.uri, entry.dist, entry.comps,
                    "Added by software-center", sourcepart)
            except dbus.exceptions.DBusException, e:
                if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                    return
        trans = self.aptd_client.update_cache(
            exit_handler=self._on_trans_finished)
        self._run_transaction(trans, None, None, None)

    # internal helpers
    def _on_trans_reply(self):
        # dummy callback for now, but its required, otherwise the aptdaemon
        # client blocks the UI and keeps gtk from refreshing
        logging.debug("_on_trans_reply")

    def _on_trans_error(self, error):
        logging.warn("_on_trans_error: %s" % error)
        # re-enable the action button again if anything went wrong
        if (error._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized" or
            error._dbus_error_name == "org.freedesktop.DBus.Error.NoReply"):
            pass
        else:
            raise
        self.emit("transaction-stopped")

    def _on_trans_finished(self, trans, enum):
        """callback when a aptdaemon transaction finished"""
        if enum == enums.EXIT_FAILED:
            excep = trans.get_error()
            # daemon died are messages that result from broken
            # cancel handling in aptdaemon (LP: #440941)
            # FIXME: this is not a proper fix, just a workaround
            if excep.code == enums.ERROR_DAEMON_DIED:
                logging.warn("daemon dies, ignoring: %s" % excep)
            else:
                msg = "%s: %s\n%s\n\n%s" % (
                    _("ERROR"),
                    enums.get_error_string_from_enum(excep.code),
                    enums.get_error_description_from_enum(excep.code),
                    excep.details)
                logging.error("error in _on_trans_finished '%s'" % msg)
                # show dialog to the user and exit (no need to reopen
                # the cache)
                dialogs.error(None,
                              enums.get_error_string_from_enum(excep.code),
                              enums.get_error_description_from_enum(excep.code),
                              excep.details)
        # send finished signal
        self.emit("transaction-finished", enum != enums.EXIT_FAILED)

    # FIXME: move this to a better place
    def _get_diff(self, old, new):
        if not os.path.exists("/usr/bin/diff"):
            return ""
        diff = subprocess.Popen(["/usr/bin/diff",
                                 "-u",
                                 old, new],
                                stdout=subprocess.PIPE).communicate()[0]
        return diff

    # FIXME: move this into aptdaemon/use the aptdaemon one
    def _config_file_prompt(self, transaction, old, new):
        diff = self._get_diff(old, new)
        d = dialogs.DetailsMessageDialog(None,
                                         details=diff,
                                         type=gtk.MESSAGE_INFO,
                                         buttons=gtk.BUTTONS_NONE)
        d.add_buttons(_("_Keep"), gtk.RESPONSE_NO,
                      _("_Replace"), gtk.RESPONSE_YES)
        d.set_default_response(gtk.RESPONSE_NO)
        text = _("Configuration file '%s' changed") % old
        desc = _("Do you want to use the new version?")
        d.set_markup("<big><b>%s</b></big>\n\n%s" % (text, desc))
        res = d.run()
        d.destroy()
        # send result to the daemon
        if res == gtk.RESPONSE_YES:
            transaction.config_file_prompt_answer(old, "replace")
        else:
            transaction.config_file_prompt_answer(old, "keep")

    def _medium_required(self, transaction, medium, drive):
        dialog = AptMediumRequiredDialog(medium, drive)
        res = dialog.run()
        dialog.hide()
        if res == gtk.RESPONSE_OK:
            transaction.provide_medium(medium)
        else:
            transaction.cancel()

    def _setup_http_proxy(self, transaction):
        http_proxy = get_http_proxy_string_from_gconf()
        if http_proxy:
            transaction.set_http_proxy(http_proxy)

    def _run_transaction(self, trans, pkgname, appname, iconname):
        # set object data
        trans.set_data("appname", appname)
        trans.set_data("iconname", iconname)
        trans.set_data("pkgname", pkgname)
        # setup http proxy
        self._setup_http_proxy(trans)
        # we support debconf
        trans.set_debconf_frontend("gnome")
        trans.connect("config-file-prompt", self._config_file_prompt)
        trans.connect("medium-required", self._medium_required)
        trans.run(error_handler=self._on_trans_error,
                  reply_handler=self._on_trans_reply)



