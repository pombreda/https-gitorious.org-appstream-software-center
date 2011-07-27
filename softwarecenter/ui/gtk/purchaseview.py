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

from gi.repository import GObject
import gtk
import logging
import os
import simplejson
import sys
import urllib
import webkit

from gettext import gettext as _

from softwarecenter.backend import get_install_backend

LOG = logging.getLogger(__name__)

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

class PurchaseView(gtk.VBox):
    """ 
    View that displays the webkit-based UI for purchasing an item. 
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

    __gsignals__ = {
         'purchase-succeeded' : (GObject.SIGNAL_RUN_LAST,
                                 GObject.TYPE_NONE,
                                 ()),
         'purchase-failed'    : (GObject.SIGNAL_RUN_LAST,
                                 GObject.TYPE_NONE,
                                 ()),
         'purchase-cancelled-by-user' : (GObject.SIGNAL_RUN_LAST,
                                         GObject.TYPE_NONE,
                                         ()),
    }

    def __init__(self):
        gtk.VBox.__init__(self)
        self.wk = None
        self._wk_handlers_blocked = False

    def init_view(self):
        if self.wk is None:
            self.wk = ScrolledWebkitWindow()
            self.wk.webkit.connect("new-window-policy-decision-requested", self._on_new_window)
            # a possible way to do IPC (script or title change)
            self.wk.webkit.connect("script-alert", self._on_script_alert)
            self.wk.webkit.connect("title-changed", self._on_title_changed)
            self.wk.webkit.connect("notify::load-status", self._on_load_status_changed)
        # unblock signal handlers if needed when showing the purchase webkit view in
        # case they were blocked after a previous purchase was completed or canceled
        self._unblock_wk_handlers()

    def initiate_purchase(self, app, iconname, url=None, html=None):
        """
        initiates the purchase workflow inside the embedded webkit window
        for the item specified       
        """
        self.init_view()
        self.app = app
        self.iconname = iconname
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
            GObject.timeout_add_seconds(1, _generate_events, self)
        
    def _on_new_window(self, view, frame, request, action, policy):
        LOG.debug("_on_new_window")
        import subprocess
        subprocess.Popen(['xdg-open', request.get_uri()])
        return True

    def _on_script_alert(self, view, frame, message):
        self._process_json(message)
        # stop further processing to avoid actually showing the alter
        return True

    def _on_title_changed(self, view, frame, title):
        #print "on_title_changed", view, frame, title
        # see wkwidget.py _on_title_changed() for a code example
        self._process_json(title)

    def _on_load_status_changed(self, view, property_spec):
        """ helper to give visual feedback while the page is loading """
        prop = view.get_property(property_spec.name)
        if prop == webkit.LOAD_PROVISIONAL:
            if self.window:
                self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
        elif (prop == webkit.LOAD_FIRST_VISUALLY_NON_EMPTY_LAYOUT or
              prop == webkit.LOAD_FINISHED):
            if self.window:
                self.window.set_cursor(None)

    def _process_json(self, json_string):
        try:
            LOG.debug("server returned: '%s'" % json_string)
            res = simplejson.loads(json_string)
            #print res
        except:
            LOG.debug("error processing json: '%s'" % json_string)
            return
        if res["successful"] == False:
            if (res.get("user_canceled", False) or
                # note the different spelling
                res.get("user_cancelled", False) or
                # COMPAT with older clients that do not send the user
                #        canceled property (LP: #696861), this msg appears
                #        to be not translated
                "CANCELLED" in res.get("failures", "")):
                self.emit("purchase-cancelled-by-user")
                self._block_wk_handlers()
                return
            # this is what the agent implements
            elif "failures" in res:
                LOG.error("the server returned a error: '%s'" % res["failures"])
            # show a generic error, the "failures" string we get from the
            # server is way too technical to show, but we do log it
            self.emit("purchase-failed")
            self._block_wk_handlers()
            return
        else:
            self.emit("purchase-succeeded")
            self._block_wk_handlers()
            # gather data from response
            deb_line = res["deb_line"]
            signing_key_id = res["signing_key_id"]
            # add repo and key
            get_install_backend().add_repo_add_key_and_install_app(
                deb_line, signing_key_id, self.app, self.iconname)
                                                                   
    def _block_wk_handlers(self):
        # we need to block webkit signal handlers when we hide the
        # purchase webkit view, this prevents e.g. handling of signals on
        # title_change on reloads (see LP: #696861)
        if not self._wk_handlers_blocked:
            self.wk.webkit.handler_block_by_func(self._on_new_window)
            self.wk.webkit.handler_block_by_func(self._on_script_alert)
            self.wk.webkit.handler_block_by_func(self._on_title_changed)
            self.wk.webkit.handler_block_by_func(self._on_load_status_changed)
            self._wk_handlers_blocked = True
        
    def _unblock_wk_handlers(self):
        if self._wk_handlers_blocked:
            self.wk.webkit.handler_unblock_by_func(self._on_new_window)
            self.wk.webkit.handler_unblock_by_func(self._on_script_alert)
            self.wk.webkit.handler_unblock_by_func(self._on_title_changed)
            self.wk.webkit.handler_unblock_by_func(self._on_load_status_changed)
            self._wk_handlers_blocked = False
        

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
def _send_keys(view, s):
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
        event.window = view.window
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
def _generate_events(view):
    global STATES

    (state, title, keys) = STATES[0]

    print "_generate_events: in state", state

    current_title = view.wk.webkit.get_property("title")
    if current_title and current_title.startswith(title):
        print "found state", state
        _send_keys(view, keys)
        STATES.pop(0)

    return True

#     # for debugging only    
#    def _on_key_press(dialog, event):
#        print event, event.keyval

if __name__ == "__main__":
    #url = "http://www.animiertegifs.de/java-scripts/alertbox.php"
    url = "http://www.ubuntu.cohtml=DUMMY_m"
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
    #GObject.timeout_add_seconds(1, _generate_events, d)
    
    widget = PurchaseView()
    widget.initiate_purchase(app=None, iconname=None, url=url)
    #widget.initiate_purchase(app=None, iconname=None, html=DUMMY_HTML)


    window = gtk.Window()
    window.add(widget)
    window.set_size_request(600, 500)
    window.set_position(gtk.WIN_POS_CENTER)
    window.show_all()
    window.connect('destroy', gtk.main_quit)

    gtk.main()

