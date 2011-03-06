import atk
import gtk
import gobject
import pango
import pangocairo

from mkit import EM, Button, VLinkButton, EtchedLabel
from softwarecenter.drawing import color_floats


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


class SubcategoryEtchedLabel(gtk.Label):
    
    ETCHING_ALPHA = 0.85
    
    def __init__(self, *args, **kwargs):
        gtk.Label.__init__(self, *args, **kwargs)
        self.set_justify(gtk.JUSTIFY_CENTER)
        self.set_line_wrap(True)

        self.connect('expose-event', self._on_expose)
        return

    def _on_expose(self, widget, event):
        l = self.get_layout()
        a = widget.allocation

        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        cr.clip()

        pc = pangocairo.CairoContext(cr)
        w, h = a.width, a.height

        # calc label position
        lx, ly, lw, lh = l.get_pixel_extents()[1]

        x = a.x-lx
        y = a.y-ly

        if lw < w:
            x += int((w-lw)/2)

        # paint the bevel
        pc.move_to(x, y+1)
        pc.layout_path(l)
        r,g,b = color_floats(self.style.light[self.state])
        pc.set_source_rgba(r, g, b, self.ETCHING_ALPHA)
        pc.fill()

        # paint the foregorund text
        widget.style.paint_layout(widget.window,
                                  widget.state,
                                  True, # use text gc    
                                  a,    # allocation    
                                  widget,
                                  '',   # detail    
                                  x, y,
                                  l)    # layout
        return True


class SubcategoryButton(Button):

    SPACING = 6
    BORDER_WIDTH = 2
    ICON_SIZE = gtk.ICON_SIZE_DIALOG

    def __init__(self, label, iconname):
        Button.__init__(self)

        vb = gtk.VBox(spacing=SubcategoryButton.SPACING)
        vb.set_border_width(SubcategoryButton.BORDER_WIDTH)
        self.add(vb)

        vb.pack_start(gtk.image_new_from_icon_name(iconname,
                                                   SubcategoryButton.ICON_SIZE),
                                                   False)

        self.label = SubcategoryEtchedLabel(label)
        self.label.set_line_wrap(True)
        self.label.set_padding(0, 6)
        vb.pack_start(self.label, False)

        self.label_list = ('label',)

        self.a11y = self.get_accessible()
        self.a11y.set_name(label)
        self.a11y.set_role(atk.ROLE_PUSH_BUTTON)

        self.connect('expose-event', self._on_expose)
        #~ self.connect('expose-event', self._debug_on_expose)
    
        # cahce the initial layout width for testing label width
        vb.connect('size-allocate', self._on_size_allocate)
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

    def _debug_on_expose(self, widget, event):
        cr = widget.window.cairo_create()
        cr.rectangle(widget.allocation)
        cr.set_source_rgba(1, 0, 0, 0.7)
        cr.stroke()
        cr.rectangle(self.label.allocation)
        cr.set_source_rgba(0,0,1,0.7)
        cr.stroke()
        del cr
        return

    def _on_size_allocate(self, widget, allocation):
        self.label.set_size_request(allocation.width, 3*EM)
        return
