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
import base64
import glib
import logging
import os
import simplejson
import string
import shutil
import sys
import time
import urllib
import xapian


from ConfigParser import RawConfigParser, NoOptionError
from gettext import gettext as _
from glob import glob

from softwarecenter.enums import *
from softwarecenter.enums import DB_SCHEMA_VERSION
from softwarecenter.paths import SOFTWARE_CENTER_ICON_CACHE_DIR
from softwarecenter.db.database import parse_axi_values_file

from locale import getdefaultlocale
import gettext
import cPickle

# weights for the different fields
WEIGHT_DESKTOP_NAME = 10
WEIGHT_DESKTOP_KEYWORD = 5
WEIGHT_DESKTOP_GENERICNAME = 3
WEIGHT_DESKTOP_COMMENT = 1

WEIGHT_APT_PKGNAME = 8
WEIGHT_APT_SUMMARY = 5
WEIGHT_APT_DESCRIPTION = 1

# some globals (FIXME: that really need to go into a new Update class)
popcon_max = 0
seen = set()
LOG = logging.getLogger(__name__)

# init axi
axi_values = parse_axi_values_file()

# get cataloged_times
cataloged_times = {}
CF = "/var/lib/apt-xapian-index/cataloged_times.p"
if os.path.exists(CF):
    cataloged_times = cPickle.load(open(CF))
del CF

class AppInfoParserBase(object):
    """ base class for reading AppInfo meta-data """

    def get_desktop(self, key):
        """ get a AppInfo entry for the given key """
    def has_option_desktop(self, key):
        """ return True if there is a given AppInfo info """
    def _get_desktop_list(self, key, split_str=";"):
        result = []
        try:
            list_str = self.get_desktop(key)
            for item in list_str.split(split_str):
                if item:
                    result.append(item)
        except (NoOptionError, KeyError):
            pass
        return result
    def get_desktop_categories(self):
        return self._get_desktop_list("Categories")
    def get_desktop_mimetypes(self):
        if not self.has_option_desktop("MimeType"):
            return []
        return self._get_desktop_list("MimeType")
    @property
    def desktopf(self):
        """ return the file that the AppInfo comes from """

class SoftwareCenterAgentParser(AppInfoParserBase):
    """ map the data we get from the software-center-agent """

    # map from requested key to sca_entry attribute
    MAPPING = { 'Name'       : 'name',
                'Price'      : 'price',
                'Package'    : 'package_name',
                'Categories' : 'categories',
                'Channel'    : 'channel',
                'Deb-Line'   : 'deb_line',
                'Signing-Key-Id' : 'signing_key_id',
                'Purchased-Date' : 'purchase_date',
                'PPA'        : 'archive_id',
                'Icon'       : 'icon',
                'Screenshot-Url' : 'screenshot_url',
                'Thumbnail-Url' : 'thumbnail_url',
              }

    # map from requested key to a static data element
    STATIC_DATA = { 'Type' : 'Application',
                  }

    def __init__(self, sca_entry):
        self.sca_entry = sca_entry
        self.origin = "software-center-agent"
        self._apply_exceptions()
    def _apply_exceptions(self):
        # map screenshot to thumbnail
        if (hasattr(self.sca_entry, "screenshot_url") and 
            not hasattr(self.sca_entry, "thumbnail_url")):
            url = self.sca_entry.screenshot_url.replace(".png", ".thumb.png")
            self.sca_entry.thumbnail_url = url
        if hasattr(self.sca_entry, "description"):
            self.sca_entry.Comment = self.sca_entry.description.split("\n")[0]
            self.sca_entry.Description = "\n".join(self.sca_entry.description.split("\n")[1:])
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
        # never translate the pkgname
        if key == "X-AppInstall-Package":
            return self.get(self.DE, key)
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
    LOG.debug("adding popcon_max_desktop '%s'" % popcon_max)
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
        LOG.debug("processing %s" % appinfo)
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
        LOG.debug("processing %s" % desktopf)
        # process events
        while context.pending():
            context.iteration()
        try:
            parser = DesktopConfigParser()
            parser.read(desktopf)
            index_app_info_from_parser(parser, db, cache)
        except Exception, e:
            # Print a warning, no error (Debian Bug #568941)
            LOG.warning("error processing: %s %s" % (desktopf, e))
    return True

