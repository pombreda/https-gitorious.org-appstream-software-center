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
import locale
import logging
import os
import string
import sys
import xapian

from ConfigParser import RawConfigParser, NoOptionError
from glob import glob

from softwarecenter.enums import *

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

# make seen a global var
seen = set()

class AppInfoParserBase(object):
    """ base class for a appinfo parser """

    @property
    def name(self):
        """ return the name of the application """
    @property
    def package_name(self):
        """ return the package name that the application belongs to """
    @property
    def ignore(self):
        """ return True if this file should be ignored """
    @property
    def archive_component(self):
        """ return the component of the package (main, universe) """
    @property
    def archive_section(self):
        """ return the section of the package (net, python) """
    @property
    def channel(self):
        """ return the channel """
    @property
    def icon(self):
        """ return the icon name """
    @property
    def desktop_categories(self):
        """ return a list of desktop categories (AudioVideo;Foo) """
    @property
    def type(self):
        """ return the type (Application) """
    @property
    def gettext_domain(self):
        """ return the gettext domain """
    @property
    def architecture(self):
        """ return the architecture """
    @property
    def popcon(self):
        """ return the popcon value """
    @property
    def generic_name(self):
        """ return a generic_name for the app """
    @property
    def comment(self):
        """ return a comment for the app """
    @property
    def search_text(self):
        """ return text that should be used to index the data"""
    @property
    def keywords(self):
        """ return keywords """

class AppInfoDesktopParser(AppInfoParserBase):
    """ base class for a appinfo parser """

    def __init__(self, desktopf):
        self._parser =  DesktopConfigParser()
        self._parser.read(desktopf)
    def _get_option_or_none(self, k):
        if self._parser.has_option_desktop(k):
            return self._parser.get_desktop(k)
    @property
    def name(self):
        return self._get_option_or_none("Name")
    @property
    def package_name(self):
        return self._get_option_or_none("X-AppInstall-Package")
    @property
    def ignore(self):
        if self._parser.has_option_desktop("X-AppInstall-Ignore"):
            ignore = parser.get_desktop("X-AppInstall-Ignore")
            if ignore.strip().lower() == "true":
                return True
        return False
    @property
    def archive_component(self):
        return self._get_option_or_none("X-AppInstall-Section")
    @property
    def channel(self):
        """ return the channel """
        return self._get_option_or_none("X-AppInstall-Channel")
    @property
    def icon(self):
        return self._parser.get_desktop("Icon")
    @property
    def desktop_categories(self):
        return self._parser.get_desktop_categories()
    @property
    def type(self):
        """ return the type (Application) """
        return self._get_option_or_none("Type")
    @property
    def gettext_domain(self):
        return self._get_option_or_none("X-Ubuntu-Gettext-Domain")
    @property
    def architectures(self):
        return self._get_option_or_none("X-AppInstall-Architectures")
    @property
    def popcon(self):
        return self._get_option_or_none("X-AppInstall-Popcon")
    @property
    def generic_name(self):
        return self._get_option_or_none("GenericName")
    @property
    def comment(self):
        return self._get_option_or_none("Comment")
    @property
    def search_text(self):
        """ return text that should be used to index the data"""
    @property
    def keywords(self):
        """ return keywords """
    


class DesktopConfigParser(RawConfigParser):
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
    def get_desktop_categories(self):
        " get the list of categories for the desktop file "
        categories = []
        try:
            categories_str = self.get_desktop("Categories")
            for item in categories_str.split(";"):
                if item:
                    categories.append(item)
        except NoOptionError:
            pass
        return categories

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
    update_from_var_lib_apt_lists()

def update_from_var_lib_apt_lists(db, cache, listsdir=None):
    """ index the files in /var/lib/apt/lists/*AppInfo """
    context = glib.main_context_default()
    if not listsdir:
        listsdir = apt_pkg.Config.FindDir("Dir::State::lists")
    for appinfo in glob("%s/*AppInfo" % listsdir):
        logging.debug("processing %s" % appinfo)
        # process events
        while context.pending():
            context.iteration()
        tagf = apt_pkg.TagFile(open(appinfo))
        for section in tagf:
            if not "Package" in section:
                logging.debug("no Package header, ignoring")
                continue
    return True

