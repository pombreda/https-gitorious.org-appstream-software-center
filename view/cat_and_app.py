
import gtk
import logging
import os
import xapian

from appview import *
from catview import *

def category_activated(iconview, path, app_view, label):
    (name, pixbuf, query) = iconview.get_model()[path]
    new_model = AppStore(iconview.xapiandb, 
                         iconview.icons, 
                         query, 
                         limit=0,
                         sort=True)
    app_view.set_model(new_model)
    label.set_text("%s items" % len(new_model))

if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)

    datadir = "/usr/share/app-install"

    xapian_base_path = "/var/cache/app-install"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    # now the categories
    cat_view = CategoriesView(datadir, db, icons)
    scroll_cat = gtk.ScrolledWindow()
    scroll_cat.add(cat_view)
    
    # and the apps
    app_store = AppStore(db, icons)
    app_view = AppView(app_store)
    scroll_app = gtk.ScrolledWindow()
    scroll_app.add(app_view)

    # status label
    label = gtk.Label()

    # and a status label
    
    # pack and show
    box = gtk.VBox()
    box.pack_start(scroll_cat)
    box.pack_start(scroll_app)
    box.pack_start(label, expand=False)

    # setup signals
    cat_view.connect("item-activated", category_activated, app_view, label)

    win = gtk.Window()
    win.add(box)
    win.set_size_request(600,400)
    win.show_all()

    gtk.main()
