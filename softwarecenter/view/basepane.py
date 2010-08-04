# Copyright (C) 2010 Canonical
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


class BasePane(object):
    """ Base for all the View widgets that can be registered in a 
        ViewManager 
    """

    def __init__(self):
        # stuff that is queried by app.py
        self.apps_filter = None
        self.searchentry = None

    def is_category_view_showing(self):
        return False

    def update_app_view(self):
        pass

    def get_status_text(self):
        return ""

    def get_current_app(self):
        return None


