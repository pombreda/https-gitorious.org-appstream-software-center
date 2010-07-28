#!/usr/bin/python
# Copyright (C) 2010 Canonical
#
# Authors:
#  Geliy Sokolov
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

""" setup global logging for software-center """

class NullFilterThatWarnsAboutRootLoggerUsage(logging.Filter):
    """ pass all messages through, but warn about messages that
        come from the root logger (and not from the softwarecenter root)
    """
    def filter(self, record):
        if not record.name.startswith("softwarecenter"):
            fixme_msg = logging.getLogger("softwarecenter.fixme").findCaller()
            s = "logs to the root logger: '%s'" % str(fixme_msg)
            logging.getLogger("softwarecenter.fixme").warn(s)
        return 1
	
class OrFilter(logging.Filter):
    """ A filter that can have multiple filter strings and shows
        the message if any of the filter strings matches
    """
    def __init__(self):
        self.filters = []
    def filter(self, record):
        for (fname,flen) in self.filters:
            if (flen == 0 or 
                fname == record.name or 
                (len(record.name)>flen and record.name[flen] == ".")):
                return 1
        return 0
    def add(self, log_filter):
        """ add a log_filter string to the list of OR expressions """
        self.filters.append((log_filter, len(log_filter)))

def add_filters_from_string(long_filter_str):
    """ take the string passed from e.g. the commandline and create
        logging.Filters for it. It will prepend "softwarecenter."
        if that is not passed and will split "," to support mulitple
        filters
    """
    logging.debug("adding filter: '%s'" % long_filter_str)
    logfilter = OrFilter()
    for filter_str in long_filter_str.split(","):
        filter_str = filter_str.strip("")
        if filter_str == "":
            return
        if not (filter_str.startswith("sc") or 
                filter_str.startswith("softwarecenter")):
            filter_str = "sc.%s" % filter_str
        if filter_str.startswith("sc"):
            filter_str = "softwarecenter" + filter_str[2:]
        logfilter.add(filter_str)
    # attach or filter
    handler.addFilter(logfilter)



# setup global software-center logging
root = logging.getLogger()
fmt = logging.Formatter(logging.BASIC_FORMAT, None)
handler = logging.StreamHandler()
handler.setFormatter(fmt)
root.addHandler(handler)
handler.addFilter(NullFilterThatWarnsAboutRootLoggerUsage())
