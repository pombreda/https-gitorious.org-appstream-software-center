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
import ConfigParser

class SoftwareCenterConfig(ConfigParser.SafeConfigParser):
    def __init__(self):
        ConfigParser.SafeConfigParser.__init__(self)
        
def set(path, section, key, value):
    config = SoftwareCenterConfig()
    dir = os.path.split(path)[0]
    if not os.path.isdir(dir):
        os.makedirs(dir)
    if os.path.isfile(path):
        config.read(path)
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, key, value)
    with open(path, 'w') as configfile:
        config.write(configfile)

def get(path, section, key):
    config = SoftwareCenterConfig()
    if os.path.isfile(path):
        config.read(path)
        return config.get(section, key)
    else:
        return False
