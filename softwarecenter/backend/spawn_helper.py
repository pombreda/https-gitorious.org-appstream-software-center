#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import cPickle
from gi.repository import GObject
import logging
import os
import simplejson


LOG = logging.getLogger(__name__)

class SpawnHelper(GObject.GObject):
    
    __gsignals__ = {
        "data-available" : (GObject.SIGNAL_RUN_LAST,
                            GObject.TYPE_NONE, 
                            (GObject.TYPE_PYOBJECT,),
                            ),
        "exited" : (GObject.SIGNAL_RUN_LAST,
                    GObject.TYPE_NONE, 
                    (int,),
                    ),
        "error" : (GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, 
                   (str,),
                  ),
        }

    def __init__(self, format="pickle"):
        super(SpawnHelper, self).__init__()
        self._expect_format = format
        self._stdout = None
        self._stderr = None
        self._io_watch = None
        self._child_watch = None

    def run(self, cmd):
        (pid, stdin, stdout, stderr) = GObject.spawn_async(
            cmd, flags = GObject.SPAWN_DO_NOT_REAP_CHILD, 
            standard_output=True, standard_error=True)
        self._child_watch = GObject.child_watch_add(
            pid, self._helper_finished, data=(stdout, stderr))
        self._io_watch = GObject.io_add_watch(
            stdout, GObject.IO_IN, self._helper_io_ready, (stdout, ))

    def _helper_finished(self, pid, status, (stdout, stderr)):
        # get status code
        res = os.WEXITSTATUS(status)
        if res == 0:
            self.emit("exited", res)
        else:
            LOG.warn("exit code %s from helper" % res)
            # check stderr
            err = os.read(stderr, 4*1024)
            self._stderr = err
            if err:
                LOG.warn("got error from helper: '%s'" % err)
            self.emit("error", err)
            os.close(stderr)
        if self._io_watch:
            GObject.source_remove(self._io_watch)
        if self._child_watch:
            GObject.source_remove(self._child_watch)

    def _helper_io_ready(self, source, condition, (stdout,)):
        # read the raw data
        data = ""
        while True:
            s = os.read(stdout, 1024)
            if not s: break
            data += s
        os.close(stdout)
        self._stdout = data
        if self._expect_format == "pickle":
            # unpickle it, we should *always* get valid data here, so if
            # we don't this should raise a error
            try:
                data = cPickle.loads(data)
            except:
                LOG.exception("can not load pickle data: '%s'" % data)
        elif self._expect_format == "json":
            try:
                data = simplejson.loads(data)
            except:
                LOG.exception("can not load json: '%s'" % data)
        elif self._expect_format == "none":
            pass
        else:
            LOG.error("unknown format: '%s'", self._expect_format)
        self.emit("data-available", data)
        return False
