
import apt
import glib
import gobject
import gtk
import time

class GtkMainIterationProgress(apt.progress.OpProgress):
    """Progress that just runs the main loop"""
    def update(self, percent):
        while gtk.events_pending():
            gtk.main_iteration()

class AptCache(gobject.GObject):
    """ 
    A apt cache that opens in the background and keeps the UI alive
    """
    
    __gsignals__ = {'cache-ready':  (gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    'cache-invalid':(gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    }
    
    def __init__(self):
        gobject.GObject.__init__(self)
        self._cache = None
        glib.timeout_add(100, self.open)
    def open(self):
        self._ready = False
        self.emit("cache-invalid")
        if self._cache == None:
            self._cache = apt.Cache(GtkMainIterationProgress())
        else:
            self._cache.open(GtkMainIterationProgress())
        self._ready = True
        self.emit("cache-ready")
    def __getitem__(self, key):
        return self._cache[key]
    def __iter__(self):
        return self._cache.__iter__()
    def __contains__(self, k):
        return self.cache.__contains__(k)
    def has_key(self, key):
        return self._cache.has_key(key)
    @property
    def ready(self):
        return self._ready

if __name__ == "__main__":
    c = AptCache()
