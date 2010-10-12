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
import time
LOG = logging.getLogger("sofwarecenter.zeitgeist")

try:
    from zeitgeist.client import ZeitgeistClient
    from zeitgeist.datamodel import Event, Interpretation
except ImportError:
    LOG.exception("zeitgeist import failed")
    ZEITGEIST_AVAILABLE = False
else:
    ZEITGEIST_AVAILABLE = True

class SoftwareCenterZeitgeist():
    """ simple wrapper around zeitgeist """

    def __init__(self):
        self.zg_client = ZeitgeistClient()
        
    def get_usage_counter(self, application, callback, timerange=None):
        """Request the usage count as integer for the given application.
           When the request is there, "callback" is called. A optional
           timerange like [time.time(), time.time() - 30*24*60*60] can
           also be specified
        """
        def _callback(event_ids):
            callback(len(event_ids))
        # the app we are looking for
        application = "application://"+application.split("/")[-1]
        # the event_templates
        e1 = Event.new_for_values(
            actor=application, interpretation=Interpretation.MODIFY_EVENT.uri)
        e2 = Event.new_for_values(
            actor=application, interpretation=Interpretation.CREATE_EVENT.uri)
        # run it
        self.zg_client.find_event_ids_for_templates(
            [e1, e2], _callback, timerange=timerange, num_events=0)
       
    def get_popular_mimetypes(self, callback, num = 3):
        def _callback(events):
            mimetypes = {}
            for event in events:
                mimetype = event.subjects[0].mimetype
                if not mimetypes.has_key(mimetype):
                    mimetypes[mimetype] = 0
                mimetypes[mimetype] += 1
            results = []
            if len(mimetypes) == 0:
                callback([])
            for k, v in mimetypes.iteritems():
                    results.append([v, k])
            results.sort(reverse = True)
            print "###########"
            print "MOST USED"
            print "----------"
            for i in results[:num]:
                print i
            print "###########"
            callback(results[:num])
        # FIXME: investigate how result_type 0 or 2 would affect the results
        self.zg_client.find_events_for_template(
            [], _callback, num_events=1000, result_type=2)

class SoftwareCenterZeitgeistDummy():
    def get_usage_counter(self, application, callback):
        callback(0)
    def get_popular_mimetypes(self, callback):
        callback([])

# singleton
if ZEITGEIST_AVAILABLE:
    zeitgeist_singleton = SoftwareCenterZeitgeist()
else:
    zeitgeist_singleton = SoftwareCenterZeitgeistDummy()

if __name__ == "__main__":

    def _callback_counter(events):
        print "test _callback: ", events
    # all time gedit
    zeitgeist_singleton.get_usage_counter("gedit.desktop", _callback_counter)

    # yesterday gedit
    end = time.time()
    start = end - 24*60*60
    zeitgeist_singleton.get_usage_counter("gedit.desktop", _callback_counter,
                                          timerange=[start, end])
    
    # most popular
    def _callback_popular(mimetypes):
        print "test _callback: "
        for tuple in mimetypes:
        	print tuple
    zeitgeist_singleton.get_popular_mimetypes(_callback_popular)

    import gtk
    gtk.main()
