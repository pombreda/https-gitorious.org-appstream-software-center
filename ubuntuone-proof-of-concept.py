import gtk

builder = gtk.Builder()
builder.add_from_file("Unsaved 2.ui")

builder.get_object("window1").show_all()
builder.get_object("window1").connect("delete-event", gtk.main_quit)
gtk.main()
