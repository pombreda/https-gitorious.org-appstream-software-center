# Copyright (C) 2010 Canonical
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

from apt.debfile import DebPackage
import apt_pkg
import locale
import os
import re
import string

from apt import Cache
from apt import debfile
from gettext import gettext as _
from mimetypes import guess_type
from softwarecenter.apt.apthistory import get_apt_history
from softwarecenter.distro import get_distro
from softwarecenter.enums import *
from softwarecenter.utils import *

# this is a very lean class as its used in the main listview
# and there are a lot of application objects in memory
class Application(object):
    """ The central software item abstraction. it contains a 
        pkgname that is always available and a optional appname
        for packages with multiple applications
        
        There is also a __cmp__ method and a name property
    """
    def __init__(self, appname="", pkgname="", request="", popcon=0):
        if not (appname or pkgname):
            raise ValueError("Need either appname or pkgname or request")
        # defaults
        self.pkgname = pkgname.replace("$kernel", os.uname()[2])
        self.appname = appname
        # the request can take additional "request" data like apturl
        # strings or the path of a local deb package
        self.request = request
        self._popcon = popcon
        # a "?" in the name means its a apturl request
        if "?" in pkgname:
            # the bit before the "?" is the pkgname, everything else the req
            (self.pkgname, sep, self.request) = pkgname.partition("?")

    @property
    def name(self):
        """Show user visible name"""
        if self.appname:
            return self.appname
        return self.pkgname.capitalize()
    @property
    def popcon(self):
        return self._popcon
    # get a AppDetails object for this Applications
    def get_details(self, db):
        """ return a new AppDetails object for this application """
        return AppDetails(db, application=self)
    # special methods
    def __hash__(self):
        return ("%s:%s" % (self.appname, self.pkgname)).__hash__()
    def __cmp__(self, other):
        return self.apps_cmp(self, other)
    def __str__(self):
        return "%s,%s" % (self.appname, self.pkgname)
    @staticmethod
    def apps_cmp(x, y):
        """ sort method for the applications """
        # sort(key=locale.strxfrm) would be more efficient, but its
        # currently broken, see http://bugs.python.org/issue2481
        if x.appname and y.appname:
            return locale.strcoll(x.appname, y.appname)
        elif x.appname:
            return locale.strcoll(x.appname, y.pkgname)
        elif y.appname:
            return locale.strcoll(x.pkgname, y.appname)
        else:
            return cmp(x.pkgname, y.pkgname)

class DebFileApplication(Application):
    def __init__(self, debfile):
        # deb overrides this
        if not debfile.endswith(".deb") and not debfile.count('/') >= 2:
            raise ValueError("Need a deb file, got '%s'" % debfile)
        debname = os.path.splitext(os.path.basename(debfile))[0]
        self.appname = debname.split('_')[0].capitalize()
        self.pkgname = debname.split('_')[0].lower()
        self.request = debfile
    def get_details(self, db):
        return AppDetailsDebFile(db, application=self)


