#!/usr/bin/python
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
import glib
import logging
import os
import simplejson
import string
import sys
import time
import urllib
import xapian

from ConfigParser import RawConfigParser, NoOptionError
from gettext import gettext as _
from glob import glob


from softwarecenter.enums import *
from softwarecenter.utils import GnomeProxyURLopener

# weights for the different fields
WEIGHT_DESKTOP_NAME = 10
WEIGHT_DESKTOP_KEYWORD = 5
WEIGHT_DESKTOP_GENERICNAME = 3
WEIGHT_DESKTOP_COMMENT = 1

WEIGHT_APT_PKGNAME = 8
WEIGHT_APT_SUMMARY = 5
WEIGHT_APT_DESCRIPTION = 1

from locale import getdefaultlocale
import gettext

# some globals (FIXME: that really need to go into a new Update class)
popcon_max = 0
seen = set()

class AppInfoParserBase(object):
    """ base class for reading AppInfo meta-data """

    def get_desktop(self, key):
        """ get a AppInfo entry for the given key """
    def has_option_desktop(self, key):
        """ return True if there is a given AppInfo info """
    def get_desktop_categories(self):
        categories = []
        try:
            categories_str = self.get_desktop("Categories")
            for item in categories_str.split(";"):
                if item:
                    categories.append(item)
        except NoOptionError:
            pass
        return categories
    @property
    def desktopf(self):
        """ return the file that the AppInfo comes from """

class SoftwareCenterAgentParser(AppInfoParserBase):
    """ map the data we get from the software-center-agent """

    # map from requested key to sca_entry attribute
    MAPPING = { 'Name'       : 'name',
                'Comment'    : 'description',
                'Price'      : 'price',
                'Package'    : 'package_name',
                'Categories' : 'categories',
                'Channel'    : 'channel',
                'Deb-Line'   : 'deb_line',
                'Signing-Key-Id' : 'signing_key_id',
                'Purchased-Date' : 'purchase_date',
              }

    # map from requested key to a static data element
    STATIC_DATA = { 'Type' : 'Application',
                  }

    def __init__(self, sca_entry):
        self.sca_entry = sca_entry
        self.origin = "software-center-agent"
    def _apply_mapping(self, key):
        # strip away bogus prefixes
        if key.startswith("X-AppInstall-"):
            key = key[len("X-AppInstall-"):]
        if key in self.MAPPING:
            return self.MAPPING[key]
        return key
    def get_desktop(self, key):
        if key in self.STATIC_DATA:
            return self.STATIC_DATA[key]
        return getattr(self.sca_entry, self._apply_mapping(key))
    def has_option_desktop(self, key):
        return (key in self.STATIC_DATA or
                hasattr(self.sca_entry, self._apply_mapping(key)))
    @property
    def desktopf(self):
        return self.origin

class JsonTagSectionParser(AppInfoParserBase):

    MAPPING = { 'Name'       : 'application_name',
                'Comment'    : 'description',
                'Price'      : 'price',
                'Package'    : 'package_name',
                'Categories' : 'categories',
              }

    def __init__(self, tag_section, url):
        self.tag_section = tag_section
        self.url = url
    def _apply_mapping(self, key):
        # strip away bogus prefixes
        if key.startswith("X-AppInstall-"):
            key = key[len("X-AppInstall-"):]
        if key in self.MAPPING:
            return self.MAPPING[key]
        return key
    def get_desktop(self, key):
        return self.tag_section[self._apply_mapping(key)]
    def has_option_desktop(self, key):
        return self._apply_mapping(key) in self.tag_section
    @property
    def desktopf(self):
        return self.url

