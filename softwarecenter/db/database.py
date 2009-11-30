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
import locale
import logging
import xapian
from softwarecenter.enums import *


class Application(object):
    """ a simple data object that contains just appname, pkgname
        and a sort method
    """
    __slots__ = ["appname", "pkgname"]
    def __init__(self, appname, pkgname):
        self.appname = appname
        self.pkgname = pkgname
    @staticmethod
    def apps_cmp(x, y):
        """ sort method for the applications """
        # sort(key=locale.strxfrm) would be more efficient, but its
        # currently broken, see http://bugs.python.org/issue2481
        if x.appname and y.appname:
            return locale.strcoll(x.appname, y.appname)
        else:
            return cmp(x.pkgname, y.pkgname)

class StoreDatabase(gobject.GObject):
    """thin abstraction for the xapian database with convenient functions"""

    __gsignals__ = {"reopen" : (gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                ()),
                    "open" : (gobject.SIGNAL_RUN_FIRST,
                              gobject.TYPE_NONE,
                              (gobject.TYPE_STRING,)),
                    }
    def __init__(self, pathname, cache):
        gobject.GObject.__init__(self)
        self._db_pathname = pathname
        self._aptcache = cache

    def open(self, pathname=None):
        " open the database "
        if pathname:
            self._db_pathname = pathname
        self.xapiandb = xapian.Database(self._db_pathname)
        # add the apt-xapian-database for here (we don't do this
        # for now as we do not have a good way to integrate non-apps
        # with the UI)
        axi = xapian.Database("/var/lib/apt-xapian-index/index")
        self.xapiandb.add_database(axi)
        self.xapian_parser = xapian.QueryParser()
        self.xapian_parser.set_database(self.xapiandb)
        self.xapian_parser.add_boolean_prefix("pkg", "AP")
        self.xapian_parser.set_default_op(xapian.Query.OP_AND)
        self.emit("open", self._db_pathname)

    def reopen(self):
        " reopen the database "
        self.open()
        self.emit("reopen")

    def get_query_from_search_entry(self, search_term):
        """ get xapian.Query from a search term string """
        query = self.xapian_parser.parse_query(search_term, 
                                               xapian.QueryParser.FLAG_PARTIAL|
                                               xapian.QueryParser.FLAG_BOOLEAN)
        # FIXME: expand to add "AA" and "AP" before each search term?
        return query

    def get_summary(self, doc):
        """ get human readable summary of the given document """
        summary = doc.get_value(XAPIAN_VALUE_SUMMARY)
        # if we do not have the summary in the xapian db, get it
        # from the apt cache
        if not summary and self._aptcache.ready: 
            pkgname = self.get_pkgname(doc)
            if (self._aptcache.has_key(pkgname) and 
                self._aptcache[pkgname].candidate):
                return  self._aptcache[pkgname].candidate.summary
        return summary

    def get_pkgname(self, doc):
        """ Return a packagename from a xapian document """
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        # if there is no value it means we use the apt-xapian-index 
        # that store the pkgname in the data field directly
        if not pkgname:
            pkgname = doc.get_data()
        return pkgname

    def get_xapian_document(self, appname, pkgname):
        """ Get the machting xapian document for appname, pkgname
        
        If no document is found, raise a IndexError
        """
        logging.debug("get_xapian_document app='%s' pkg='%s'" % (appname,pkgname))
        # first search for appname in the app-install-data namespace
        for m in self.xapiandb.postlist("AA"+appname):
            doc = self.xapiandb.get_document(m.docid)
            if doc.get_value(XAPIAN_VALUE_PKGNAME) == pkgname:
                return doc
        # then look for matching packages from a-x-i
        for m in self.xapiandb.postlist("XP"+pkgname):
            doc = self.xapiandb.get_document(m.docid)
            return doc
        # no matching document found
        raise IndexError("No app '%s' for '%s' in database" % (appname,pkgname))

    def is_appname_duplicated(self, appname):
        """Check if the given appname is stored multiple times in the db
           This can happen for generic names like "Terminal"
        """
        for (i, m) in enumerate(self.xapiandb.postlist("AA"+appname)):
            if i > 0:
                return True
        return False

    def __len__(self):
        """return the doc count of the database"""
        return self.xapiandb.get_doccount()


