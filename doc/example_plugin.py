
import gtk

import softwarecenter.plugin

from gettext import gettext as _

class ExamplePlugin(softwarecenter.plugin.Plugin):
    """ mock plugin """

    VIEW_PAGE_EXAMPLE_PLUGIN = "view-page-example-plugin"

    def init_plugin(self):
        print "init_plugin"
        self.plugin_view = gtk.VBox()
        self.plugin_view.pack_start(gtk.Label("Hello from the example plugin"))
        self.app.view_manager.register(self.plugin_view, 
                                       self.VIEW_PAGE_EXAMPLE_PLUGIN)

        # FIXME: workaround for imperfect apps.py
        self.plugin_view.apps_filter = None

        # FIXME: this needs to get better
        model = self.app.view_switcher.get_model()
        icon = None
        parent_iter = None
        channel = None
        model.append(parent_iter, [icon, _("Example Plugin"), 
                                   self.VIEW_PAGE_EXAMPLE_PLUGIN, channel])
                     
