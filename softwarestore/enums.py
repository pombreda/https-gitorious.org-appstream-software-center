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

# system pathes
XAPIAN_BASE_PATH = "/var/cache/software-store"
APP_INSTALL_PATH = "/usr/share/app-install"
ICON_PATH = APP_INSTALL_PATH+"/icons/"


# icon
MISSING_APP_ICON = "applications-other"


# values used in the database
XAPIAN_VALUE_PKGNAME = 171
XAPIAN_VALUE_ICON = 172
XAPIAN_VALUE_GETTEXT_DOMAIN = 173
XAPIAN_VALUE_ARCHIVE_SECTION = 174
XAPIAN_VALUE_ARCHIVE_ARCH = 175
XAPIAN_VALUE_POPCON = 176
XAPIAN_VALUE_SUMMARY = 177
