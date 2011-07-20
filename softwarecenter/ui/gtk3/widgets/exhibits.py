from gi.repository import Gtk
from gi.repository import GObject

from softwarecenter.utils import SimpleFileDownloader

class ExhibitBanner(Gtk.Fixed):

    MIN_WIDTH  = 100

    def __init__(self):
        Gtk.Fixed.__init__(self)
        self.image = Gtk.Image()
        self.label = Gtk.Label()
        self.downloader = SimpleFileDownloader()
        self.downloader.connect(
            "file-download-complete", self._on_file_download_complete)
                                
    def _on_file_download_complete(self, downloader, path):
        self.image.set_from_file(path)

    def set_exhibit(self, exhibit):
        # FIXME:
        # - set background color
        # background image first
        self.downloader.download_file(exhibit.banner_url, use_cache=True)
        self.put(self.image, 0, 0)
        # then label on top
        self.label.set_text(exhibit.title_translated)
        self.put(self.label, exhibit.title_coords[0], exhibit.title_coords[1])
        # FIXME: set font name, colors, size (that is not exposed in the API)

if __name__ == "__main__":
    from mock import Mock

    win = Gtk.Window()
    win.set_size_request(600, 400)

    exhibit = Mock()
    exhibit.background_color = "#000000"
    exhibit.banner_url = "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=orangeubuntulogo.png"
    exhibit.date_created = "2011-07-20 08:49:15"
    exhibit.font_color = "#000000"
    exhibit.font_name = ""
    exhibit.id = 1
    exhibit.package_names = "apt,2vcard"
    exhibit.published = True
    exhibit.title_coords = [10, 10]
    exhibit.title_translated = "Some title"

    exhibit_banner = ExhibitBanner()
    exhibit_banner.set_exhibit(exhibit)
    win.add(exhibit_banner)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
