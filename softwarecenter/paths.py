# Copyright (C) 2009 Canonical
#
# Authors:
#  Andrew Higginson
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

import logging
import os
from xdg import BaseDirectory as xdg

# system pathes
APP_INSTALL_PATH = "/usr/share/app-install"
APP_INSTALL_DESKTOP_PATH = APP_INSTALL_PATH+"/desktop/"
APP_INSTALL_CHANNELS_PATH = APP_INSTALL_PATH+"/channels/"
ICON_PATH = APP_INSTALL_PATH+"/icons/"

SOFTWARE_CENTER_BASE = "/usr/share/software-center"
SOFTWARE_CENTER_PLUGIN_DIR = os.environ.get(
    "SOFTWARE_CENTER_PLUGINS_DIR",
    os.path.join(SOFTWARE_CENTER_BASE, "plugins"))

# FIXME: use relative paths here
INSTALLED_ICON = "/usr/share/software-center/icons/software-center-installed.png"
IMAGE_LOADING = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading.gif"
IMAGE_LOADING_INSTALLED = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"

# xapian pathes
XAPIAN_BASE_PATH = "/var/cache/software-center"
XAPIAN_BASE_PATH_SOFTWARE_CENTER_AGENT = os.path.join(
    xdg.xdg_cache_home,
    "software-center", 
    "software-center-agent.db")

# ratings&review
# relative to datadir
SUBMIT_REVIEW_APP = "submit_review.py"
REPORT_REVIEW_APP = "report_review.py"
SUBMIT_USEFULNESS_APP = "submit_usefulness.py"
MODIFY_REVIEW_APP = "modify_review.py"

# there was a bug in maverick 3.0.3 (#652151) that could lead to a empty
# root owned directory in ~/.cache/software-center - we remove it here
# so that it gets later re-created with the right permissions
def try_to_fixup_root_owned_dir_via_remove(directory):
    if os.path.exists(directory) and not os.access(directory, os.W_OK):
        try:
            logging.warn("trying to fix not writable cache directory")
            os.rmdir(directory)
        except:
            logging.exception("failed to fix not writable cache directory")


# ensure we don't create directories in /home/$user
if os.getuid() == 0 and "SUDO_USER" in os.environ and "HOME" in os.environ:
    del os.environ["HOME"]

SOFTWARE_CENTER_CONFIG_DIR = os.path.join(xdg.xdg_config_home, "software-center")
SOFTWARE_CENTER_CACHE_DIR = os.path.join(xdg.xdg_cache_home, "software-center")
# FIXUP a brief broken software-center in maverick
try_to_fixup_root_owned_dir_via_remove(SOFTWARE_CENTER_CACHE_DIR)

SOFTWARE_CENTER_CONFIG_FILE = os.path.join(SOFTWARE_CENTER_CONFIG_DIR, "softwarecenter.cfg") 
SOFTWARE_CENTER_ICON_CACHE_DIR = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "icons")
