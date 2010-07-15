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
import logging
import simplejson
import webkit

from gettext import gettext as _

from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro

class PurchaseDialog(gtk.Dialog):

    LOADING_HTML = """
<html>
<head>
 <title></title>
</head>
<body>
 <h1>%s</h1>
</body>
</html>
""" % _("Connecting to payment service...")

    def __init__(self, app, url=None, html=None):
        gtk.Dialog.__init__(self)
        self.set_title("")
        self.app = app
        self.set_size_request(700, 600)
        self.webkit = webkit.WebView()
        settings = self.webkit.get_settings()
        settings.set_property("enable-plugins", False)
        # a possible way to do IPC (script or title change)
        self.webkit.connect("script-alert", self._on_script_alert)
        self.webkit.connect("title-changed", self._on_title_changed)
        self.webkit.load_html_string(self.LOADING_HTML, "file:///")
        self.webkit.show()
        while gtk.events_pending():
            gtk.main_iteration()
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
        try:
            res = simplejson.loads(json_string)
            #print res
        except:
            logging.exception("error processing json")
            return
        if res["successful"] == False:
            self.response(gtk.RESPONSE_CANCEL)
            return
        self.response(gtk.RESPONSE_OK)
        # gather data from response
        source_entry = res["deb_line"]
        signing_key = res["signing_key_id"]
        # add repo and key
        get_install_backend().add_repo_add_key_and_install_app(source_entry,
                                                               signing_key,
                                                               self.app)

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
                                      "deb_line" : "deb https://user:pass@private-ppa.launchpad.net/mvo/ubuntu lucid main", \
                                      "package_name" : "2vcard", \
                                      "application_name" : "The 2vcard app", \
                                      "signing_key_id" : "1024R/0EB12F05"\
                                    }') }
  function cancel() { changeTitle('{ "successful" : false }') }
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
    d = PurchaseDialog(app=None, html=DUMMY_HTML)
    #d = PurchaseDialog(app=None, url="http://spiegel.de")
    d.run()
