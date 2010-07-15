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
SOFTWARE_CENTER_PLUGIN_DIR = os.path.join(SOFTWARE_CENTER_BASE, "/plugins")

# icons
MISSING_APP_ICON = "applications-other"
MISSING_PKG_ICON = "dialog-question"

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

# fake channels
PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME = "for-pay-needs-reinstall"
AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME = "available-for-pay"

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
    # special
    PKG_STATE_NEEDS_SOURCE,
    PKG_STATE_NEEDS_PURCHASE,
    PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED,
    PKG_STATE_UNKNOWN,
 ) = range(11)

from version import *
USER_AGENT="Software Center/%s (N;) %s/%s (%s)" % (VERSION, 
                                                   DISTRO, 
                                                   RELEASE,
                                                   CODENAME)

