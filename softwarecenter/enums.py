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