# the details
class AppDetails(object):
    """ The details for a Application. This contains all the information
        we have available like website etc
    """

    def __init__(self, db, doc=None, application=None):
        """ Create a new AppDetails object. It can be created from
            a xapian.Document or from a db.application.Application object
        """
        if not doc and not application:
            raise ValueError, "Need either document or application"
        self._db = db
        self._cache = self._db._aptcache
        self._distro = get_distro()
        self._history = get_apt_history()
        # import here (intead of global) to avoid dbus dependency
        # in update-software-center (that imports application, but
        # never uses AppDetails) LP: #620011
        from softwarecenter.backend import get_install_backend
        self._backend = get_install_backend()
        # FIXME: why two error states ?
        self._error = None
        self._error_not_found = None

        # load application
        self._app = application
        if doc:
            self._app = Application(self._db.get_appname(doc), 
                                    self._db.get_pkgname(doc), 
                                    "")

        # sustitute for apturl
        if self._app.request:
            self._app.request = self._app.request.replace(
                "$distro", self._distro.get_distro_codename())

        # load pkg cache
        self._pkg = None
        if (self._app.pkgname in self._cache and 
            self._cache[self._app.pkgname].candidate):
            self._pkg = self._cache[self._app.pkgname]

        # load xapian document
        self._doc = doc
        if not self._doc:
            try:
                self._doc = self._db.get_xapian_document(
                    self._app.appname, self._app.pkgname)
            except IndexError:
                # if there is no document and no apturl request,
                # set error state
                debfile_matches = re.findall(r'/', self._app.request)
                channel_matches = re.findall(r'channel=[a-z,-]*', 
                                             self._app.request)
                section_matches = re.findall(r'section=[a-z]*', 
                                             self._app.request)
                if (not self._pkg and 
                    not debfile_matches and 
                    not channel_matches and 
                    not section_matches):
                    self._error = _("Not Found")
                    self._error_not_found = _("There isn't a software package called \"%s\" in your current software sources.") % self.pkgname.capitalize()

    @property
    def architecture(self):
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_ARCHIVE_ARCH)

    @property
    def channelname(self):
        if self._doc:
            channel = self._doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
            path = APP_INSTALL_CHANNELS_PATH + channel + ".list"
            if os.path.exists(path):
                return channel
        else:
            # check if we have an apturl request to enable a channel
            channel_matches = re.findall(r'channel=([a-z,-]*)', self._app.request)
            if channel_matches:
                channel = channel_matches[0]
                channelfile = APP_INSTALL_CHANNELS_PATH + channel + ".list"
                if os.path.exists(channelfile):
                    return channel

    @property
    def channelfile(self):
        channel = self.channelname
        if channel:
            return APP_INSTALL_CHANNELS_PATH + channel + ".list"

    @property
    def component(self):
        """ 
        get the component (main, universe, ..)
        
        this uses the data from apt, if there is none it uses the 
        data from the app-install-data files
        """
        # try apt first
        if self._pkg:
            for origin in self._pkg.candidate.origins:
                if (origin.origin == "Ubuntu" and origin.trusted and origin.component):
                    return origin.component
        # then xapian
        if self._doc:
            comp = self._doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
            return comp
        # then apturl requests
        if not self._doc:
            section_matches = re.findall(r'section=([a-z]+)', self._app.request)
            if section_matches:
                valid_section_matches = []
                for section_match in section_matches:
                    if self._unavailable_component(component_to_check=section_match) and valid_section_matches.count(section_match) == 0:
                        valid_section_matches.append(section_match)
                if valid_section_matches:
                    return ('&').join(valid_section_matches)

    @property
    def desktop_file(self):
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_DESKTOP_FILE)

    @property
    def description(self):
        if self._pkg:
            return self._pkg.candidate.description
        return ""

    @property
    def error(self):
        if self._error_not_found:
            return self._error_not_found
        elif self._error:
            return self._error
        # this may have changed since we inited the appdetails
        elif self.pkg_state == PKG_STATE_NOT_FOUND:
            self._error =  _("Not Found")
            self._error_not_found = _("There isn't a software package called \"%s\" in your current software sources.") % self.pkgname.capitalize()
            return self._error_not_found

    @property
    def icon(self):
        if self._doc:
            return os.path.splitext(self._db.get_iconname(self._doc))[0]
        if not self.summary:
            return MISSING_PKG_ICON
            
    @property
    def icon_file_name(self):
        if self._doc:
            return self._db.get_iconname(self._doc)
            
    @property
    def icon_needs_download(self):
        if self._doc:
            return self._db.get_icon_needs_download(self._doc)
            
    @property
    def icon_url(self):
        return self._distro.get_downloadable_icon_url(self._cache, self.pkgname, self.icon_file_name)

    @property
    def installation_date(self):
        return self._history.get_installed_date(self.pkgname)
        
    @property
    def purchase_date(self):
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_PURCHASED_DATE)

    @property
    def license(self):
        return self._distro.get_license_text(self.component)

    @property
    def maintenance_status(self):
        return self._distro.get_maintenance_status(
            self._cache, self.display_name, self.pkgname, self.component, 
            self.channelname)

    @property
    def name(self):
        """ Return the name of the application, this will always
            return Application.name. Most UI will want to use
            the property display_name instead
        """
        return self._app.name
    
    @property
    def display_name(self):
        """ Return the name as it should be displayed in the UI

            Note that this may not corespond to the Appname as the
            spec says the name should be the summary for packages
            and the summary the pkgname
        """
        if self._error_not_found:
            return self._error
        if self._doc:
            name = self._db.get_appname(self._doc)
            if name:
                return name
            else:
                # by spec..
                return self._db.get_summary(self._doc)
        return self.name

    @property
    def display_summary(self):
        """ Return the summary as it should be displayed in the UI

            Note that this may not corespond to the summary value as the
            spec says the name should be the summary for packages
            and the summary the pkgname
        """
        if self._doc:
            name = self._db.get_appname(self._doc)
            if name:
                return self._db.get_summary(self._doc)
            else:
                # by spec..
                return self._db.get_pkgname(self._doc)
        return ""

    @property
    def pkg(self):
        if self._pkg:
            return self._pkg

    @property
    def pkgname(self):
        return self._app.pkgname

    @property
    def pkg_state(self):
        # puchase state
        if self.pkgname in self._backend.pending_purchases:
            return PKG_STATE_INSTALLING_PURCHASED

        # via the pending transactions dict
        if self._pkg and self.pkgname in self._backend.pending_transactions:
            # FIXME: we don't handle upgrades yet
            if self._pkg.installed:
                return PKG_STATE_REMOVING
            else:
                return PKG_STATE_INSTALLING

        # if we have _pkg that means its either:
        # - available for download (via sources.list)
        # - locally installed
        # - intalled and available for download
        if self._pkg:
            # Don't handle upgrades yet
            #if self._pkg.installed and self._pkg._isUpgradable:
            #    return PKG_STATE_UPGRADABLE
            if self._pkg.installed:
                return PKG_STATE_INSTALLED
            else:
                return PKG_STATE_UNINSTALLED
        # if we don't have a _pkg, then its either:
        #  - its in a unavailable repo
        #  - the repository information is outdated
        #  - the repository information is missing (/var/lib/apt/lists empty)
        #  - its a failure in our meta-data (e.g. typo in the pkgname in
        #    the metadata)
        #  - not available for our architecture
        if not self._pkg:
            if self.channelname:
                if self._unavailable_channel():
                    return PKG_STATE_NEEDS_SOURCE
                else:
                    self._error =  _("Not Found")
                    self._error_not_found = _("There isn't a software package called \"%s\" in your current software sources.") % self.pkgname.capitalize()
                    return PKG_STATE_NOT_FOUND
            else:
                if self.price and self._available_for_our_arch():
                    return PKG_STATE_NEEDS_PURCHASE
                if (self.purchase_date and
                    self._doc.get_value(XAPIAN_VALUE_ARCHIVE_DEB_LINE)):
                    return PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED
                if self.component:
                    components = self.component.split('&')
                    for component in components:
                        if (component and (self._unavailable_component(component_to_check=component) or self._available_for_our_arch())):
                            return PKG_STATE_NEEDS_SOURCE
                        if component and not self._available_for_our_arch():
                            self._error_not_found = _("Not available for this type of computer (%s).") % get_current_arch()
                            return PKG_STATE_NOT_FOUND
                else:
                    self._error =  _("Not Found")
                    self._error_not_found = _("There isn't a software package called \"%s\" in your current software sources.") % self.pkgname.capitalize()
                    return PKG_STATE_NOT_FOUND
        return PKG_STATE_UNKNOWN

    @property
    def price(self):
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_PRICE)

    @property
    def ppaname(self):
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_ARCHIVE_PPA)

    @property
    def deb_line(self):
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_ARCHIVE_DEB_LINE)

    @property
    def signing_key_id(self):
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_ARCHIVE_SIGNING_KEY_ID)

    @property
    def screenshot(self):
        # if there is a custom screenshot url provided, use that
        if self._doc:
            if self._doc.get_value(XAPIAN_VALUE_SCREENSHOT_URL):
                return self._doc.get_value(XAPIAN_VALUE_SCREENSHOT_URL)
        # else use the default
        return self._distro.SCREENSHOT_LARGE_URL % self.pkgname

    @property
    def summary(self):
        if self._doc:
            return self._db.get_summary(self._doc)
        elif self._pkg:
            return self._pkg.candidate.summary

    @property
    def thumbnail(self):
        # if there is a custom thumbnail url provided, use that
        if self._doc:
            if self._doc.get_value(XAPIAN_VALUE_THUMBNAIL_URL):
                return self._doc.get_value(XAPIAN_VALUE_THUMBNAIL_URL)
        # else use the default
        return self._distro.SCREENSHOT_THUMB_URL % self.pkgname

    @property
    def version(self):
        if self._pkg:
            return self._pkg.candidate.version

    @property
    def warning(self):
        # apturl minver matches
        if not self.pkg_state == PKG_STATE_INSTALLED:
            if self._app.request:
                minver_matches = re.findall(r'minver=[a-z,0-9,-,+,.,~]*', self._app.request)
                if minver_matches and self.version:
                    minver = minver_matches[0][7:]
                    if apt_pkg.version_compare(minver, self.version) > 0:
                        return _("Version %s or later not available.") % minver
        # can we enable a source
        if not self._pkg:
            source_to_enable = None
            if self.channelname and self._unavailable_channel():
                source_to_enable = self.channelname
            elif self.component:
                source_to_enable = self.component
            if source_to_enable:
                sources = source_to_enable.split('&')
                sources_length = len(sources)
                if sources_length == 1:
                    warning = _("Available from the \"%s\" source.") % sources[0]
                elif sources_length > 1:
                    # Translators: the visible string is constructed concatenating 
                    # the following 3 strings like this: 
                    # Available from the following sources: %s, ... %s, %s.                
                    warning = _("Available from the following sources: ")
                    # Cycle through all, but the last
                    for source in sources[:-1]:
                        warning += _("\"%s\", ") % source
                    warning += _("\"%s\".") % sources[sources_length - 1]
                return warning

    @property
    def website(self):
        if self._pkg:
            return self._pkg.candidate.homepage

    def _unavailable_channel(self):
        """ Check if the given doc refers to a channel that is currently not enabled """
        # this is basically just a test to see if canonical-partner is enabled, it won't return true for anything else really..
        channel = self.channelname
        if not channel:
            return False
        if channel.count('-') != 1:
            return False
        available = self._cache.component_available(channel.split('-')[0], channel.split('-')[1])
        return (not available)

    def _unavailable_component(self, component_to_check=None):
        """ Check if the given doc refers to a component that is currently not enabled """
        if component_to_check:
            component = component_to_check
        elif self.component:
            component = self.component
        else:
            component =  self._doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        if not component:
            return False
        distro_codename = self._distro.get_codename()
        available = self._cache.component_available(distro_codename, component)
        return (not available)

    def _available_for_our_arch(self):
        """ check if the given package is available for our arch """
        arches = self.architecture
        # if we don't have a arch entry in the document its available
        # on all architectures we know about
        if not arches:
            return True
        # check the arch field and support both "," and ";"
        sep = ","
        if ";" in arches:
            sep = ";"
        elif "," in arches:
            sep = ","
        for arch in map(string.strip, arches.split(sep)):
            if arch == get_current_arch():
                return True
        return False

    def __str__(self):
        details = []
        details.append("* AppDetails")
        details.append("                name: %s" % self.name)
        details.append("                 pkg: %s" % self.pkg)
        details.append("             pkgname: %s" % self.pkgname)
        details.append("        architecture: %s" % self.architecture)
        details.append("         channelname: %s" % self.channelname)
        details.append("                 ppa: %s" % self.ppaname)
        details.append("         channelfile: %s" % self.channelfile)
        details.append("           component: %s" % self.component)
        details.append("        desktop_file: %s" % self.desktop_file)
        details.append("         description: %s" % self.description)
        details.append("                icon: %s" % self.icon)
        details.append("      icon_file_name: %s" % self.icon_file_name)
        details.append(" icon_needs_download: %s" % self.icon_needs_download)
        details.append("            icon_url: %s" % self.icon_url)
        details.append("   installation_date: %s" % self.installation_date)
        details.append("       purchase_date: %s" % self.purchase_date)
        details.append("             license: %s" % self.license)
        details.append("  maintenance_status: %s" % self.maintenance_status)
        details.append("           pkg_state: %s" % self.pkg_state)
        details.append("               price: %s" % self.price)
        details.append("          screenshot: %s" % self.screenshot)
        details.append("             summary: %s" % self.summary)
        details.append("           thumbnail: %s" % self.thumbnail)
        details.append("             version: %s" % self.version)
        details.append("             website: %s" % self.website)
        return '\n'.join(details)

