# Copyright (C) 2009-2010 Canonical
#
# Authors:
#  Seif Lotfy
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
LOG = logging.getLogger("sofwarecenter.zeitgeist")

try:
    from zeitgeist.client import ZeitgeistClient
    from zeitgeist.datamodel import Event
except ImportError:
    LOG.exception("zeitgeist import failed")
    ZEITGEIST_AVAILABLE = False
else:
    ZEITGEIST_AVAILABLE = True

class SoftwareCenterZeitgeist():
    """ simple wrapper around zeitgeist """

    def __init__(self):
        self.zg_client = ZeitgeistClient()
        
    def get_usage_counter(self, application, callback):
        application = "application://"+application.split("/")[-1]
        def _callback(event_ids):
            callback(len(event_ids))
        e = Event()
        e.actor = application
        self.zg_client.find_event_ids_for_templates(
            [e], _callback, num_events=0)

class SoftwareCenterZeitgeistDummy():
    def get_usage_counter(self, application, callback):
        callback(0)

# singleton
if ZEITGEIST_AVAILABLE:
    zeitgeist_singleton = SoftwareCenterZeitgeist()
else:
     zeitgeist_singleton = SoftwareCenterZeitgeistDummy()

if __name__ == "__main__":

    def _callback(events):
        print "test _callback: ", events
    zeitgeist_singleton.get_usage_counter("gedit.desktop", _callback)

    import gtk
    gtk.main()
