# Copyright (C) 2009 Canonical
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

import apt
import apt_pkg
import atk
import gmenu
import gettext
import gobject
import gio
import glib
import logging
import os
import re
import urllib
import tempfile
import traceback
import time
import xml.sax.saxutils
import gtk
import dbus

from enums import USER_AGENT, MISSING_APP_ICON, APP_ICON_SIZE

# define additional entities for the unescape method, needed
# because only '&amp;', '&lt;', and '&gt;' are included by default
ESCAPE_ENTITIES = {"&apos;":"'",
                   '&quot;':'"'}
                   
LOG = logging.getLogger("softwarecenter.utils")


class ExecutionTime(object):
    """
    Helper that can be used in with statements to have a simple
    measure of the timming of a particular block of code, e.g.
    with ExecutinTime("db flush"):
        db.flush()
    """
    def __init__(self, info=""):
        self.info = info
    def __enter__(self):
        self.now = time.time()
    def __exit__(self, type, value, stack):
        logger = logging.getLogger("softwarecenter.performance")
        logger.debug("%s: %s" % (self.info, time.time() - self.now))


def log_traceback(info):
    """
    Helper that can be used as a debug helper to show what called
    the code at this place. Logs to softwarecenter.traceback
    """
    logger = logging.getLogger("softwarecenter.traceback")
    logger.debug("%s: %s" % (info, "".join(traceback.format_stack())))
    

def wait_for_apt_cache_ready(f):
    """ decorator that ensures that self.cache is ready using a
        gtk idle_add - needs a cache as argument
    """
    def wrapper(*args, **kwargs):
        self = args[0]
        # check if the cache is ready and 
        if not self.cache.ready:
            if hasattr(self, "app_view") and self.app_view.window:
                self.app_view.window.set_cursor(self.busy_cursor)
            glib.timeout_add(500, lambda: wrapper(*args, **kwargs))
            return False
        # cache ready now
        if hasattr(self, "app_view") and self.app_view.window:
            self.app_view.window.set_cursor(None)
        f(*args, **kwargs)
        return False
    return wrapper


def htmlize_package_desc(desc):
    def _is_bullet(line):
        return re.match("^(\s*[-*])", line)
    inside_p = False
    inside_li = False
    indent_len = None
    for line in desc.splitlines():
        stripped_line = line.strip()
        if (not inside_p and 
            not inside_li and 
            not _is_bullet(line) and
            stripped_line):
            yield '<p tabindex="0">'
            inside_p = True
        if stripped_line:
            match = re.match("^(\s*[-*])", line)
            if match:
                if inside_li:
                    yield "</li>"
                yield "<li>"
                inside_li = True
                indent_len = len(match.group(1))
                stripped_line = line[indent_len:].strip()
                yield stripped_line
            elif inside_li:
                if not line.startswith(" " * indent_len):
                    yield "</li>"
                    inside_li = False
                yield stripped_line
            else:
                yield stripped_line
        else:
            if inside_li:
                yield "</li>"
                inside_li = False
            if inside_p:
                yield "</p>"
                inside_p = False
    if inside_li:
        yield "</li>"
    if inside_p:
        yield "</p>"

def get_parent_xid(widget):
    while widget.get_parent():
        widget = widget.get_parent()
    return widget.window.xid

def get_language():
    """Helper that returns the current language
    """
    import locale
    # fallback if locale parsing fails
    FALLBACK = "en"
    # those languages need the full language-code, the other ones
    # can be abbreved
    FULL = ["pt_BR", 
            "zh_CN", "zh_TW"]
    try:
        language = locale.getdefaultlocale(('LANGUAGE','LANG','LC_CTYPE','LC_ALL'))[0]
    except Exception as e:
        logging.warn("Failed to get language: '%s'" % e)
        language = "C"
    # use fallback if we can't determine the language
    if language is None or language == "C":
        return FALLBACK
    if language in FULL:
        return language
    return language.split("_")[0]

def get_http_proxy_string_from_libproxy(url):
    """Helper that uses libproxy to get the http proxy for the given url """
    import libproxy
    pf = libproxy.ProxyFactory()
    proxies = pf.getProxies(url)
    # FIXME: how to deal with multiple proxies?
    proxy = proxies[0]
    if proxy == "direct://":
        return ""
    else:
        return proxy

def get_http_proxy_string_from_gconf():
    """Helper that gets the http proxy from gconf

    Returns: string with http://auth:pw@proxy:port/ or None
    """
    try:
        import gconf, glib
        client = gconf.client_get_default()
        if client.get_bool("/system/http_proxy/use_http_proxy"):
            authentication = ""
            if client.get_bool("/system/http_proxy/use_authentication"):
                user = client.get_string("/system/http_proxy/authentication_user")
                password = client.get_string("/system/http_proxy/authentication_password")
                authentication = "%s:%s@" % (user, password)
            host = client.get_string("/system/http_proxy/host")
            port = client.get_int("/system/http_proxy/port")
            http_proxy = "http://%s%s:%s/" %  (authentication, host, port)
            if host:
                return http_proxy
    except Exception:
        logging.exception("failed to get proxy from gconf")
    return None

