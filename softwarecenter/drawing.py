import math

from gtk.gdk import Color

PI = math.pi
PI_OVER_180 = PI/180


def color_floats(color):
    if isinstance(color, Color):
        c = color
    elif isinstance(color, str):
        c = Color(color)
    else:
        raise TypeError; print 'Expected gtk.gdk.Color or color hash...'
    return c.red_float, c.green_float, c.blue_float

def rounded_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(r+x, r+y, r, PI, 270*PI_OVER_180)
    cr.arc(x+w-r, r+y, r, 270*PI_OVER_180, 0)
    cr.arc(x+w-r, y+h-r, r, 0, 90*PI_OVER_180)
    cr.arc(r+x, y+h-r, r, 90*PI_OVER_180, PI)
    cr.close_path()
    return

def rounded_rect2(cr, x, y, w, h, radii):
    nw, ne, se, sw = radii

    cr.save()
    cr.translate(x, y)
    if nw:
        cr.new_sub_path()
        cr.arc(nw, nw, nw, PI, 270 * PI_OVER_180)
    else:
        cr.move_to(0, 0)
    if ne:
        cr.arc(w-ne, ne, ne, 270 * PI_OVER_180, 0)
    else:
        cr.rel_line_to(w-nw, 0)
    if se:
        cr.arc(w-se, h-se, se, 0, 90 * PI_OVER_180)
    else:
        cr.rel_line_to(0, h-ne)
    if sw:
        cr.arc(sw, h-sw, sw, 90 * PI_OVER_180, PI)
    else:
        cr.rel_line_to(-(w-se), 0)

    cr.close_path()
    cr.restore()
    return

def circle(cr, x, y, w, h):
    cr.new_path()

    r = min(w, h)*0.5
    x += int((w-2*r)/2)
    y += int((h-2*r)/2)

    cr.arc(r+x, r+y, r, 0, 360*PI_OVER_180)
    cr.close_path()
    return

def draw_tab(cr, x, y, w, h, r=7, rr=5):
    cr.new_sub_path()

    cr.arc_negative(x-rr, h+y-rr, rr, 90*PI_OVER_180, 0)

    cr.arc(r+x, r+y, r, PI, 270*PI_OVER_180)
    cr.arc(x+w-r, r+y, r, 270*PI_OVER_180, 0)

    cr.arc_negative(x+w+rr, h+y-rr, rr, PI, 90*PI_OVER_180)

#    cr.close_path()
    return
