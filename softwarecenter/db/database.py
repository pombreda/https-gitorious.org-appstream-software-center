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
import os
import re
import string
import xapian
from softwarecenter.db.application import Application

from softwarecenter.utils import *
from softwarecenter.enums import *
from gettext import gettext as _

def parse_axi_values_file(filename="/var/lib/apt-xapian-index/values"):
    """ parse the apt-xapian-index "values" file and provide the 
    information in the self._axi_values dict
    """
    axi_values = {}
    if not os.path.exists(filename):
        return
    for raw_line in open(filename):
        line = string.split(raw_line, "#", 1)[0]
        if line.strip() == "":
            continue
        (key, value) = line.split()
        axi_values[key] = int(value)
    return axi_values

class StoreDatabase(gobject.GObject):
    """thin abstraction for the xapian database with convenient functions"""

    # TRANSLATORS: List of "grey-listed" words sperated with ";"
    # Do not translate this list directly. Instead,
    # provide a list of words in your language that people are likely
    # to include in a search but that should normally be ignored in
    # the search.
    SEARCH_GREYLIST_STR = _("app;application;package;program;programme;"
                            "suite;tool")

    # signal emited
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
        self._additional_databases = []

        # the xapian values as read from /var/lib/apt-xapian-index/values
        self._axi_values = {}
        self._logger = logging.getLogger("softwarecenter.db")

    def open(self, pathname=None, use_axi=True, use_agent=True):
        " open the database "
        if pathname:
            self._db_pathname = pathname
        self.xapiandb = xapian.Database(self._db_pathname)
        # add the apt-xapian-database for here (we don't do this
        # for now as we do not have a good way to integrate non-apps
        # with the UI)
        if use_axi:
            try:
                axi = xapian.Database("/var/lib/apt-xapian-index/index")
                self.xapiandb.add_database(axi)
                self._axi_values = parse_axi_values_file()
            except:
                self._logger.exception("failed to add apt-xapian-index")
        if use_agent:
            try:
                sca = xapian.Database(XAPIAN_BASE_PATH_SOFTWARE_CENTER_AGENT)
                self.xapiandb.add_database(sca)
            except Exception as e:
                logging.warn("failed to add sca db %s" % e)
        # additional dbs
        for db in self._additional_databases:
            self.xapiandb.add_database(db)
        # parser etc
        self.xapian_parser = xapian.QueryParser()
        self.xapian_parser.set_database(self.xapiandb)
        self.xapian_parser.add_boolean_prefix("pkg", "XP")
        self.xapian_parser.add_boolean_prefix("pkg", "AP")
        self.xapian_parser.add_prefix("pkg_wildcard", "XP")
        self.xapian_parser.add_prefix("pkg_wildcard", "AP")
        self.xapian_parser.set_default_op(xapian.Query.OP_AND)
        self.emit("open", self._db_pathname)

    def add_database(self, database):
        self._additional_databases.append(database)
        self.xapiandb.add_database(database)

    def del_database(self, database):
        self._additional_databases.remove(database)

    def reopen(self):
        " reopen the database "
        self.open()
        self.emit("reopen")

    @property
    def popcon_max(self):
        popcon_max = xapian.sortable_unserialise(self.xapiandb.get_metadata("popcon_max_desktop"))
        assert popcon_max > 0
        return popcon_max

    def _comma_expansion(self, search_term):
        """do expansion of "," in a search term, see
        https://wiki.ubuntu.com/SoftwareCenter?action=show&redirect=SoftwareStore#Searching%20for%20multiple%20package%20names
        """
        # expand "," to APpkgname AND
        # (ignore trailing comma)
        search_term = search_term.rstrip(",")
        if "," in search_term:
            queries = []
            added = set()
            for pkgname in search_term.split(","):
                pkgname = pkgname.lower()
                # double comma, ignore term
                if not pkgname:
                    continue
                # not a pkgname, return
                if not re.match("[0-9a-z\.\-]+", pkgname):
                    return None
                # only add if not there already
                if pkgname not in added:
                    added.add(pkgname)
                    queries.append(xapian.Query("AP"+pkgname))
            return queries
        return None

    def get_query_list_from_search_entry(self, search_term, category_query=None):
        """ get xapian.Query from a search term string and a limit the
            search to the given category
        """
        def _add_category_to_query(query):
            """ helper that adds the current category to the query"""
            if not category_query:
                return query
            return xapian.Query(xapian.Query.OP_AND, 
                                category_query,
                                query)
        # empty query returns a query that matches nothing (for performance
        # reasons)
        if search_term == "" and category_query is None:
            return xapian.Query()
        # we cheat and return a match-all query for single letter searches
        if len(search_term) < 2:
            return _add_category_to_query(xapian.Query(""))

        # filter query by greylist (to avoid overly generic search terms)
        orig_search_term = search_term
        for item in self.SEARCH_GREYLIST_STR.split(";"):
            (search_term, n) = re.subn('\\b%s\\b' % item, '', search_term)
            if n: 
                self._logger.debug("greylist changed search term: '%s'" % search_term)
        # restore query if it was just greylist words
        if search_term == '':
            self._logger.debug("grey-list replaced all terms, restoring")
            search_term = orig_search_term
        
        # check if we need to do comma expansion instead of a regular
        # query
        queries = self._comma_expansion(search_term)
        if queries:
            return map(_add_category_to_query, queries)

        # get a pkg query
        pkg_query = xapian.Query()
        for term in search_term.split():
            pkg_query = xapian.Query(xapian.Query.OP_OR,
                                     xapian.Query("XP"+term),
                                     pkg_query)
        pkg_query = _add_category_to_query(pkg_query)

        # get a search query
        fuzzy_query = self.xapian_parser.parse_query(search_term, 
                                               xapian.QueryParser.FLAG_PARTIAL|
                                               xapian.QueryParser.FLAG_BOOLEAN)
        fuzzy_query = _add_category_to_query(fuzzy_query)
        return [pkg_query,fuzzy_query]

    def get_summary(self, doc):
        """ get human readable summary of the given document """
        summary = doc.get_value(XAPIAN_VALUE_SUMMARY)
        channel = doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
        # if we do not have the summary in the xapian db, get it
        # from the apt cache
        if not summary and self._aptcache.ready: 
            pkgname = self.get_pkgname(doc)
            if (pkgname in self._aptcache and 
                self._aptcache[pkgname].candidate):
                return  self._aptcache[pkgname].candidate.summary
            elif channel:
                # FIXME: print something if available for our arch
                pass
            else:
                return _("Sorry, '%s' is not available for this type of computer (%s).") % (pkgname, get_current_arch())
        return summary

    def get_pkgname(self, doc):
        """ Return a packagename from a xapian document """
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        # if there is no value it means we use the apt-xapian-index 
        # that store the pkgname in the data field directly
        if not pkgname:
            pkgname = doc.get_data()
        return pkgname

    def get_appname(self, doc):
        """ Return a appname from a xapian document """
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        # if there is no value it means we use the apt-xapian-index 
        # and that has no appname
        if not pkgname:
            return None
        return doc.get_data()

    def get_iconname(self, doc):
        """ Return the iconname from the xapian document """
        iconname = doc.get_value(XAPIAN_VALUE_ICON)
        return iconname

    def pkg_in_category(self, pkgname, cat_query):
        """ Return True if the given pkg is in the given category """
        pkg_query1 = xapian.Query("AP"+pkgname)
        pkg_query2 = xapian.Query("XP"+pkgname)
        pkg_query = xapian.Query(xapian.Query.OP_OR, pkg_query1, pkg_query2)
        pkg_and_cat_query = xapian.Query(xapian.Query.OP_AND, pkg_query, cat_query)
        enquire = xapian.Enquire(self.xapiandb)
        enquire.set_query(pkg_and_cat_query)
        matches = enquire.get_mset(0, len(self))
        if matches:
            return True
        return False

        
    def get_icon_needs_download(self, doc):
        """ Return a value if the icon needs to be downloaded """
        return doc.get_value(XAPIAN_VALUE_ICON_NEEDS_DOWNLOAD)

    def get_popcon(self, doc):
        """ Return a popcon value from a xapian document """
        popcon_raw = doc.get_value(XAPIAN_VALUE_POPCON)
        if popcon_raw:
            popcon = xapian.sortable_unserialise(popcon_raw)
        else:
            popcon = 0
        return popcon

    def get_xapian_document(self, appname, pkgname):
        """ Get the machting xapian document for appname, pkgname
        
        If no document is found, raise a IndexError
        """
        #self._logger.debug("get_xapian_document app='%s' pkg='%s'" % (appname,pkgname))
        # first search for appname in the app-install-data namespace
        for m in self.xapiandb.postlist("AA"+appname):
            doc = self.xapiandb.get_document(m.docid)
            if doc.get_value(XAPIAN_VALUE_PKGNAME) == pkgname:
                return doc
        # then search for pkgname in the app-install-data namespace
        for m in self.xapiandb.postlist("AP"+pkgname):
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

    def __iter__(self):
        """ support iterating over the documents """
        for it in self.xapiandb.postlist(""):
            doc = self.xapiandb.get_document(it.docid)
            yield doc

if __name__ == "__main__":
    import apt
    import sys

    db = StoreDatabase("/var/cache/software-center/xapian", apt.Cache())
    db.open()
    if len(sys.argv) < 2:
        search = "apt,apport"
    else:
        search = sys.argv[1]
    query = db.get_query_list_from_search_entry(search)
    print query
    enquire = xapian.Enquire(db.xapiandb)
    enquire.set_query(query)
    matches = enquire.get_mset(0, len(db))
    for m in matches:
        doc = m.document
        print doc.get_data()

    # test origin
    query = xapian.Query("XOL"+"Ubuntu")
    enquire = xapian.Enquire(db.xapiandb)
    enquire.set_query(query)
    matches = enquire.get_mset(0, len(db))
    print "Ubuntu origin: ", len(matches)
    