def add_from_purchased_but_needs_reinstall_data(purchased_but_may_need_reinstall_list, db, cache):
    """Add application that have been purchased but may require a reinstall
    
    This adds a inmemory database to the main db with the special
    PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME channel prefix

    :return: a xapian query to get all the apps that need reinstall
    """
    # magic
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
            LOG.exception("error processing: %s " % e)
    # add new in memory db to the main db
    db.add_database(db_purchased)
    # return a query
    query = xapian.Query("AH"+PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME)
    return query

def update_from_software_center_agent(db, cache, ignore_etag=False):
    """ update index based on the software-center-agent data """
    def _available_cb(sca, available):
        # print "available: ", available
        LOG.debug("available: '%s'" % available)
        sca.available = available
    def _error_cb(sca, error):
        LOG.warn("error: %s" % error)
        sca.available = []
    # use the anonymous interface to s-c-agent, scales much better and is
    # much cache friendlier
    from softwarecenter.backend.restfulclient import SoftwareCenterAgentAnonymous
    sca = SoftwareCenterAgentAnonymous(ignore_etag)
    sca.connect("available", _available_cb)
    sca.connect("error", _error_cb)
    sca.available = None
    sca.query_available()
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
            # magic channel
            entry.channel = AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME
            # icon is transmited inline
            iconname = "sc-agent-%s" % entry.package_name
            icondata = base64.b64decode(entry.icon_data)
            open(os.path.join(SOFTWARE_CENTER_ICON_CACHE_DIR,
                              "%s.png" % iconname),"w").write(icondata)
            entry.icon = iconname
            # now the normal parser
            parser = SoftwareCenterAgentParser(entry)
            index_app_info_from_parser(parser, db, cache)
        except Exception, e:
            LOG.warning("error processing: %s " % e)
    # return true if we have data entries
    return len(sca.available) > 0
        