def encode_for_xml(unicode_data, encoding="ascii"):
    """ encode a given string for xml """
    return unicode_data.encode(encoding, 'xmlcharrefreplace')

def decode_xml_char_reference(s):
    """ takes a string like 
        'Search&#x2026;' 
        and converts it to
        'Search...'
    """
    import re
    p = re.compile("\&\#x(\d\d\d\d);")
    return p.sub(r"\u\1", s).decode("unicode-escape")
    
def version_compare(a, b):
    return apt_pkg.version_compare(a, b)

def upstream_version_compare(a, b):
    return apt_pkg.version_compare(apt_pkg.upstream_version(a),
                                   apt_pkg.upstream_version(b))

def upstream_version(v):
    return apt_pkg.upstream_version(v)

def unescape(text):
    """
    unescapes the given text
    """
    return xml.sax.saxutils.unescape(text, ESCAPE_ENTITIES)

def get_current_arch():
    return apt_pkg.config.find("Apt::Architecture")

def uri_to_filename(uri):
    return apt_pkg.uri_to_filename(uri)

def human_readable_name_from_ppa_uri(ppa_uri):
    """ takes a PPA uri and returns a human readable name for it """
    from urlparse import urlsplit
    name = urlsplit(ppa_uri).path
    if name.endswith("/ubuntu"):
        return name[0:-len("/ubuntu")]
    return name

def sources_filename_from_ppa_entry(entry):
    """ 
    takes a PPA SourceEntry and returns a filename suitable for sources.list.d
    """
    from urlparse import urlsplit
    import apt_pkg
    name = "%s.list" % apt_pkg.URItoFileName(entry.uri)
    return name

def release_filename_in_lists_from_deb_line(debline):
    """
    takes a debline and returns the filename of the Release file
    in /var/lib/apt/lists
    """
    import aptsources.sourceslist
    entry = aptsources.sourceslist.SourceEntry(debline)
    name = "%s_dists_%s_Release" % (uri_to_filename(entry.uri), entry.dist)
    return name
    
def get_default_language():
    import locale
    locale = locale.getdefaultlocale()
    if not locale:
        return "en"
    if locale[0] == "C":
        return "en"
    return locale[0]
    
def is_unity_running():
    """
    return True if Unity is currently running
    """
    unity_running = False
    try:
        bus = dbus.SessionBus()
        unity_running = bus.name_has_owner("com.canonical.Unity")
    except:
        LOG.exception("could not check for Unity dbus service")
    return unity_running
    
def get_icon_from_theme(icons, iconname=None, iconsize=APP_ICON_SIZE, missingicon=MISSING_APP_ICON):
    """
    return the icon in the theme that corresponds to the given iconname
    """    
    if not iconname:
        iconname = missingicon
    try:
        icon = icons.load_icon(iconname, iconsize, 0)
    except Exception, e:
        LOG.warning("could not load icon '%s', displaying missing icon instead: %s " % (iconname, e))
        icon = icons.load_icon(missingicon, iconsize, 0)
    return icon
    
def get_file_path_from_iconname(icons, iconname=None, iconsize=APP_ICON_SIZE):
    """
    return the file path of the icon in the theme that corresponds to the
    given iconname, or None if it cannot be determined
    """
    if (not iconname or
        not icons.has_icon(iconname)):
        iconname = MISSING_APP_ICON
    try:
        icon_info = icons.lookup_icon(iconname, iconsize, 0)
    except Exception:
        icon_info = icons.lookup_icon(MISSING_APP_ICON, iconsize, 0)
    if icon_info is not None:
        icon_file_path = icon_info.get_filename()
        icon_info.free()
        return icon_file_path

def clear_token_from_ubuntu_sso(appname):
    """ send a dbus signal to the com.ubuntu.sso service to clear 
        the credentials for the given appname, e.g. _("Ubuntu Software Center")
    """
    import dbus
    bus = dbus.SessionBus()
    proxy = bus.get_object('com.ubuntu.sso', '/credentials')
    proxy.clear_token(appname)

def get_nice_date_string(cur_t):
    """ return a "nice" human readable date, like "2 minutes ago"  """
    import datetime
    dt = datetime.datetime.utcnow() - cur_t
    days = dt.days
    secs = dt.seconds

    if days < 1:

        if secs < 120:   # less than 2 minute ago
            s = _('a few minutes ago')   # dont be fussy

        elif secs < 3600:   # less than an hour ago
            s = gettext.ngettext("%(min)i minute ago",
                                 "%(min)i minutes ago",
                                 (secs/60)) % { 'min' : (secs/60) }

        else:   # less than a day ago
            s = gettext.ngettext("%(hours)i hour ago",
                                 "%(hours)i hours ago",
                                 (secs/3600)) % { 'hours' : (secs/3600) }

    elif days <= 5: # less than a week ago
        s = gettext.ngettext("%(days)i day ago",
                             "%(days)i days ago",
                             days) % { 'days' : days }

    else:   # any timedelta greater than 5 days old
        # YYYY-MM-DD
        s = cur_t.isoformat().split('T')[0]

    return s

