import gconf
import gtk
import logging
import tempfile
import time
import urllib

class GnomeProxyURLopener(urllib.FancyURLopener):
    """A urllib.URLOpener that honors the gnome proxy settings"""
    def __init__(self):
        proxies = {}
        import gconf
        client = gconf.client_get_default()
        if client.get_bool("/system/http_proxy/use_http_proxy"):
            host = client.get_string("/system/http_proxy/host")
            port = client.get_int("/system/http_proxy/port")
            proxies = { "http" : "http://%s:%s/" %  (host, port) }
        urllib.FancyURLopener.__init__(self, proxies)

class ShowImageDialog(gtk.Dialog):
    """A dialog that shows a image """

    def __init__(self, url, appname, parent=None):
        gtk.Dialog.__init__(self)
        # find parent window for the dialog
        if not parent:
            parent = self.get_parent()
            while parent:
                parent = w.get_parent()
        # image
        self.img = gtk.Image()
        self.img.show()
        # progress
        self.progress = gtk.ProgressBar()
        self.progress.show()
        # box
        vbox = gtk.VBox()
        vbox.pack_start(self.img)
        vbox.pack_start(self.progress, expand=False)
        vbox.show()
        # dialog
        self.set_transient_for(parent)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.get_content_area().add(vbox)
        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.set_default_size(400,400)
        self.set_title(appname)
        # install urlopener
        urllib._urlopener = GnomeProxyURLopener()
        # data
        self.fetched = 0.0
        self.url = url

    def run(self):
        self.show()
        self._load(self.url)
        gtk.Dialog.run(self)

    def _load(self, url):
        self.progress.show()
        self.progress.set_fraction(0.0)
        location = tempfile.NamedTemporaryFile()
        try:
            screenshot = urllib.urlretrieve(url, location.name, self._progress)
        except Exception, e:
            logging.exception("urlopen error")
            return
        # load into icon
        self.progress.hide()
        self.img.set_from_file(location.name)

    def _progress(self, count, block, total):
        #time.sleep(0.1)
        self.fetched += block
        # ensure we do not go over 100%
        percent = min(self.fetched/total, 1.0)
        self.progress.set_fraction(percent)
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    pkgname = "synaptic"
    url = "http://screenshots.debian.net/screenshot/synaptic"
    d = ShowImageDialog(url, pkgname)
    d.run()
