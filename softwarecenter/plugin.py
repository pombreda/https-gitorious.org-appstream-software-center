# Copyright (C) 2010 Canonical
#
# Authors:
#  Lars Wirzenius
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

import imp
import inspect
import logging
import os

class Plugin(object):

    """Base class for plugins.
    
    """
    def init(self):
        """ Init the plugin (UI, connect signals etc)
           
            This should be overwriten by the individual plugins
        """


class PluginManager(object):

    """Class to find and load plugins.
    
    Plugins are stored in files named '*_plugin.py' in the list of
    directories given to the initializer.
    
    """
    
    def __init__(self, app, plugin_dirs):
        self._app = app
        if isinstance(plugin_dirs, basestring):
            plugin_dirs = [plugin_dirs]
        self._plugin_dirs = plugin_dirs
        self._plugins = None

    def get_plugin_files(self):
        """Return all filenames in which plugins may be stored."""
        
        names = []
        for dirname in self._plugin_dirs:
            basenames = [x for x in os.listdir(dirname) 
                            if x.endswith(".py")]
            logging.debug("Plugin modules in %s: %s" % 
                            (dirname, " ".join(basenames)))
            names += [os.path.join(dirname, x) for x in basenames]
        
        return names

    def _find_plugins(self, module):
        """Find and instantiate all plugins in a module."""
        plugins = []
        for dummy, member in inspect.getmembers(module):
            if inspect.isclass(member) and issubclass(member, Plugin):
                plugins.append(member)
        logging.debug("Plugins in %s: %s" %
                      (module, " ".join(str(x) for x in plugins)))
        return [plugin() for plugin in plugins]

    def _load_module(self, filename):
        """Load a module from a filename."""
        logging.debug("Loading module %s" % filename)
        module_name, dummy = os.path.splitext(os.path.basename(filename))
        f = file(filename, "r")
        try:
            module = imp.load_module(module_name, f, filename,
                                     (".py", "r", imp.PY_SOURCE))
        except Exception, e: # pragma: no cover
            logging.warning("Failed to load plugin '%s' (%s)" % 
                            (module_name, e))
            return None
        f.close()
        return module

    @property
    def plugins(self):
        return self._plugins

    def load_plugins(self):
        """Return all plugins that have been found.
        """

        if self._plugins is None:
            self._plugins = []
            filenames = self.get_plugin_files()
            for i in range(len(filenames)):
                module = self._load_module(filenames[i])
                for plugin in self._find_plugins(module):
                    plugin.app = self._app
                    plugin.init()
                    self._plugins.append(plugin)
        # get the matching plugins
        plugins = [p for p in self._plugins]
        logging.debug("plugins are '%s'" % plugins)
        return plugins
