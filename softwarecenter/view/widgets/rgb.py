# Copyright (C) 2009 Matthew McGowan
#
# Authors:
#   Matthew McGowan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import colorsys


def lighten(gdkcolor, amount):
    h,l,s = colorsys.rgb_to_hls(
        gdkcolor.red_float,
        gdkcolor.green_float,
        gdkcolor.blue_float)
    return colorsys.hls_to_rgb(h,l+l*amount,s)

def darken(gdkcolor, amount):
    h,l,s = colorsys.rgb_to_hls(
        gdkcolor.red_float,
        gdkcolor.green_float,
        gdkcolor.blue_float)
    return colorsys.hls_to_rgb(h,l-l*amount,s)

