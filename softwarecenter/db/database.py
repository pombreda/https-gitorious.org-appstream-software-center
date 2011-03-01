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
from softwarecenter.paths import XAPIAN_BASE_PATH_SOFTWARE_CENTER_AGENT
from gettext import gettext as _

class SearchQuery(list):
    """ a list wrapper for a search query. it can take a search string
        or a list of search strings

        It provides __eq__ to easily compare two search query lists
    """
    def __init__(self, query_string_or_list):
        if query_string_or_list is None:
            pass
        # turn single querries into a single item list
        elif isinstance(query_string_or_list, xapian.Query):
            self.append(query_string_or_list)
        else:
            self.extend(query_string_or_list)
    def __eq__(self, other):
        # turn single querries into a single item list
        if  isinstance(other, xapian.Query):
            other = [other]
        q1 = [str(q) for q in self]
        q2 = [str(q) for q in other]
        return q1 == q2
    def __ne__(self, other):
        return not self.__eq__(other)
    def __repr__(self):
        return "[%s]" % ",".join([str(q) for q in self])

# class LocaleSorter(xapian.KeyMaker)
#   ubuntu maverick does not have the KeyMakter yet, maintain compatibility
#   for now by falling back to the old xapian.Sorter
try:
    parentClass = xapian.KeyMaker
except AttributeError:
    parentClass = xapian.Sorter