def get_exec_line_from_desktop(desktop_file):
    for line in open(desktop_file):
        if line.startswith("Exec="):
            return line.split("Exec=")[1]

class SimpleFileDownloader(gobject.GObject):

    LOG = logging.getLogger("softwarecenter.simplefiledownloader")

    __gsignals__ = {
        "file-url-reachable"      : (gobject.SIGNAL_RUN_LAST,
                                     gobject.TYPE_NONE,
                                     (bool,),),

        "file-download-complete"  : (gobject.SIGNAL_RUN_LAST,
                                     gobject.TYPE_NONE,
                                     (str,),),

        "error"                   : (gobject.SIGNAL_RUN_LAST,
                                     gobject.TYPE_NONE,
                                     (gobject.TYPE_PYOBJECT,
                                      gobject.TYPE_PYOBJECT,),),
        }

    def __init__(self):
        gobject.GObject.__init__(self)
        self.tmpdir = None

    def download_file(self, url, dest_file_path=None):
        self.LOG.debug("download_file: %s %s" % (url, dest_file_path))
        if dest_file_path is None:
            if self.tmpdir is None:
                self.tmpdir = tempfile.mkdtemp(prefix="software-center-")
            dest_file_path = os.path.join(self.tmpdir, uri_to_filename(url))

        self.url = url
        self.dest_file_path = dest_file_path
        
        if os.path.exists(self.dest_file_path):
            self.emit('file-url-reachable', True)
            self.emit("file-download-complete", self.dest_file_path)
            return
        
        f = gio.File(url)
        # first check if the url is reachable
        f.query_info_async(gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                           self._check_url_reachable_and_then_download_cb)
                           
    def _check_url_reachable_and_then_download_cb(self, f, result):
        try:
            result = f.query_info_finish(result)
            self.emit('file-url-reachable', True)
            self.LOG.debug("file reachable %s" % self.url)
            # url is reachable, now download the file
            f.load_contents_async(self._file_download_complete_cb)
        except glib.GError, e:
            self.LOG.debug("file *not* reachable %s" % self.url)
            self.emit('file-url-reachable', False)
            self.emit('error', glib.GError, e)
        del f

    def _file_download_complete_cb(self, f, result, path=None):
        self.LOG.debug("file download completed %s" % self.dest_file_path)
        # The result from the download is actually a tuple with three 
        # elements (content, size, etag?)
        # The first element is the actual content so let's grab that
        try:
            content = f.load_contents_finish(result)[0]
        except gio.Error, e:
            # i witnissed a strange error[1], so make the loader robust in this
            # situation
            # 1. content = f.load_contents_finish(result)[0]
            #    gio.Error: DBus error org.freedesktop.DBus.Error.NoReply
            self.LOG.debug(e)
            self.emit('error', (gio.Error, e))
            return

        outputfile = open(self.dest_file_path, "w")
        outputfile.write(content)
        outputfile.close()
        self.emit('file-download-complete', self.dest_file_path)


class GMenuSearcher(object):

    def __init__(self):
        self._found = None
    def _search_gmenu_dir(self, dirlist, needle):
        for item in dirlist[-1].get_contents():
            mtype = item.get_type()
            if mtype == gmenu.TYPE_DIRECTORY:
                self._search_gmenu_dir(dirlist+[item], needle)
            elif item.get_type() == gmenu.TYPE_ENTRY:
                desktop_file_path = item.get_desktop_file_path()
                # direct match of the desktop file name and the installed
                # desktop file name
                if os.path.basename(desktop_file_path) == needle:
                    self._found = dirlist+[item]
                    return
                # if there is no direct match, take the part of the path after 
                # "applications" (e.g. kde4/amarok.desktop) and
                # change "/" to "_" and do the match again - this is what
                # the data extractor is doing
                if "applications/" in desktop_file_path:
                    path_after_applications = desktop_file_path.split("applications/")[1]
                    if needle == path_after_applications.replace("/","_"):
                        self._found = dirlist+[item]
                        return

                
    def get_main_menu_path(self, desktop_file, menu_files_list=None):
        if not desktop_file:
            return None
        # use the system ones by default, but allow override for
        # easier testing
        if menu_files_list is None:
            menu_files_list = ["applications.menu", "settings.menu"]
        for n in menu_files_list:
            tree = gmenu.lookup_tree(n)
            self._search_gmenu_dir([tree.get_root_directory()], 
                                   os.path.basename(desktop_file))
            if self._found:
                return self._found
        return None

        
if __name__ == "__main__":
    s = decode_xml_char_reference('Search&#x2026;')
    print s
    print type(s)
    print unicode(s)
