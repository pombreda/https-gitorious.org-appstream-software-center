# Copyright (C) 2010 Canonical
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

import gtk
import simplejson
import webkit

from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro

class PurchaseDialog(gtk.Dialog):

    def __init__(self, url=None, html=None):
        gtk.Dialog.__init__(self)
        self.set_size_request(500, 300)
        self.webkit = webkit.WebView()
        settings = self.webkit.get_settings()
        settings.set_property("enable-plugins", False)
        # a possible way to do IPC (script or title change)
        self.webkit.connect("script-alert", self._on_script_alert)
        self.webkit.connect("title-changed", self._on_title_changed)
        self.webkit.show()
        if url:
            self.webkit.load_uri(url)
        elif html:
            self.webkit.load_html_string(html, "file:///")
        self.vbox.pack_start(self.webkit)
        self.distro = get_distro()

    def run(self):
        return gtk.Dialog.run(self)

    def _on_script_alert(self, view, frame, message):
        print "on_script_alert", view, frame, message
        self._process_json(message)
        # stop further processing to avoid actually showing the alter
        return True

    def _on_title_changed(self, view, frame, title):
        print "on_title_changed", view, frame, title
        # see wkwidget.py _on_title_changed() for a code example
        self._process_json(title)

    def _process_json(self, json_string):
        res = simplejson.loads(json_string)
        print res
        if res["successful"] == False:
            self.response(gtk.RESPONSE_CANCEL)
        # FIXME: add auth key
        source_entry = res["apt_line"]
        backend = get_install_backend()
        backend.add_vendor_key_from_keyserver(res["signing_key_id"])
        backend.add_sources_list_entry(source_entry)
        backend.emit("channels-changed", True)
        backend.reload()
        # now queue installing the app
        backend.install(res["pkgname"], "", "")
        self.response(gtk.RESPONSE_OK)

if __name__ == "__main__":
    html = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
       "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
 <title></title>
</head>
<body>
 <script type="text/javascript">
  function changeTitle(title) { document.title = title; }
  function success() { changeTitle('{ "successful" : true, \
                                      "apt_line" : "deb https://private-ppa.launchapd.net/mvo/ubuntu lucid main", \
                                      "pkgname" : "2vcard" \
                                    }') }
  function cancel() { changeTitle('{ "successful" : "false" }') }
 </script>
 <h1>Purchase test</h1>
 <p>  Some text  </p>
 <input type="button" name="test_button2" 
        value="Button cancel"
      onclick='cancel()'
 />
 <input type="button" name="test_button" 
        value="Button ok"
      onclick='success()'
 />
</body>
</html>
    """
    #url = "http://www.animiertegifs.de/java-scripts/alertbox.php"
    #url = "http://www.ubuntu.com"
    d = PurchaseDialog(html=html)
    d.run()
