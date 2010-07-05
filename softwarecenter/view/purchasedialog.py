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

    def __init__(self, app, url=None, html=None):
        gtk.Dialog.__init__(self)
        self.app = app
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
        else:
            self.webkit.load_html_string(DUMMY_HTML, "file:///")
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
        #print res
        if res["successful"] == False:
            self.response(gtk.RESPONSE_CANCEL)
            return
        self.response(gtk.RESPONSE_OK)
        # gather data from response
        source_entry = res["deb_line"]
        signing_key = res["signing_key_id"]
        # add repo and key
        backend = get_install_backend()
        backend.add_sources_list_entry(source_entry)
        backend.add_vendor_key_from_keyserver(signing_key)
        backend.emit("channels-changed", True)
        # teload to ensure we have the new package data
        backend.reload()
        # and then queue the install only when the reload finished
        # otherwise the daemon will fail because he does not know
        # the new package name yet
        self._reload_signal_id = backend.connect(
            "reload-finished", self._on_reload_finished, backend)

    def _on_reload_finished(self, trans, result, backend):
        """ 
        callback that is called once after reload was queued
        and will trigger the install of the for-pay package itself
        (after that it will automatically de-register)
        """
        backend.install(self.app.pkgname, self.app.appname, "")
        # disconnect again, this is only a one-time operation
        backend.handler_disconnect(self._reload_signal_id)
        self._reload_signal_id = None


# just used for testing
DUMMY_HTML = """
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
                                      "deb_line" : "deb https://user:pass@private-ppa.launchapd.net/mvo/ubuntu lucid main", \
                                      "package_name" : "2vcard", \
                                      "application_name" : "The 2vcard app", \
                                      "signing_key_id" : "1024R/0EB12F05"\
                                    }') }
  function cancel() { changeTitle('{ "successful" : "false" }') }
 </script>
 <h1>Purchase test page</h1>
 <p> To buy Frobunicator for 99$ you need to enter your credit card info</p>
 <p>  Enter your credit card info  </p>
 <p>
 <input type="entry">
 </p>
 <input type="button" name="test_button2" 
        value="Cancel"
      onclick='cancel()'
 />
 <input type="button" name="test_button" 
        value="Buy now"
      onclick='success()'
 />
</body>
</html>
    """

if __name__ == "__main__":
    #url = "http://www.animiertegifs.de/java-scripts/alertbox.php"
    #url = "http://www.ubuntu.com"
    d = PurchaseDialog(html=DUMMY_HTML)
    d.run()
