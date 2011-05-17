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
import cPickle
import gio
import glib
import glob
import gzip
import os.path
import re
import logging
import string
import datetime

from datetime import datetime

LOG = logging.getLogger(__name__)

from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.utils import ExecutionTime

def ascii_lower(key):
    ascii_trans_table = string.maketrans(string.ascii_uppercase,
                                        string.ascii_lowercase)
    return key.translate(ascii_trans_table)

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
            # we use ascii_lower for issues described in LP: #581207
            attr = ascii_lower(k)
            if k in sec:
                value = map(self._fixup_history_item, sec[k].split("),"))
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
    def __cmp__(self, other):
        return cmp(self.start_date, other.start_date)
    @staticmethod
    def _fixup_history_item(s):
        """ strip history item string and add missing ")" if needed """
        s=s.strip()
        # remove the infomation about the architecture
        s = re.sub(":\w+", "", s)
        if "(" in s and not s.endswith(")"):
            s+=")"
        return s
               
class AptHistory(object):

    def __init__(self, use_cache=True):
        LOG.debug("AptHistory.__init__()")
        self.main_context = glib.main_context_default()
        self.history_file = apt_pkg.config.find_file("Dir::Log::History")
        #Copy monitoring of history file changes from historypane.py
        self.logfile = gio.File(self.history_file)
        self.monitor = self.logfile.monitor_file()
        self.monitor.connect("changed", self._on_apt_history_changed)
        self.update_callback = None
        LOG.debug("init history")
        # this takes a long time, run it in the idle handler
        self.transactions = []
        self.history_ready = False
        glib.idle_add(self.rescan, use_cache)

    def _mtime_cmp(self, a, b):
        return cmp(os.path.getmtime(a), os.path.getmtime(b))

    def rescan(self, use_cache=True):
        self.history_ready = False
        self.transactions = []
        p = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "apthistory.p")
        cachetime = 0
        if os.path.exists(p) and use_cache:
            with ExecutionTime("loading pickle cache"):
                try:
                    self.transactions = cPickle.load(open(p))
                    cachetime = os.path.getmtime(p)
                except:
                    LOG.exception("failed to load cache")
        for history_gz_file in sorted(glob.glob(self.history_file+".*.gz"),
                                      cmp=self._mtime_cmp):
            if os.path.getmtime(history_gz_file) < cachetime:
                LOG.debug("skipping already cached '%s'" % history_gz_file)
                continue
            self._scan(history_gz_file)
        self._scan(self.history_file)
        if use_cache:
            cPickle.dump(self.transactions, open(p, "w"))
        self.history_ready = True
    
    def _scan(self, history_file, rescan = False):
        LOG.debug("_scan: %s (%s)" % (history_file, rescan))
        try:
            tagfile = apt_pkg.TagFile(open(history_file))
        except (IOError, SystemError), ioe:
            LOG.debug(ioe)
            return
        for stanza in tagfile:
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
                trans.start_date <= self.transactions[0].start_date):
                continue
            # add it
            # FIXME: this is a list, so potentially slow, but its sorted
            #        so we could (and should) do a binary search
            if not trans in self.transactions:
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
    """ get the global AptHistory() singleton object """
    global apt_history
    if apt_history is None:
        apt_history = AptHistory()
    return apt_history

