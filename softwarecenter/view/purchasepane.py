# Copyright (C) 2010 Canonical
#
# Authors:
#  Michael Vogt
#  Gary Lasker
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

import glib
import gtk
import logging
import os
import simplejson
import sys
import urllib
import webkit

from softwarecenter.view.basepane import BasePane

from gettext import gettext as _

class ScrolledWebkitWindow(gtk.ScrolledWindow):

    def __init__(self):
        super(ScrolledWebkitWindow, self).__init__()
        self.webkit = webkit.WebView()
        settings = self.webkit.get_settings()
        settings.set_property("enable-plugins", False)
        self.webkit.show()
        # embed the webkit view in a scrolled window
        self.add(self.webkit)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

class PurchasePane(gtk.VBox, BasePane):
    """ 
    Pane that displays the UI for purchasing an item. 
    """
    
    LOADING_HTML = """
<html>
<head>
 <title></title>
</head>
<style type="text/css">
html {
  background: #fff;
  color: #000;
  font: sans-serif;
  font: caption;
  text-align: center;
  position: absolute;
  top: 0;
  bottom: 0;
  width: 100%%;
  height: 100%%;
  display: table;
}
body {
  display: table-cell;
  vertical-align: middle;
}
h1 {
  background: url(file:///usr/share/software-center/images/spinner.gif) top center no-repeat;
  padding-top: 48px; /* leaves room for the spinner above */
  font-size: 100%%;
  font-weight: normal;
}
</style>
<body>
 <h1>%s</h1>
</body>
</html>
""" % _("Connecting to payment service...")

    def __init__(self, app, iconname, url=None, html=None):
        gtk.VBox.__init__(self)
        self.set_title("")
        self.app = app
        self.iconname = iconname
        self.wk = ScrolledWebkitWindow()
        self.wk.webkit.connect("create-web-view", 
                               self._on_create_webview_request)
        # a possible way to do IPC (script or title change)
        self.wk.webkit.connect("script-alert", self._on_script_alert)
        self.wk.webkit.connect("title-changed", self._on_title_changed)
        self.wk.webkit.load_html_string(self.LOADING_HTML, "file:///")
        self.wk.show()
        while gtk.events_pending():
            gtk.main_iteration()
        if url:
            self.wk.webkit.load_uri(url)
        elif html:
            self.wk.webkit.load_html_string(html, "file:///")
        else:
            self.wk.webkit.load_html_string(DUMMY_HTML, "file:///")
        self.pack_start(self.wk)
        # only for debugging
        if os.environ.get("SOFTWARE_CENTER_DEBUG_BUY"):
            glib.timeout_add_seconds(1, _generate_events, self)
            
    def init_view(self):
        print "called PurchasePane.init_view.  TODO:  Implement or remove this."
        
    def set_title(self, title):
        print "called PurchasePane.set_title to '%s'.  TODO:  Implement.", title

    def _on_create_webview_request(self, view, frame, parent=None):
        logging.debug("_on_create_webview_request")
        popup = gtk.Dialog()
        popup.set_size_request(750,400)
        popup.set_title("")
        popup.set_modal(True)
        popup.set_transient_for(self)
        wk = ScrolledWebkitWindow()
        wk.show()
        popup.vbox.pack_start(wk)
        popup.show()
        return wk.webkit

    def run(self):
        return gtk.Dialog.run(self)

    def _on_script_alert(self, view, frame, message):
        print "on_script_alert", view, frame, message
        self._process_json(message)
        # stop further processing to avoid actually showing the alter
        return True

    def _on_title_changed(self, view, frame, title):
        #print "on_title_changed", view, frame, title
        # see wkwidget.py _on_title_changed() for a code example
        self._process_json(title)

    def _process_json(self, json_string):
        try:
            res = simplejson.loads(json_string)
            #print res
        except:
            logging.debug("error processing json: '%s'" % json_string)
            return
        if res["successful"] == False:
            self.hide()
            if res.get("user_canceled", False):
                # no need to show anything, the user did the
                # cancel
                pass
            # this is what the agent implements
            elif "failures" in res:
                logging.error("the server returned a error: '%s'" % res["failures"])
            # show a generic error, the "failures" string we get from the
            # server is way too technical to show, but we do log it
            dialogs.error(self,
                          _("Failure in the purchase process."),
                          _("Sorry, something went wrong. Your payment "
                            "has been cancelled."))
            self.response(gtk.RESPONSE_CANCEL)
            return

        self.response(gtk.RESPONSE_OK)
        # gather data from response
        deb_line = res["deb_line"]
        signing_key_id = res["signing_key_id"]
        # add repo and key
        get_install_backend().add_repo_add_key_and_install_app(deb_line,
                                                               signing_key_id,
                                                               self.app,
                                                               self.iconname)

