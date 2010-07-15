#!/usr/bin/python
# Copyright (C) 2009 Canonical
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

DEBUG = logging.DEBUG
INFO = logging.INFO

class Logger:

    def __init__(self):
        logging.basicConfig()
        self._loggers = {}
        self._filter = None
        self._logger = logging.getLogger("softwarecenter.log")
        self._loggers["softwarecenter.log"] = self._logger
    def getLogger(self,log_name):
        if not log_name in self._loggers:
            self._logger.debug("adding " + log_name)
            self._loggers[log_name] = logging.getLogger(log_name)
            if not self._filter is None:
                self._logger.debug("and updating filter")
                self._loggers[log_name].addFilter(self._filter)
        return self._loggers[log_name]
        
    def addFilter(self,filter_str):
        self._filter = logging.Filter(filter_str)
        self._logger.debug("updating filter:" + filter_str)
        for log_name in self._loggers:
            self._logger.debug( "for:" + log_name)
            self._loggers[log_name].addFilter(self._filter)

    def setLevel(self,level):
        self.getLogger("").setLevel(level)


logger = Logger()

def getLogger(log_name=""):
    if log_name == "":
        return logger
    else:
        return logger.getLogger(log_name)

def debug(message):
    logger.getLogger("softwarecenter.fixme").debug(message)

def warn(message):
    logger.getLogger("softwarecenter.fixme").warn(message)