def update_from_app_install_data(db, cache, datadir=APP_INSTALL_PATH):
    """ index the desktop files in $datadir/desktop/*.desktop """
    term_generator = xapian.TermGenerator()
    context = glib.main_context_default()
    popcon_max = 0
    for desktopf in glob(datadir+"/desktop/*.desktop"):
        logging.debug("processing %s" % desktopf)
        # process events
        while context.pending():
            context.iteration()

        doc = xapian.Document()
        term_generator.set_document(doc)
        try:
            parser = AppInfoDesktopParser(desktopf)

            # app name is the data
            name = parser.name
            if name in seen:
                logging.debug("duplicated name '%s' (%s)" % (name, desktopf))
            seen.add(name)
            doc.set_data(name)
            index_name(doc, name, term_generator)
            # check if we should ignore this file
            if parser.ignore:
                logging.debug("X-AppInstall-Ignore found for '%s'" % desktopf)
                continue
            # package name
            pkgname = parser.package_name
            doc.add_term("AP"+pkgname)
            doc.add_value(XAPIAN_VALUE_PKGNAME, pkgname)
            doc.add_value(XAPIAN_VALUE_DESKTOP_FILE, desktopf)
            # pocket (main, restricted, ...)
            if parser.archive_component:
                archive_section = parser.archive_component
                doc.add_term("AS"+archive_section)
                doc.add_value(XAPIAN_VALUE_ARCHIVE_SECTION, archive_section)
            # section (mail, base, ..)
            if pkgname in cache and cache[pkgname].candidate:
                section = cache[pkgname].candidate.section
                doc.add_term("AE"+section)
            # channel (third party stuff)
            if parser.channel:
                archive_channel = parser.channel
                doc.add_term("AH"+archive_channel)
                doc.add_value(XAPIAN_VALUE_ARCHIVE_CHANNEL, archive_channel)
            # icon
            if parser.icon:
                icon = parser.icon
                doc.add_value(XAPIAN_VALUE_ICON, icon)
            # write out categories
            for cat in parser.desktop_categories:
                doc.add_term("AC"+cat.lower())
            # get type (to distinguish between apps and packages
            if parser.type:
                type = parser.type
                doc.add_term("AT"+type.lower())
            # check gettext domain
            if parser.gettext_domain:
                domain = parser.gettext_domain
                doc.add_value(XAPIAN_VALUE_GETTEXT_DOMAIN, domain)
            # architecture
            if parser.architectures:
                arches = parser.architectures
                doc.add_value(XAPIAN_VALUE_ARCHIVE_ARCH, arches)
            # popcon
            # FIXME: popularity not only based on popcon but also
            #        on archive section, third party app etc
            if parser.popcon:
                popcon = float(parser.popcon)
                # sort_by_value uses string compare, so we need to pad here
                doc.add_value(XAPIAN_VALUE_POPCON, 
                              xapian.sortable_serialise(popcon))
                popcon_max = max(popcon_max, popcon)

            # comment goes into the summary data if there is one,
            # other wise we try GenericName and if nothing else,
            # the summary of the package
            if parser.comment:
                s = parser.comment
                doc.add_value(XAPIAN_VALUE_SUMMARY, s)
            elif parser.generic_name:
                s = parser.generic_name
                if s != parser.name:
                    doc.add_value(XAPIAN_VALUE_SUMMARY, s)
            elif self.pkgname in cache and cache[pkgname].candidate:
                s = cache[pkgname].candidate.summary
                doc.add_value(XAPIAN_VALUE_SUMMARY, s)

            # add packagename as meta-data too
            term_generator.index_text_without_positions(pkgname, WEIGHT_APT_PKGNAME)

            # now add search data from the desktop file
            if parser.generic_name:
                w = WEIGHT_DESKTOP_GENERICNAME
                term_generator.index_text_without_positions(s, w)
            if parser.comment:
                w = WEIGHT_DESKTOP_COMMENT
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
            if parser.keywords:
                keywords = parser.keywords
                for s in keywords.split(";"):
                    if s:
                        term_generator.index_text_without_positions(s, WEIGHT_DESKTOP_KEYWORD)
                
            # FIXME: now do the same for the localizations in the
            #        desktop file
            # FIXME3: add X-AppInstall-Section
        except Exception, e:
            # Print a warning, no error (Debian Bug #568941)
            logging.warning("error processing: %s %s" % (desktopf, e))
            continue
        # now add it
        db.add_document(doc)
    # add db global meta-data
    logging.debug("adding popcon_max_desktop '%s'" % popcon_max)
    db.set_metadata("popcon_max_desktop", xapian.sortable_serialise(float(popcon_max)))
    return True

def rebuild_database(pathname):
    import apt
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

