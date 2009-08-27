
import apt
import glib
import gtk
import time

class GtkMainIterationProgress(apt.progress.OpProgress):
    """Progress that just runs the main loop"""
    def update(self, percent):
        while gtk.events_pending():
            gtk.main_iteration()

class AptCache(object):
    """ 
    A apt cache that opens in the background and keeps the UI alive
    """
    def __init__(self):
        self._cache = None
        glib.timeout_add(100, self.open)
    def open(self):
        self._ready = False
        if self._cache == None:
            self._cache = apt.Cache(GtkMainIterationProgress())
        else:
            self._cache.open(GtkMainIterationProgress())
        self._ready = True
    def __getitem__(self, key):
        return self._cache[key]
    def has_key(self, key):
        return self._cache.has_key(key)
    @property
    def ready(self):
        return self._ready
