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

import os

# pkgname of this app itself (used for "self-awareness", see spec)
SOFTWARE_CENTER_PKGNAME = 'software-center'

# buy-something base url
#BUY_SOMETHING_HOST = "http://localhost:8000/"
BUY_SOMETHING_HOST = os.environ.get("SOFTWARE_CENTER_BUY_HOST") or "https://software-center.ubuntu.com"
BUY_SOMETHING_HOST_ANONYMOUS = os.environ.get("SOFTWARE_CENTER_BUY_HOST") or "http://software-center.ubuntu.com"

# version of the database, every time something gets added (like 
# terms for mime-type) increase this (but keep as a string!)
DB_SCHEMA_VERSION = "2"

# the default limit for a search
DEFAULT_SEARCH_LIMIT = 10000

# the server size "page" for ratings&reviews
REVIEWS_BATCH_PAGE_SIZE = 10

# the various "views" that the app has
class ViewPages:
    AVAILABLE = "view-page-available"
    INSTALLED = "view-page-installed"
    HISTORY =  "view-page-history"
    SEPARATOR_1 = "view-page-separator-1"
    PENDING =  "view-page-pending"
    CHANNEL = "view-page-channel"

    # items considered "permanent", that is, if a item disappears
    # (e.g. progress) then switch back to the previous on in permanent
    # views (LP:  #431907)
    PERMANENT_VIEWS = (AVAILABLE,
                       INSTALLED,
                       CHANNEL,
                       HISTORY
                      )

# define ID values for the various buttons found in the navigation bar
class NavButtons:
    CATEGORY = "category"
    LIST     = "list"
    SUBCAT   = "subcat"
    DETAILS  = "details"
    SEARCH   = "search"
    PURCHASE = "purchase"
    PREV_PURCHASES = "prev-purchases"

# define ID values for the action bar buttons
class ActionButtons:
    INSTALL = "install"
    ADD_TO_LAUNCHER = "add_to_launcher"
    CANCEL_ADD_TO_LAUNCHER = "cancel_add_to_launcher"

# icons
class Icons:
    APP_ICON_SIZE = 48

    MISSING_APP = "applications-other"
    MISSING_PKG = "dialog-question"   # XXX: Not used?
    GENERIC_MISSING = "gtk-missing-image"

# sorting
class SortMethods:
    (UNSORTED,
     BY_ALPHABET,
     BY_SEARCH_RANKING,
     BY_CATALOGED_TIME,
    ) = range(4)

# values used in the database
class XapianValues:
    APPNAME = 170
    PKGNAME = 171
    ICON = 172
    GETTEXT_DOMAIN = 173
    ARCHIVE_SECTION = 174
    ARCHIVE_ARCH = 175
    POPCON = 176
    SUMMARY = 177
    ARCHIVE_CHANNEL = 178
    DESKTOP_FILE = 179
    PRICE = 180
    ARCHIVE_PPA = 181
    ARCHIVE_DEB_LINE = 182
    ARCHIVE_SIGNING_KEY_ID = 183
    PURCHASED_DATE = 184
    SCREENSHOT_URL = 185
    ICON_NEEDS_DOWNLOAD = 186         # no longer used
    THUMBNAIL_URL = 187
    SC_DESCRIPTION = 188
    APPNAME_UNTRANSLATED = 189
    ICON_URL = 190

# fake channels
PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME = "for-pay-needs-reinstall"
AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME = "available-for-pay"

# custom keys for the new-apps repository, correspond
# control file custom fields:
#  XB-AppName, XB-Icon, XB-Screenshot-Url, XB-Thumbnail-Url, XB-Category
class CustomKeys:
    APPNAME = "AppName"
    ICON = "Icon"
    SCREENSHOT_URL = "Screenshot-Url"
    THUMBNAIL_URL = "Thumbnail-Url"
    CATEGORY = "Category"

# pkg action state constants
class PkgStates:
    (
    # current
    INSTALLED,
    UNINSTALLED,
    UPGRADABLE,
    REINSTALLABLE,
    # progress
    INSTALLING,
    REMOVING,
    UPGRADING,
    ENABLING_SOURCE,
    INSTALLING_PURCHASED,
    # special
    NEEDS_SOURCE,
    NEEDS_PURCHASE,
    PURCHASED_BUT_REPO_MUST_BE_ENABLED,
    ERROR,
    # the package is not found in the DB or cache
    NOT_FOUND, 
    # this *needs* to be last (for test_appdetails.py) and means
    # something went wrong and we don't have a state for this PKG
    UNKNOWN,
    ) = range(15)

# application actions
class AppActions:
    INSTALL = "install"
    REMOVE = "remove"
    UPGRADE = "upgrade"
    APPLY = "apply_changes"

# transaction types
class TransactionTypes:
    INSTALL = "install"
    REMOVE = "remove"
    UPGRADE = "upgrade"
    APPLY = "apply_changes"
    REPAIR = "repair_dependencies"

# mouse event codes for back/forward buttons
# TODO: consider whether we ought to get these values from gconf so that we
#       can be sure to use the corresponding values used by Nautilus:
#           /apps/nautilus/preferences/mouse_forward_button
#           /apps/nautilus/preferences/mouse_back_button
MOUSE_EVENT_FORWARD_BUTTON = 9
MOUSE_EVENT_BACK_BUTTON = 8

# delimiter for directory path separator in app-install
APP_INSTALL_PATH_DELIMITER = "__"

from version import VERSION, DISTRO, RELEASE, CODENAME
USER_AGENT="Software Center/%s (N;) %s/%s (%s)" % (VERSION, 
                                                   DISTRO, 
                                                   RELEASE,
                                                   CODENAME)

# experimental, only for testing FIXME: remove this
USE_PACKAGEKIT_BACKEND = True
