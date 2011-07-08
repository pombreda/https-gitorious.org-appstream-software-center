from gi.repository import Gtk

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager
from softwarecenter.ui.gtk3.panes.viewswitcher import ViewSwitcher


class GlobalPane(Gtk.VBox):

    PADDING = StockEms.MEDIUM

    def __init__(self, view_manager, datadir, db, cache, icons):
        Gtk.VBox.__init__(self)
        self.top_hbox = Gtk.HBox(spacing=StockEms.XLARGE)
        self.top_hbox.set_border_width(self.PADDING)
        # add nav history back/forward buttons...
        # note:  this is hacky, would be much nicer to make the custom self/right
        # buttons in BackForwardButton to be Gtk.Activatable/Gtk.Widgets, then wire in the
        # actions using e.g. self.navhistory_back_action.connect_proxy(self.back_forward.left),
        # but couldn't seem to get this to work..so just wire things up directly
        vm = get_viewmanager()
        self.back_forward = vm.get_global_backforward()
        self.top_hbox.pack_start(self.back_forward, False, True, 0)

        self.view_switcher = ViewSwitcher(view_manager, datadir, db, cache, icons)
        self.top_hbox.pack_start(self.view_switcher, True, True, 0)

        #~ self.init_atk_name(self.searchentry, "searchentry")
        self.searchentry = vm.get_global_searchentry()
        self.top_hbox.pack_end(self.searchentry, False, True, 0)
        self.pack_start(self.top_hbox, False, True, 0)
        return
