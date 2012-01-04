# Copyright (C) 2010 Canonical
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
#
#
# taken from lp:~canonical-ca-hackers/software-center/scaclient 
# and put into scaclient_pristine.py

import logging
import os
import sys


# useful for debugging
if "SOFTWARE_CENTER_DEBUG_HTTP" in os.environ:
    import httplib2
    httplib2.debuglevel = 1

# patch default_service_root to the one we use
from softwarecenter.enums import RECOMMENDER_HOST
try:
    from ureclient_pristine import UbuntuRecommenderAPI
    UbuntuRecommenderAPI.default_service_root = RECOMMENDER_HOST+"/api/1.0"
except:
    logging.exception("need python-piston-mini client")
    sys.exit(1)



if __name__ == "__main__":

    ura = UbuntuRecommenderAPI()
    
    top_apps = ura.recommend_top()
    print(top_apps)