class DesktopTagSectionParser(AppInfoParserBase):
    def __init__(self, tag_section, tagfile):
        self.tag_section = tag_section
        self.tagfile = tagfile
    def get_desktop(self, key):
        # strip away bogus prefixes
        if key.startswith("X-AppInstall-"):
            key = key[len("X-AppInstall-"):]
        # FIXME: make i18n work similar to get_desktop
        # first try dgettext
        if "Gettext-Domain" in self.tag_section:
            value = self.tag_section.get(key)
            if value:
                domain = self.tag_section["Gettext-Domain"]
                translated_value = gettext.dgettext(domain, value)
                if value != translated_value:
                    return translated_value
        # then try the i18n version of the key (in [de_DE] or
        # [de]) but ignore errors and return the untranslated one then
        try:
            locale = getdefaultlocale(('LANGUAGE','LANG','LC_CTYPE','LC_ALL'))[0]
            if locale:
                if self.has_option_desktop("%s-%s" % (key, locale)):
                    return self.tag_section["%s-%s" % (key, locale)]
                if "_" in locale:
                    locale_short = locale.split("_")[0]
                    if self.has_option_desktop("%s-%s" % (key, locale_short)):
                        return self.tag_section["%s-%s" % (key, locale_short)]
        except ValueError,e :
            pass
        # and then the untranslated field
        return self.tag_section[key]
    def has_option_desktop(self, key):
        # strip away bogus prefixes
        if key.startswith("X-AppInstall-"):
            key = key[len("X-AppInstall-"):]
        return key in self.tag_section
    @property
    def desktopf(self):
        return self.tagfile

class DesktopConfigParser(RawConfigParser, AppInfoParserBase):
    " thin wrapper that is tailored for xdg Desktop files "
    DE = "Desktop Entry"
    def get_desktop(self, key):
        " get generic option under 'Desktop Entry'"
        # first try dgettext
        if self.has_option_desktop("X-Ubuntu-Gettext-Domain"):
            value = self.get(self.DE, key)
            if value:
                domain = self.get(self.DE, "X-Ubuntu-Gettext-Domain")
                translated_value = gettext.dgettext(domain, value)
                if value != translated_value:
                    return translated_value
        # then try the i18n version of the key (in [de_DE] or
        # [de]) but ignore errors and return the untranslated one then
        try:
            locale = getdefaultlocale(('LANGUAGE','LANG','LC_CTYPE','LC_ALL'))[0]
            if locale:
                if self.has_option_desktop("%s[%s]" % (key, locale)):
                    return self.get(self.DE, "%s[%s]" % (key, locale))
                if "_" in locale:
                    locale_short = locale.split("_")[0]
                    if self.has_option_desktop("%s[%s]" % (key, locale_short)):
                        return self.get(self.DE, "%s[%s]" % (key, locale_short))
        except ValueError,e :
            pass
        # and then the untranslated field
        return self.get(self.DE, key)
    def has_option_desktop(self, key):
        " test if there is the option under 'Desktop Entry'"
        return self.has_option(self.DE, key)
    def read(self, filename):
        self._filename = filename
        RawConfigParser.read(self, filename)
    @property
    def desktopf(self):
        return self._filename

def ascii_upper(key):
    """Translate an ASCII string to uppercase
    in a locale-independent manner."""
    ascii_trans_table = string.maketrans(string.ascii_lowercase,
                                         string.ascii_uppercase)
    return key.translate(ascii_trans_table)

def index_name(doc, name, term_generator):
    """ index the name of the application """
    doc.add_value(XAPIAN_VALUE_APPNAME, name)
    doc.add_term("AA"+name)
    w = globals()["WEIGHT_DESKTOP_NAME"]
    term_generator.index_text_without_positions(name, w)

def update(db, cache, datadir=APP_INSTALL_PATH):
    update_from_app_install_data(db, cache, datadir)
    update_from_var_lib_apt_lists(db, cache)
    # add db global meta-data
    logging.debug("adding popcon_max_desktop '%s'" % popcon_max)
    db.set_metadata("popcon_max_desktop", xapian.sortable_serialise(float(popcon_max)))

