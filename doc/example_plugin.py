
import gtk
import sys

import softwarecenter.plugin
from softwarecenter.view.basepane import BasePane

from gettext import gettext as _

class ExamplePluginPane(gtk.VBox, BasePane):
    
    def __init__(self):
        gtk.VBox.__init__(self)
        self.pack_start(gtk.Label("Hello from the example plugin"))
    

class ExamplePlugin(softwarecenter.plugin.Plugin):
    """ mock plugin """

    VIEW_PAGE_EXAMPLE_PLUGIN = "view-page-example-plugin"

    def init_plugin(self):
        sys.stderr.write("init_plugin\n")
        self.plugin_view = ExamplePluginPane()
        self.app.view_manager.register(self.plugin_view, 
                                       self.VIEW_PAGE_EXAMPLE_PLUGIN)

        # FIXME: workaround for imperfect apps.py
        self.plugin_view.apps_filter = None

        # FIXME: this needs to get better
        model = self.app.view_switcher.get_model()
        icon = None
        parent_iter = None
        channel = None
        model.append(parent_iter, [icon,
                                   _("Example Plugin"), 
                                   self.VIEW_PAGE_EXAMPLE_PLUGIN, 
                                   channel, 
                                   None])
                     
