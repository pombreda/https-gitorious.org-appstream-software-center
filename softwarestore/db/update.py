#!/usr/bin/python
# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
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
import locale
import logging
import os
import sys
import xapian

from ConfigParser import RawConfigParser, NoOptionError
from glob import glob

try:
    from softwarestore.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from softwarestore.enums import *

# weights for the different fields
WEIGHT_DESKTOP_NAME = 10
WEIGHT_DESKTOP_KEYWORD = 5
WEIGHT_DESKTOP_GENERICNAME = 3
WEIGHT_DESKTOP_COMMENT = 1

WEIGHT_APT_SUMMARY = 5
WEIGHT_APT_DESCRIPTION = 1

from locale import getdefaultlocale
import gettext

class DesktopConfigParser(RawConfigParser):
    " thin wrapper that is tailored for xdg Desktop files "
    DE = "Desktop Entry"
    def get_desktop(self, key):
        " get generic option under 'Desktop Entry'"
        # first try dgettext
        if self.has_option_desktop("X-Ubuntu-Gettext-Domain"):
            value = self.get(self.DE, key)
            domain = self.get(self.DE, "X-Ubuntu-Gettext-Domain")
            translated_value = gettext.dgettext(domain, value)
            if value != translated_value:
                return translated_value
        # then try the i18n version of the key (in [de_DE] or
        # [de]
        locale = getdefaultlocale()[0]
        if self.has_option_desktop("%s[%s]" % (key, locale)):
            return self.get(self.DE, "%s[%s]" % (key, locale))
        if "_" in locale:
            locale_short = locale.split("_")[0]
            if self.has_option_desktop("%s[%s]" % (key, locale_short)):
                return self.get(self.DE, "%s[%s]" % (key, locale_short))
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

def update(db, cache, datadir=APP_INSTALL_PATH):
    " index the desktop files in $datadir/desktop/*.desktop "
    term_generator = xapian.TermGenerator()
    for desktopf in glob(datadir+"/desktop/*.desktop"):
        logging.debug("processing %s" % desktopf)
        parser = DesktopConfigParser()
        doc = xapian.Document()
        term_generator.set_document(doc)
        try:
            parser.read(desktopf)
            # app name is the data
            name = parser.get_desktop("Name")
            doc.set_data(name)
            doc.add_term("AA"+name)
            # package name
            pkgname = parser.get_desktop("X-AppInstall-Package")
            doc.add_term("AP"+pkgname)
            doc.add_value(XAPIAN_VALUE_PKGNAME, pkgname)
            doc.add_value(XAPIAN_VALUE_DESKTOP_FILE, desktopf)
            # section (main, restricted, ...)
            if parser.has_option_desktop("X-AppInstall-Section"):
                archive_section = parser.get_desktop("X-AppInstall-Section")
                doc.add_term("AS"+archive_section)
                doc.add_value(XAPIAN_VALUE_ARCHIVE_SECTION, archive_section)
            # channel (third party stuff)
            if parser.has_option_desktop("X-AppInstall-Channel"):
                archive_channel = parser.get_desktop("X-AppInstall-Channel")
                doc.add_term("AH"+archive_section)
                doc.add_value(XAPIAN_VALUE_ARCHIVE_CHANNEL, archive_channel)
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
                popcon = parser.get_desktop("X-AppInstall-Popcon")
                # sort_by_value uses string compare, so we need to pad here
                doc.add_value(XAPIAN_VALUE_POPCON, 
                              xapian.sortable_serialise(float(popcon)))

            # comment goes into the summary data if there is one,
            # other wise we try GenericName
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

            # now add search data from the desktop file
            for key in ["Name","Generic Name","Comment"]:
                if not parser.has_option_desktop(key):
                    continue
                s = parser.get_desktop(key)
                w = globals()["WEIGHT_DESKTOP_"+key.replace(" ","").upper()]
                term_generator.index_text_without_positions(s)
            # add data from the apt cache
            if pkgname in cache and cache[pkgname].candidate:
                s = cache[pkgname].candidate.summary
                term_generator.index_text_without_positions(s, WEIGHT_APT_SUMMARY)
                s = cache[pkgname].candidate.description
                term_generator.index_text_without_positions(s, WEIGHT_APT_DESCRIPTION)
            # add our keywords (with high priority)
            if parser.has_option_desktop("X-AppInstall-Keywords"):
                keywords = parser.get_desktop("X-AppInstall-Keywords")
                for s in keywords.split(";"):
                    if s:
                        term_generator.index_text_without_positions(s, WEIGHT_DESKTOP_KEYWORD)
                
            # FIXME: now do the same for the localizations in the
            #        desktop file
            # FIXME3: add X-AppInstall-Section
        except Exception, e:
            logging.warn("error processing: %s %s" % (desktopf, e))
            continue
        # now add it
        db.add_document(doc)
    return True

def rebuild_database(pathname):
    import apt
    cache = apt.Cache(memonly=True)
    if os.access(pathname, os.W_OK):
        db = xapian.WritableDatabase(pathname, xapian.DB_CREATE_OR_OVERWRITE)
        update(db, cache)
        db.flush()
        return
    else:
        logging.warn("Cannot write to ./data/xapian.")
        logging.warn("Please check you have the relevant permissions.")
        exit()
