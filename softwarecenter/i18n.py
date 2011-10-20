# Copyright (C) 2011 Canonical
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

import logging
import os
LOG = logging.getLogger(__name__)

# fallback if locale parsing fails
FALLBACK = "en"
# those languages need the full language-code, the other ones
# can be abbreved
FULL = ["pt_BR", 
        "zh_CN", "zh_TW"]
def get_languages():
    """Helper that returns the split up languages"""
    if not "LANGUAGE" in os.environ:
        return [get_language()]
    langs = os.environ["LANGUAGE"].split(":")
    for lang in langs[:]:
        if "_" in lang and not lang in FULL:
            langs.remove(lang)
    return langs

def get_language():
    """Helper that returns the current language
    """
    import locale
    try:
        language = locale.getdefaultlocale(('LANGUAGE','LANG','LC_CTYPE','LC_ALL'))[0]
    except Exception as e:
        LOG.warn("Failed to get language: '%s'" % e)
        language = "C"
    # use fallback if we can't determine the language
    if language is None or language == "C":
        return FALLBACK
    if language in FULL:
        return language
    return language.split("_")[0]
