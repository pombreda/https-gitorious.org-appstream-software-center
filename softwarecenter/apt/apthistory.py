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


import apt
import apt_pkg
import gio
import glib
import glob
import gzip
import string
import datetime
import logging

from datetime import datetime

from debian_bundle import deb822

class Transaction(object):
    """ Represents an apt transaction 

o    Attributes:
    - 'start_date': the start date/time of the transaction as datetime
    - 'install', 'upgrade', 'downgrade', 'remove', 'purge':
        contain the list of packagenames affected by this action
    """

    PKGACTIONS=["Install", "Upgrade", "Downgrade", "Remove", "Purge"]

    def __init__(self, sec):
        self.start_date = datetime.strptime(sec["Start-Date"],
                                            "%Y-%m-%d  %H:%M:%S")
        # set the object attributes "install", "upgrade", "downgrade",
        #                           "remove", "purge", error
        for k in self.PKGACTIONS+["Error"]:
            attr = k.lower()
            if k in sec:
                value = map(string.strip, sec[k].split("),"))
            else:
                value = []
            setattr(self, attr, value)
    def __len__(self):
        count=0
        for k in self.PKGACTIONS:
            count += len(getattr(self, k.lower()))
        return count
    def __repr__(self):
        return ('<Transaction: start_date:%s install:%s upgrade:%s downgrade:%s remove:%s purge:%s' % (self.start_date, self.install, self.upgrade, self.downgrade, self.remove, self.purge))
               
class AptHistory(object):

    def __init__(self):
        self.main_context = glib.main_context_default()
        self.history_file = apt_pkg.config.find_file("Dir::Log::History")
        self.rescan()
        #Copy monitoring of history file changes from historypane.py
        self.logfile = gio.File(self.history_file)
        self.monitor = self.logfile.monitor_file()
        self.monitor.connect("changed", self._on_apt_history_changed)
        self.update_callback = None

    def rescan(self):
        self.transactions = []
        for history_gz_file in glob.glob(self.history_file+".*.gz"):
            self._scan(history_gz_file)
        self._scan(self.history_file)
    
    def _scan(self, history_file, rescan = False):
        try:
            if history_file.endswith(".gz"):
                f = gzip.open(history_file)
            else:
                f = open(history_file)
        except IOError, ioe:
            logging.debug(ioe)
            return
        for stanza in deb822.Deb822.iter_paragraphs(f):
            # keep the UI alive
            while self.main_context.pending():
                self.main_context.iteration()
            # ignore records with 
            try:
                trans = Transaction(stanza)
            except KeyError, e:
                continue
            # ignore the ones we have already
            if (rescan and
                len(self.transactions) > 0 and
                trans.start_date < self.transactions[0].start_date):
                break
            # add it
            self.transactions.insert(0, trans)
            
    def _on_apt_history_changed(self, monitor, afile, other_file, event):
        if event == gio.FILE_MONITOR_EVENT_CHANGES_DONE_HINT:
            self._scan(self.history_file, rescan = True)
            if self.update_callback:
                self.update_callback()
    
    def set_on_update(self,update_callback):
        self.update_callback=update_callback
            
    def get_installed_date(self, pkg_name):
        installed_date = None
        for trans in self.transactions:
            for pkg in trans.install:
                if pkg.split(" ")[0] == pkg_name:
                    installed_date = trans.start_date
                    return installed_date
        return installed_date
    
    def _find_in_terminal_log(self, date, term_file):
        found = False
        term_lines = []
        for line in term_file:
            if line.startswith("Log started: %s" % date):
                found = True
            elif line.endswith("Log ended") or line.startswith("Log started"):
                found = False
            if found:
                term_lines.append(line)
        return term_lines

    def find_terminal_log(self, date):
        """Find the terminal log part for the given transaction
           (this can be rather slow)
        """
        # FIXME: try to be more clever here with date/file timestamps
        term = apt_pkg.config.find_file("Dir::Log::Terminal")
        term_lines = self._find_in_terminal_log(date, open(term))
        # now search the older history
        if not term_lines:
            for f in glob.glob(term+".*.gz"):
                term_lines = self._find_in_terminal_log(date, gzip.open(f))
                if term_lines:
                    return term_lines
        return term_lines

# make it a singleton
apt_history = None
def get_apt_history():
    global apt_history
    if apt_history is None:
        apt_history = AptHistory()
    return apt_history
