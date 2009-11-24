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

import os
from xdg import BaseDirectory as xdg

class SoftwareCenterPaths(object):
    def __init__(self):
        self.config = xdg.xdg_config_home
        self.config_file = os.path.join(self.config, "softwarecenter", "softwarecenter.cfg")
        
def get(variable):
    paths = SoftwareCenterPaths()
    return getattr(paths, variable)