def index_app_info_from_parser(parser, db, cache):
        term_generator = xapian.TermGenerator()
        term_generator.set_database(db)
        try:
            # this tests if we have spelling suggestions (there must be
            # a better way?!?) - this is needed as inmemory does not have
            # spelling corrections, but it allows setting the flag and will
            # raise a exception much later
            db.add_spelling("test")
            db.remove_spelling("test")
            # this enables the flag for it (we only reach this line if
            # the db supports spelling suggestions)
            term_generator.set_flags(xapian.TermGenerator.FLAG_SPELLING)
        except xapian.UnimplementedError:
            pass
        doc = xapian.Document()
        term_generator.set_document(doc)
        # app name is the data
        if parser.has_option_desktop("X-GNOME-FullName"):
            name = parser.get_desktop("X-GNOME-FullName")
        else:
            name = parser.get_desktop("Name")
        if name in seen:
            LOG.debug("duplicated name '%s' (%s)" % (name, parser.desktopf))
        seen.add(name)
        doc.set_data(name)
        index_name(doc, name, term_generator)
        # check if we should ignore this file
        if parser.has_option_desktop("X-AppInstall-Ignore"):
            ignore = parser.get_desktop("X-AppInstall-Ignore")
            if ignore.strip().lower() == "true":
                LOG.debug("X-AppInstall-Ignore found for '%s'" % parser.desktopf)
                return
        # package name
        pkgname = parser.get_desktop("X-AppInstall-Package")
        doc.add_term("AP"+pkgname)
        if '-' in pkgname:
            # we need this to work around xapian oddness
            doc.add_term(pkgname.replace('-','_'))
        doc.add_value(XAPIAN_VALUE_PKGNAME, pkgname)
        doc.add_value(XAPIAN_VALUE_DESKTOP_FILE, parser.desktopf)
        # display name
        if "display_name" in axi_values:
            doc.add_value(axi_values["display_name"], name)
        # cataloged_times
        if pkgname in cataloged_times and "catalogedtime" in axi_values:
            doc.add_value(axi_values["catalogedtime"], 
                          xapian.sortable_serialise(cataloged_times[pkgname]))
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
        # thumbnail (for third party)
        if parser.has_option_desktop("X-AppInstall-Thumbnail-Url"):
            url = parser.get_desktop("X-AppInstall-Thumbnail-Url")
            doc.add_value(XAPIAN_VALUE_THUMBNAIL_URL, url)
        # price (pay stuff)
        if parser.has_option_desktop("X-AppInstall-Price"):
            price = parser.get_desktop("X-AppInstall-Price")
            doc.add_value(XAPIAN_VALUE_PRICE, price)
            # since this is a commercial app, indicate it in the component value
            doc.add_value(XAPIAN_VALUE_ARCHIVE_SECTION, "commercial")
        # icon
        if parser.has_option_desktop("Icon"):
            icon = parser.get_desktop("Icon")
            doc.add_value(XAPIAN_VALUE_ICON, icon)
        # write out categories
        for cat in parser.get_desktop_categories():
            doc.add_term("AC"+cat.lower())
        for mime in parser.get_desktop_mimetypes():
            doc.add_term("AM"+mime.lower())
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
            if apt_pkg.config.find("Apt::Architecture") not in arches:
                return
        # Description (software-center extension)
        if parser.has_option_desktop("X-AppInstall-Description"):
            descr = parser.get_desktop("X-AppInstall-Description")
            doc.add_value(XAPIAN_VALUE_SC_DESCRIPTION, descr)
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
        for key in ["GenericName","Comment", "X-AppInstall-Description"]:
            if not parser.has_option_desktop(key):
                continue
            s = parser.get_desktop(key)
            # we need the ascii_upper here for e.g. turkish locales, see
            # bug #581207
            k = "WEIGHT_DESKTOP_" + ascii_upper(key.replace(" ", ""))
            if k in globals():
                w = globals()[k]
            else:
                LOG.debug("WEIGHT %s not found" % k)
                w = 1
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
    old_path = pathname+"_old"
    rebuild_path = pathname+"_rb"
    
    if not os.path.exists(rebuild_path):
        try:
            os.makedirs(rebuild_path)
        except:
            LOG.warn("Problem creating rebuild path '%s'." % rebuild_path)
            LOG.warn("Please check you have the relevant permissions.")
            return False
    
    # check permission
    if not os.access(pathname, os.W_OK):
        LOG.warn("Cannot write to '%s'." % pathname)
        LOG.warn("Please check you have the relevant permissions.")
        return False
    
    #check if old unrequired version of db still exists on filesystem
    if os.path.exists(old_path):
        LOG.warn("Existing xapian old db was not previously cleaned: '%s'." % old_path)
        if os.access(old_path, os.W_OK):
            #remove old unrequired db before beginning
            shutil.rmtree(old_path)
        else:
            LOG.warn("Cannot write to '%s'." % old_path)
            LOG.warn("Please check you have the relevant permissions.")
            return False

            
    # write it
    db = xapian.WritableDatabase(rebuild_path, xapian.DB_CREATE_OR_OVERWRITE)
    update(db, cache)
    # write the database version into the filep
    db.set_metadata("db-schema-version", DB_SCHEMA_VERSION)
    # update the mo file stamp for the langpack checks
    mofile = gettext.find("app-install-data")
    if mofile:
        mo_time = os.path.getctime(mofile)
        db.set_metadata("app-install-mo-time", str(mo_time))
    db.flush()
 
    os.rename(pathname, old_path)
    os.rename(rebuild_path, pathname)
    shutil.rmtree(old_path)
    return True

