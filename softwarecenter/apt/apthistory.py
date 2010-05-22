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
import glob
import gzip
import string
import datetime
import gio

from debian_bundle import deb822

class Transaction(object):
    
    PKGACTIONS=["Install", "Upgrade", "Downgrade" "Remove", "Purge"]

    def __init__(self, sec):
        self.start_date = sec["Start-Date"]
        for k in self.PKGACTIONS+["Error"]:
            if k in sec:
                setattr(self, k.lower(), map(string.strip, sec[k].split(",")))
            else:
                setattr(self, k.lower(), [])
    def __len__(self):
        count=0
        for k in self.PKGACTIONS:
            count += len(getattr(self, k.lower()))
        return count
               
class AptHistory(object):

    def __init__(self):
        self.history_file = apt_pkg.config.find_file("Dir::Log::History")
        self.rescan()
        #Copy monitoring of history file changes from historypane.py
        self.logfile = gio.File(self.history_file)
        self.monitor = self.logfile.monitor_file()
        self.monitor.connect("changed", self._on_apt_history_changed)
    
    def rescan(self):
        self.transactions = []
        for history_gz_file in glob.glob(self.history_file+".*.gz"):
            self._scan(history_gz_file)
        self._scan(self.history_file)
    
    def _scan(self, history_file):
        if history_file.endswith(".gz"):
            f = gzip.open(history_file)
        else:
            f = open(history_file)
        for stanza in deb822.Deb822.iter_paragraphs(f):
            trans = Transaction(stanza)
            self.transactions.insert(0, trans)
            
    # FIXME: Scan only recent logs.
    def _on_apt_history_changed(self, monitor, afile, other_file, event):
        if event == gio.FILE_MONITOR_EVENT_CHANGES_DONE_HINT:
            self.rescan()
            
    def get_installed_date(self, pkg_name):
        installed_date = None
        for trans in self.transactions:
            for pkg in trans.install:
                if pkg.split(" ")[0] == pkg_name:
                    installed_date = trans.start_date
                    return datetime.datetime.strptime(installed_date,"%Y-%m-%d  %H:%M:%S")
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

    # TODO:
    #  def find_terminal_log(self, date)
    #  def rescan(self, scan_all_parts=True)