class LocaleSorter(parentClass):
    """ Sort in a locale friendly way by using locale.xtrxfrm """
    def __init__(self, db):
        super(LocaleSorter, self).__init__()
        self.db = db
    def __call__(self, doc):
        return locale.strxfrm(doc.get_value(self.db._axi_values["display_name"]))


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
        self.nr_databases = 0
        if use_axi:
            try:
                axi = xapian.Database("/var/lib/apt-xapian-index/index")
                self.xapiandb.add_database(axi)
                self._axi_values = parse_axi_values_file()
                self.nr_databases += 1
            except:
                self._logger.exception("failed to add apt-xapian-index")
        if use_agent:
            try:
                sca = xapian.Database(XAPIAN_BASE_PATH_SOFTWARE_CENTER_AGENT)
                self.xapiandb.add_database(sca)
                self.nr_databases += 1
            except Exception as e:
                logging.warn("failed to add sca db %s" % e)
        # additional dbs
        for db in self._additional_databases:
            self.xapiandb.add_database(db)
            self.nr_databases += 1
        # parser etc
        self.xapian_parser = xapian.QueryParser()
        self.xapian_parser.set_database(self.xapiandb)
        self.xapian_parser.add_boolean_prefix("pkg", "XP")
        self.xapian_parser.add_boolean_prefix("pkg", "AP")
        self.xapian_parser.add_boolean_prefix("mime", "AM")
        self.xapian_parser.add_boolean_prefix("section", "XS")
        self.xapian_parser.add_boolean_prefix("origin", "XOC")
        self.xapian_parser.add_prefix("pkg_wildcard", "XP")
        self.xapian_parser.add_prefix("pkg_wildcard", "AP")
        self.xapian_parser.set_default_op(xapian.Query.OP_AND)
        self.emit("open", self._db_pathname)

    def add_database(self, database):
        self._additional_databases.append(database)
        self.xapiandb.add_database(database)

    def del_database(self, database):
        self._additional_databases.remove(database)

    def schema_version(self):
        """Return the version of the database layout
        
           This is useful to ensure we force a rebuild if its
           older than what we expect
        """
        return self.xapiandb.get_metadata("db-schema-version")

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
            return SearchQuery(xapian.Query())
        # we cheat and return a match-all query for single letter searches
        if len(search_term) < 2:
            return SearchQuery(_add_category_to_query(xapian.Query("")))

        # check if there is a ":" in the search, if so, it means the user
        # is using a xapian prefix like "pkg:" or "mime:" and in this case
        # we do not want to alter the search term (as application is in the
        # greylist but a common mime-type prefix)
        if not ":" in search_term:
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
            return SearchQuery(map(_add_category_to_query, queries))

        # get a pkg query
        pkg_query = xapian.Query()
        for term in search_term.split():
            pkg_query = xapian.Query(xapian.Query.OP_OR,
                                     xapian.Query("XP"+term),
                                     pkg_query)
        pkg_query = _add_category_to_query(pkg_query)

        # get a search query
        if not ':' in search_term: # ie, not a mimetype query
            # we need this to work around xapian oddness
            search_term = search_term.replace('-','_')
        fuzzy_query = self.xapian_parser.parse_query(search_term, 
                                               xapian.QueryParser.FLAG_PARTIAL|
                                               xapian.QueryParser.FLAG_BOOLEAN)
        # if the query size goes out of hand, omit the FLAG_PARTIAL
        # (LP: #634449)
        if fuzzy_query.get_length() > 1000:
            fuzzy_query = self.xapian_parser.parse_query(search_term, 
                                            xapian.QueryParser.FLAG_BOOLEAN)
        # now add categories
        fuzzy_query = _add_category_to_query(fuzzy_query)
        return SearchQuery([pkg_query,fuzzy_query])

    def get_spelling_correction(self, search_term):
        # get a search query
        if not ':' in search_term: # ie, not a mimetype query
            # we need this to work around xapian oddness
            search_term = search_term.replace('-','_')
        query = self.xapian_parser.parse_query(
            search_term, xapian.QueryParser.FLAG_SPELLING_CORRECTION)
        return self.xapian_parser.get_corrected_query_string()

    def get_most_popular_applications_for_mimetype(self, mimetype, 
                                                  only_uninstalled=True, num=3):
        """ return a list of the most popular applications for the given
            mimetype 
        """
        # sort by popularity by default
        enquire = xapian.Enquire(self.xapiandb)
        enquire.set_sort_by_value_then_relevance(XAPIAN_VALUE_POPCON)
        # query mimetype
        query = xapian.Query("AM%s"%mimetype)
        enquire.set_query(query)
        # mset just needs to be "big enough""
        matches = enquire.get_mset(0, 100)
        apps = []
        for match in matches:
            doc = match.document
            app = Application(self.get_appname(doc),self.get_pkgname(doc),
                              popcon=self.get_popcon(doc))
            if only_uninstalled:
                if app.get_details(self).pkg_state == PKG_STATE_UNINSTALLED:
                    apps.append(app)
            else:
                apps.append(app)
            if len(apps) == num:
                break
        return apps

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
        return summary

    def get_pkgname(self, doc):
        """ Return a packagename from a xapian document """
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        # if there is no value it means we use the apt-xapian-index 
        # that stores the pkgname in the data field or as a value
        if not pkgname:
            # the doc says that get_value() is quicker than get_data()
            # so we use that if we have a updated DB, otherwise
            # fallback to the old way (the xapian DB may not yet be rebuild)
            if "pkgname" in self._axi_values:
                pkgname = doc.get_value(self._axi_values["pkgname"])
            else:
                pkgname = doc.get_data()
        return pkgname

    def get_appname(self, doc):
        """ Return a appname from a xapian document, or None if
            a value for appname cannot be found in the document
         """
        return doc.get_value(XAPIAN_VALUE_APPNAME)

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

    def get_apps_for_pkgname(self, pkgname):
        """ Return set of docids with the matching applications for the
            given pkgname """
        result = set()
        for m in self.xapiandb.postlist("AP"+pkgname):
            result.add(m.docid)
        return result
        
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

    def get_installed_purchased_packages(self):
        """ return a set() of packagenames of purchased apps that are
            currently installed 
        """
        for_purchase_query = xapian.Query(
            "AH" + AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME)
        enquire = xapian.Enquire(self.xapiandb)
        enquire.set_query(for_purchase_query)
        matches = enquire.get_mset(0, self.xapiandb.get_doccount())
        installed_purchased_packages = set()
        for m in matches:
            pkgname = self.get_pkgname(m.document)
            if (pkgname in self.cache and
                self.cache[pkgname].is_installed):
                installed_purchased_packages.add(pkgname)
        return installed_purchased_packages

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
    
