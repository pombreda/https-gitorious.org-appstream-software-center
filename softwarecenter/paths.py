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
