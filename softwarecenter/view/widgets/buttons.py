import atk
import gtk
import gobject

from mkit import EM, Button, VLinkButton, EtchedLabel


class CategoryButton(Button):

    SPACING = 6
    BORDER_WIDTH = 2
    ICON_SIZE = gtk.ICON_SIZE_LARGE_TOOLBAR

    def __init__(self, label, iconname):
        Button.__init__(self)

        hb = gtk.HBox(spacing=CategoryButton.SPACING)
        hb.set_border_width(CategoryButton.BORDER_WIDTH)
        self.add(hb)

        hb.pack_start(gtk.image_new_from_icon_name(iconname,
                                                   CategoryButton.ICON_SIZE),
                                                   False)

        self.label = EtchedLabel(label)
        self.label.set_alignment(0, 0.5)
        self.label.set_padding(0, 6)
        hb.pack_start(self.label, False)

        self.label_list = ('label',)

        self.a11y = self.get_accessible()
        self.a11y.set_name(label)
        self.a11y.set_role(atk.ROLE_PUSH_BUTTON)

        self.connect('expose-event', self._on_expose)
        return

    def _on_expose(self, w, e):
        a = w.allocation

        if self.has_focus():
            w.style.paint_focus(w.window,
                                w.state,
                                w.allocation,
                                w,
                                'expander',
                                a.x, a.y,
                                a.width, a.height)
        return


class SubcategoryButton(VLinkButton):

    ICON_SIZE = 48
    MAX_WIDTH  = 12*EM
    MAX_HEIGHT = 9*EM

    def __init__(self, markup, icon_name, icons):
        VLinkButton.__init__(self,
                             markup,
                             icon_name,
                             SubcategoryButton.ICON_SIZE,
                             icons)

        self.set_border_width(3)
        self.set_max_width(SubcategoryButton.MAX_WIDTH)
        #self.set_max_width(SubcategoryButton.MAX_HEIGHT)
        self.box.set_size_request(SubcategoryButton.MAX_WIDTH,
                                  SubcategoryButton.MAX_HEIGHT)
        return