def update_from_json_string(db, cache, json_string, origin):
    """ index from a json string, should include origin url (free form string)
    """
    for sec in simplejson.loads(json_string):
        parser = JsonTagSectionParser(sec, origin)
        index_app_info_from_parser(parser, db, cache)
    return True

def update_from_var_lib_apt_lists(db, cache, listsdir=None):
    """ index the files in /var/lib/apt/lists/*AppInfo """
    if not listsdir:
        listsdir = apt_pkg.Config.find_dir("Dir::State::lists")
    context = glib.main_context_default()
    for appinfo in glob("%s/*AppInfo" % listsdir):
        logging.debug("processing %s" % appinfo)
        # process events
        while context.pending():
            context.iteration()
        tagf = apt_pkg.TagFile(open(appinfo))
        for section in tagf:
            parser = DesktopTagSectionParser(section, appinfo)
            index_app_info_from_parser(parser, db, cache)
    return True

def update_from_app_install_data(db, cache, datadir=APP_INSTALL_PATH):
    """ index the desktop files in $datadir/desktop/*.desktop """
    context = glib.main_context_default()
    for desktopf in glob(datadir+"/desktop/*.desktop"):
        logging.debug("processing %s" % desktopf)
        # process events
        while context.pending():
            context.iteration()
        try:
            parser = DesktopConfigParser()
            parser.read(desktopf)
            index_app_info_from_parser(parser, db, cache)
        except Exception, e:
            # Print a warning, no error (Debian Bug #568941)
            logging.warning("error processing: %s %s" % (desktopf, e))
    return True

def add_from_purchased_but_needs_reinstall_data(purchased_but_may_need_reinstall_list, db, cache):
    """Add application that have been purchased but may require a reinstall
    
    This adds a inmemory database to the main db with the special
    PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME channel prefix

    :return: a xapian query to get all the apps that need reinstall
    """
    # magic
    PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME = "for-pay-needs-reinstall"
    db_purchased = xapian.inmemory_open()
    # go over the items we have
    for item in purchased_but_may_need_reinstall_list:
        # FIXME: what to do with duplicated entries? we will end
        #        up with two xapian.Document, one for the for-pay
        #        and one for the availalbe one from s-c-agent
        #try:
        #    db.get_xapian_document(item.name,
        #                           item.package_name)
        #except IndexError:
        #    # item is not in the xapian db
        #    pass
        #else:
        #    # ignore items we already have in the db, ignore
        #    continue
        # index the item
        try:
            # we fake a channel here
            item.channel = PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME
            # and empty category to make the parser happy
            item.categories = ""
            # WARNING: item.name needs to be different than
            #          the item.name in the DB otherwise the DB
            #          gets confused about (appname, pkgname) duplication
            item.name = _("%s (already purchased)") % item.name
            parser = SoftwareCenterAgentParser(item)
            index_app_info_from_parser(parser, db_purchased, cache)
        except Exception, e:
            logging.exception("error processing: %s " % e)
    # add new in memory db to the main db
    db.add_database(db_purchased)
    # return a query
    query = xapian.Query("AH"+PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME)
    return query

def update_from_software_center_agent(db, cache):
    """ update index based on the software-center-agent data """
    def _available_cb(sca, available):
        print "available: ", available
        sca.available = available
    def _error_cb(sca, error):
        logging.warn("error: %s" % error)
        sca.available = []
    from softwarecenter.backend.restfulclient import SoftwareCenterAgent
    sca = SoftwareCenterAgent()
    sca.connect("available", _available_cb)
    sca.connect("error", _error_cb)
    sca.query_available()
    sca.available = None
    context = glib.main_context_default()
    while sca.available is None:
        while context.pending():
            context.iteration()
        time.sleep(0.1)
    for entry in sca.available:
        # process events
        while context.pending():
            context.iteration()
        try:
            parser = SoftwareCenterAgentParser(entry)
            index_app_info_from_parser(parser, db, cache)
        except Exception, e:
            logging.warning("error processing: %s " % e)
    # return true if we have data entries
    return len(sca.available) > 0
        