# just used for testing --------------------------------------------
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

# synthetic key event generation
def _send_keys(dialog, s):
    print "_send_keys", s
    MAPPING = { '@'     : 'at',
                '.'     : 'period',
                '\t'    : 'Tab',
                '\n'    : 'Return',
                '?'     : 'question',
                '\a'    : 'Down',  # fake 
                ' '     : 'space',
                '\v'    : 'Page_Down', # fake
              }
    
    for key in s:
        event = gtk.gdk.Event(gtk.gdk.KEY_PRESS)
        event.window = dialog.window
        if key.isdigit():
            key = "_"+key
        if hasattr(gtk.keysyms, key):
            event.keyval = getattr(gtk.keysyms, key)
        else:
            event.keyval = getattr(gtk.keysyms, MAPPING[key])
        gtk.main_do_event(event)
  

# \a means down key - its a just a fake to get it working
LOGIN = os.environ.get("SOFTWARE_CENTER_LOGIN") or "michael.vogt@ubuntu.com"
# for some reason the "space" key before on checkbox does not work when
# the event is generated, so this needs to be done manually :/
PAYMENT_DETAILS = "\tstreet1\tstreet2\tcity\tstate\t1234\t\a\t\a\a\t"\
                  "ACCEPTED\t4111111111111111\t1234\t\a\t\a\a\t\t\t \v"
# state-name, window title, keys
STATES = [ ('login', 'Log in', LOGIN+"\t"),
           ('confirm-sso', 'Authenticate to', '\n'),
           ('enter-payment', 'Confirm Payment Details', PAYMENT_DETAILS),
           ('confirm-payment', 'title-the-same-as-before', '\t\n'),
           ('end-state', 'no-title', ''),
         ]
def _generate_events(dialog):
    global STATES

    (state, title, keys) = STATES[0]

    print "_generate_events: in state", state

    current_title = dialog.wk.webkit.get_property("title")
    if current_title and current_title.startswith(title):
        print "found state", state
        _send_keys(dialog, keys)
        STATES.pop(0)

    return True

def _on_key_press(dialog, event):
    print event, event.keyval

if __name__ == "__main__":
    #url = "http://www.animiertegifs.de/java-scripts/alertbox.php"
    #url = "http://www.ubuntu.com"
    #d = PurchaseDialog(app=None, html=DUMMY_HTML)
    #d = PurchaseDialog(app=None, url="http://spiegel.de")
    from softwarecenter.enums import BUY_SOMETHING_HOST
    url = BUY_SOMETHING_HOST+"/subscriptions/en/ubuntu/maverick/+new/?%s" % ( 
        urllib.urlencode({
                'archive_id' : "mvo/private-test", 
                'arch' : "i386",
                }))
    # use cmdline if available
    if len(sys.argv) > 1:
        url = sys.argv[1]
    # useful for debugging
    #d.connect("key-press-event", _on_key_press)
    #glib.timeout_add_seconds(1, _generate_events, d)
    
    widget = PurchasePane(app=None, iconname=None, html=DUMMY_HTML)
    widget.show()

    window = gtk.Window()
    window.add(widget)
    window.set_size_request(600, 500)
    window.set_position(gtk.WIN_POS_CENTER)
    window.show_all()
    widget.init_view()
    window.connect('destroy', gtk.main_quit)

    gtk.main()