class AppDetailsDebFile(AppDetails):
    
    def __init__(self, db, doc=None, application=None):
        super(AppDetailsDebFile, self).__init__(db, doc, application)
        if doc:
            raise ValueError("doc must be None for deb files")

        try:
            # for some reason Cache() is much faster than "self._cache._cache"
            # on startup
            self._deb = DebPackage(self._app.request, Cache())
        except (IOError, SystemError),e:
            self._deb = None
            self._pkg = None
            if not os.path.exists(self._app.request):
                self._error = _("Not Found")
                self._error_not_found = _("The file \"%s\" does not exist.") % self._app.request
            else:
                mimetype = guess_type(self._app.request)
                if mimetype[0] != "application/x-debian-package":
                    self._error =  _("Not Found")
                    self._error_not_found = _("The file \"%s\" is not a software package.") % self._app.request
                else:
                    # hm, deb files from launchpad get this error..
                    self._error =  _("Internal Error")
                    self._error_not_found = _("The file \"%s\" could not be opened.") % self._app.request
            return

        if self.pkgname:
            self._app.pkgname = self.pkgname

        # check deb and set failure state on error
        if not self._deb.check():
            self._error = self._deb._failure_string

    @property
    def architecture(self):
        if self._deb:
            return self._deb._sections["Architecture"]

    @property
    def description(self):
        if self._deb:
            description = self._deb._sections["Description"]
            return ('\n').join(description.split('\n')[1:]).replace(" .\n", "")
        return ""

    @property
    def maintenance_status(self):
        return None

    @property
    def pkgname(self):
        if self._deb:
            return self._deb._sections["Package"]

    @property
    def pkg_state(self):
        if self._error:
            if self._error_not_found:
                return PKG_STATE_NOT_FOUND
            else:
                return PKG_STATE_ERROR
        if self._deb:
            deb_state = self._deb.compare_to_version_in_cache()
            if deb_state == DebPackage.VERSION_NONE:
                return PKG_STATE_UNINSTALLED
            elif deb_state == DebPackage.VERSION_OUTDATED:
                if self._cache[self.pkgname].installed:
                    return PKG_STATE_INSTALLED
                else:
                    return PKG_STATE_UNINSTALLED
            elif deb_state == DebPackage.VERSION_SAME:
                return PKG_STATE_REINSTALLABLE
            elif deb_state == DebPackage.VERSION_NEWER:
                if self._cache[self.pkgname].installed:
                    return PKG_STATE_UPGRADABLE
                else:
                    return PKG_STATE_UNINSTALLED
    
    @property
    def summary(self):
        if self._deb:
            description = self._deb._sections["Description"]
            return description.split('\n')[0]

    @property
    def display_summary(self):
        if self._doc:
            name = self._db.get_appname(self._doc)
            if name:
                return self.summary
            else:
                # by spec..
                return self._db.get_pkgname(self._doc)
        return self.summary

    @property
    def version(self):
        if self._deb:
            return self._deb._sections["Version"]

    @property
    def warning(self):
        # warnings for deb-files
        # FIXME: use more concise warnings
        if self._deb:
            deb_state = self._deb.compare_to_version_in_cache()
            if deb_state == DebPackage.VERSION_NONE:
                return _("Only install this file if you trust the origin.")
            elif deb_state == DebPackage.VERSION_OUTDATED:
                if not self._cache[self.pkgname].installed:
                    return _("Please install \"%s\" via your normal software channels. Only install this file if you trust the origin.") % self.name
            elif deb_state == DebPackage.VERSION_SAME:
                return _("Please install \"%s\" via your normal software channels. Only install this file if you trust the origin.") % self.name
            elif deb_state == DebPackage.VERSION_NEWER:
                return _("An older version of \"%s\" is available in your normal software channels. Only install this file if you trust the origin.") % self.name

    @property
    def website(self):
        if self._deb:
            website = None
            try:
                website = self._deb._sections["Homepage"]
            except:
                pass
            if website:
                return website