def index_app_info_from_parser(parser, db, cache):
        term_generator = xapian.TermGenerator()
        doc = xapian.Document()
        term_generator.set_document(doc)
        # app name is the data
        name = parser.get_desktop("Name")
        if name in seen:
            logging.debug("duplicated name '%s' (%s)" % (name, parser.desktopf))
        seen.add(name)
        doc.set_data(name)
        index_name(doc, name, term_generator)
        # check if we should ignore this file
        if parser.has_option_desktop("X-AppInstall-Ignore"):
            ignore = parser.get_desktop("X-AppInstall-Ignore")
            if ignore.strip().lower() == "true":
                logging.debug("X-AppInstall-Ignore found for '%s'" % parser.desktopf)
                return
        # package name
        pkgname = parser.get_desktop("X-AppInstall-Package")
        doc.add_term("AP"+pkgname)
        doc.add_value(XAPIAN_VALUE_PKGNAME, pkgname)
        doc.add_value(XAPIAN_VALUE_DESKTOP_FILE, parser.desktopf)
        # pocket (main, restricted, ...)
        if parser.has_option_desktop("X-AppInstall-Section"):
            archive_section = parser.get_desktop("X-AppInstall-Section")
            doc.add_term("AS"+archive_section)
            doc.add_value(XAPIAN_VALUE_ARCHIVE_SECTION, archive_section)
        # section (mail, base, ..)
        if pkgname in cache and cache[pkgname].candidate:
            section = cache[pkgname].candidate.section
            doc.add_term("AE"+section)
        # channel (third party stuff)
        if parser.has_option_desktop("X-AppInstall-Channel"):
            archive_channel = parser.get_desktop("X-AppInstall-Channel")
            doc.add_term("AH"+archive_channel)
            doc.add_value(XAPIAN_VALUE_ARCHIVE_CHANNEL, archive_channel)
        # singing key (third party)
        if parser.has_option_desktop("X-AppInstall-Signing-Key-Id"):
            keyid = parser.get_desktop("X-AppInstall-Signing-Key-Id")
            doc.add_value(XAPIAN_VALUE_ARCHIVE_SIGNING_KEY_ID, keyid)
        # purchased date
        if parser.has_option_desktop("X-AppInstall-Purchased-Date"):
            date = parser.get_desktop("X-AppInstall-Purchased-Date")
            doc.add_value(XAPIAN_VALUE_PURCHASED_DATE, str(date))
        # deb-line (third party)
        if parser.has_option_desktop("X-AppInstall-Deb-Line"):
            debline = parser.get_desktop("X-AppInstall-Deb-Line")
            doc.add_value(XAPIAN_VALUE_ARCHIVE_DEB_LINE, debline)
        # PPA (third party stuff)
        if parser.has_option_desktop("X-AppInstall-PPA"):
            archive_ppa = parser.get_desktop("X-AppInstall-PPA")
            doc.add_value(XAPIAN_VALUE_ARCHIVE_PPA, archive_ppa)
        # screenshot (for third party)
        if parser.has_option_desktop("X-AppInstall-Screenshot-Url"):
            url = parser.get_desktop("X-AppInstall-Screenshot-Url")
            doc.add_value(XAPIAN_VALUE_SCREENSHOT_URL, url)
        # price (pay stuff)
        if parser.has_option_desktop("X-AppInstall-Price"):
            price = parser.get_desktop("X-AppInstall-Price")
            doc.add_value(XAPIAN_VALUE_PRICE, price)
        # icon
        if parser.has_option_desktop("Icon"):
            icon = parser.get_desktop("Icon")
            doc.add_value(XAPIAN_VALUE_ICON, icon)
        # write out categories
        for cat in parser.get_desktop_categories():
            doc.add_term("AC"+cat.lower())
        # get type (to distinguish between apps and packages
        if parser.has_option_desktop("Type"):
            type = parser.get_desktop("Type")
            doc.add_term("AT"+type.lower())
        # check gettext domain
        if parser.has_option_desktop("X-Ubuntu-Gettext-Domain"):
            domain = parser.get_desktop("X-Ubuntu-Gettext-Domain")
            doc.add_value(XAPIAN_VALUE_GETTEXT_DOMAIN, domain)
        # architecture
        if parser.has_option_desktop("X-AppInstall-Architectures"):
            arches = parser.get_desktop("X-AppInstall-Architectures")
            doc.add_value(XAPIAN_VALUE_ARCHIVE_ARCH, arches)
        # popcon
        # FIXME: popularity not only based on popcon but also
        #        on archive section, third party app etc
        if parser.has_option_desktop("X-AppInstall-Popcon"):
            popcon = float(parser.get_desktop("X-AppInstall-Popcon"))
            # sort_by_value uses string compare, so we need to pad here
            doc.add_value(XAPIAN_VALUE_POPCON, 
                          xapian.sortable_serialise(popcon))
            global popcon_max
            popcon_max = max(popcon_max, popcon)

        # comment goes into the summary data if there is one,
        # other wise we try GenericName and if nothing else,
        # the summary of the package
        if parser.has_option_desktop("Comment"):
            s = parser.get_desktop("Comment")
            doc.add_value(XAPIAN_VALUE_SUMMARY, s)
        elif parser.has_option_desktop("GenericName"):
            s = parser.get_desktop("GenericName")
            if s != name:
                doc.add_value(XAPIAN_VALUE_SUMMARY, s)
        elif pkgname in cache and cache[pkgname].candidate:
            s = cache[pkgname].candidate.summary
            doc.add_value(XAPIAN_VALUE_SUMMARY, s)

        # add packagename as meta-data too
        term_generator.index_text_without_positions(pkgname, WEIGHT_APT_PKGNAME)

        # now add search data from the desktop file
        for key in ["GenericName","Comment"]:
            if not parser.has_option_desktop(key):
                continue
            s = parser.get_desktop(key)
            # we need the ascii_upper here for e.g. turkish locales, see
            # bug #581207
            w = globals()["WEIGHT_DESKTOP_" + ascii_upper(key.replace(" ", ""))]
            term_generator.index_text_without_positions(s, w)
        # add data from the apt cache
        if pkgname in cache and cache[pkgname].candidate:
            s = cache[pkgname].candidate.summary
            term_generator.index_text_without_positions(s, WEIGHT_APT_SUMMARY)
            s = cache[pkgname].candidate.description
            term_generator.index_text_without_positions(s, WEIGHT_APT_DESCRIPTION)
            for origin in cache[pkgname].candidate.origins:
                doc.add_term("XOA"+origin.archive)
                doc.add_term("XOC"+origin.component)
                doc.add_term("XOL"+origin.label)
                doc.add_term("XOO"+origin.origin)
                doc.add_term("XOS"+origin.site)

        # add our keywords (with high priority)
        if parser.has_option_desktop("X-AppInstall-Keywords"):
            keywords = parser.get_desktop("X-AppInstall-Keywords")
            for s in keywords.split(";"):
                if s:
                    term_generator.index_text_without_positions(s, WEIGHT_DESKTOP_KEYWORD)
        # now add it
        db.add_document(doc)

def rebuild_database(pathname):
    cache = apt.Cache(memonly=True)
    # check permission
    if not os.access(pathname, os.W_OK):
        logging.warn("Cannot write to '%s'." % pathname)
        logging.warn("Please check you have the relevant permissions.")
        return False
    # write it
    db = xapian.WritableDatabase(pathname, xapian.DB_CREATE_OR_OVERWRITE)
    update(db, cache)
    # update the mo file stamp for the langpack checks
    mofile = gettext.find("app-install-data")
    if mofile:
        mo_time = os.path.getctime(mofile)
        db.set_metadata("app-install-mo-time", str(mo_time))
    db.flush()
    return True

