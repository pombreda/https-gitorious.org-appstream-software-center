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
import xdg.BaseDirectory

# buy-something base url
#BUY_SOMETHING_HOST = "http://localhost:8000/"
BUY_SOMETHING_HOST = os.environ.get("SOFTWARE_CENTER_BUY_HOST") or "https://software-center.ubuntu.com"

# xapian pathes
XAPIAN_BASE_PATH = "/var/cache/software-center"
XAPIAN_BASE_PATH_SOFTWARE_CENTER_AGENT = os.path.join(
    xdg.BaseDirectory.xdg_cache_home,
    "software-center", 
    "software-center-agent.db")

# system pathes
APP_INSTALL_PATH = "/usr/share/app-install"
APP_INSTALL_DESKTOP_PATH = APP_INSTALL_PATH+"/desktop/"
APP_INSTALL_CHANNELS_PATH = APP_INSTALL_PATH+"/channels/"
ICON_PATH = APP_INSTALL_PATH+"/icons/"

SOFTWARE_CENTER_BASE = "/usr/share/software-center"
SOFTWARE_CENTER_PLUGIN_DIR = os.path.join(SOFTWARE_CENTER_BASE, "plugins")

# ratings&review
# relative to datadir
SUBMIT_REVIEW_APP = "submit_review.py"
REPORT_REVIEW_APP = "report_review.py"

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

# icon
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
XAPIAN_VALUE_PRICE = 180
XAPIAN_VALUE_ARCHIVE_PPA = 181
XAPIAN_VALUE_ARCHIVE_DEB_LINE = 182
XAPIAN_VALUE_ARCHIVE_SIGNING_KEY_ID = 183
XAPIAN_VALUE_PURCHASED_DATE = 184
XAPIAN_VALUE_SCREENSHOT_URL = 185
XAPIAN_VALUE_ICON_NEEDS_DOWNLOAD = 186
XAPIAN_VALUE_THUMBNAIL_URL = 187
XAPIAN_VALUE_SC_DESCRIPTION = 188

# fake channels
PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME = "for-pay-needs-reinstall"
AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME = "available-for-pay"

# custom keys for the new-apps repository, correspond
# control file custom fields:
#  XB-AppName, XB-Icon, XB-Screenshot-Url, XB-Thumbnail-Url, XB-Category
CUSTOM_KEY_APPNAME = "AppName"
CUSTOM_KEY_ICON = "Icon"
CUSTOM_KEY_SCREENSHOT_URL = "Screenshot-Url"
CUSTOM_KEY_THUMBNAIL_URL = "Thumbnail-Url"
CUSTOM_KEY_CATEGORY = "Category"

# pkg action state constants
(   # current
    PKG_STATE_INSTALLED,
    PKG_STATE_UNINSTALLED,
    PKG_STATE_UPGRADABLE,
    PKG_STATE_REINSTALLABLE,
    # progress
    PKG_STATE_INSTALLING,
    PKG_STATE_REMOVING,
    PKG_STATE_UPGRADING,
    PKG_STATE_ENABLING_SOURCE,
    PKG_STATE_INSTALLING_PURCHASED,
    # special
    PKG_STATE_NEEDS_SOURCE,
    PKG_STATE_NEEDS_PURCHASE,
    PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED,
    PKG_STATE_ERROR,
    # the package is not found in the DB or cache
    PKG_STATE_NOT_FOUND, 
    # this *needs* to be last (for test_appdetails.py) and means
    # something went wrong and we don't have a state for this PKG
    PKG_STATE_UNKNOWN,
 ) = range(15)

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
                                                   
# FIXME: use relative paths here
INSTALLED_ICON = "/usr/share/software-center/icons/software-center-installed.png"
IMAGE_LOADING = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading.gif"
IMAGE_LOADING_INSTALLED = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"

