

import cPickle
import glib
import gobject
import logging
import os


LOG = logging.getLogger(__name__)

class SpawnHelper(gobject.GObject):
    
    __gsignals__ = {
        "data-available" : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE, 
                            (gobject.TYPE_PYOBJECT,),
                            ),
        "error" : (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, 
                   (str,),
                  ),
        }

    def spawn_helper(self, cmd):
        (pid, stdin, stdout, stderr) = glib.spawn_async(
            cmd, flags = glib.SPAWN_DO_NOT_REAP_CHILD, 
            standard_output=True, standard_error=True)
        glib.child_watch_add(
            pid, self._helper_finished, data=(stdout, stderr))
        glib.io_add_watch(
            stdout, glib.IO_IN, self._helper_io_ready, (stdout, ))

    def _helper_finished(self, pid, status, (stdout, stderr)):
        # get status code
        res = os.WEXITSTATUS(status)
        if res != 0:
            LOG.warn("exit code %s from helper" % res)
        # check stderr
        err = os.read(stderr, 4*1024)
        if err:
            LOG.warn("got error from helper: '%s'" % err)
            self.emit("error", err)
        os.close(stderr)

    def _helper_io_ready(self, source, condition, (stdout,)):
        # read the raw data
        data = ""
        while True:
            s = os.read(stdout, 1024)
            if not s: break
            data += s
        os.close(stdout)
        # unpickle it, we should *always* get valid data here, so if
        # we don't this should raise a error
        data = cPickle.loads(data)
        self.emit("data-available", data)
        return False
