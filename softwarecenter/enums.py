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


# system pathes
XAPIAN_BASE_PATH = "/var/cache/software-center"
APP_INSTALL_PATH = "/usr/share/app-install"
APP_INSTALL_DESKTOP_PATH = APP_INSTALL_PATH+"/desktop/"
APP_INSTALL_CHANNELS_PATH = APP_INSTALL_PATH+"/channels/"
ICON_PATH = APP_INSTALL_PATH+"/icons/"
SOFTWARE_CENTER_PLUGIN_DIR = "/usr/share/software-center/plugins"

# the various "views" that the app has
VIEW_PAGE_AVAILABLE = "view-page-available"
VIEW_PAGE_INSTALLED = "view-page-installed"
VIEW_PAGE_HISTORY =  "view-page-history"
VIEW_PAGE_SEPARATOR_1 = "view-page-separator-1"
VIEW_PAGE_PENDING =  "view-page-pending"
VIEW_PAGE_CHANNEL = "view-page-channel"

# items considered "permanent", that is, if a item disappears
# (e.g. progress) then switch back to the previous on in permanent
# views (LP:  #431907)
PERMANENT_VIEWS = [VIEW_PAGE_AVAILABLE,
                   VIEW_PAGE_INSTALLED,
                   VIEW_PAGE_CHANNEL,
                   VIEW_PAGE_HISTORY,
                  ]

# icons
MISSING_APP_ICON = "applications-other"
MISSING_PKG_ICON = "dialog-question"

# sorting
(SORT_UNSORTED,
 SORT_BY_ALPHABET,
 SORT_BY_SEARCH_RANKING,
 SORT_BY_CATALOGED_TIME,
) = range(4)

# values used in the database
XAPIAN_VALUE_APPNAME = 170
XAPIAN_VALUE_PKGNAME = 171
XAPIAN_VALUE_ICON = 172
XAPIAN_VALUE_GETTEXT_DOMAIN = 173
XAPIAN_VALUE_ARCHIVE_SECTION = 174
XAPIAN_VALUE_ARCHIVE_ARCH = 175
XAPIAN_VALUE_POPCON = 176
XAPIAN_VALUE_SUMMARY = 177
XAPIAN_VALUE_ARCHIVE_CHANNEL = 178
XAPIAN_VALUE_DESKTOP_FILE = 179

# pkg action state constants
PKG_STATE_INSTALLED     = 0
PKG_STATE_UNINSTALLED   = 1
PKG_STATE_UPGRADABLE    = 2
PKG_STATE_INSTALLING    = 3
PKG_STATE_REMOVING      = 4
PKG_STATE_UPGRADING     = 5
PKG_STATE_NEEDS_SOURCE  = 6
PKG_STATE_UNKNOWN       = 7
PKG_STATE_REINSTALLABLE = 8

# application actions
APP_ACTION_INSTALL = "install"
APP_ACTION_REMOVE = "remove"
APP_ACTION_UPGRADE = "upgrade"
APP_ACTION_APPLY = "apply_changes"

from version import *
USER_AGENT="Software Center/%s (N;) %s/%s (%s)" % (VERSION, 
                                                   DISTRO, 
                                                   RELEASE,
                                                   CODENAME)

