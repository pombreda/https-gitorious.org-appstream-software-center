import apt
import apt_pkg
import xapian
import os, os.path

class DisplayNames:
    def info(self):
        """
        Return general information about the plugin.

        The information returned is a dict with various keywords:
         
         timestamp (required)
           the last modified timestamp of this data source.  This will be used
           to see if we need to update the database or not.  A timestamp of 0
           means that this data source is either missing or always up to date.
         values (optional)
           an array of dicts { name: name, desc: description }, one for every
           numeric value indexed by this data source.

        Note that this method can be called before init.  The idea is that, if
        the timestamp shows that this plugin is currently not needed, then the
        long initialisation can just be skipped.
        """
        file = apt_pkg.config.find_file("Dir::Cache::pkgcache")
        if not os.path.exists(file):
            return dict(timestamp = 0)
        return dict(
                timestamp = os.path.getmtime(file),
                values = [
                    dict(name = "display_name", desc = "display name")
                ])

    def doc(self):
        """
        Return documentation information for this data source.

        The documentation information is a dictionary with these keys:
          name: the name for this data source
          shortDesc: a short description
          fullDoc: the full description as a chapter in ReST format
        """
        return dict(
            name = "DisplayNames",
            shortDesc = "package display names indexed as values",
            fullDoc = """
            The DisplayNames data source indexes the package size and the installed
            size as the ``packagesize`` and ``installedsize`` Xapian values.
            """
        )

    def init(self, info, progress):
        """
        If needed, perform long initialisation tasks here.

        info is a dictionary with useful information.  Currently it contains
        the following values:

          "values": a dict mapping index mnemonics to index numbers

        The progress indicator can be used to report progress.
        """
        # Read the value indexes we will use
        values = info['values']
        self.val_display_name = values.get("display_name", -1)

    def index(self, document, pkg):
        """
        Update the document with the information from this data source.

        document  is the document to update
        pkg       is the python-apt Package object for this package
        """
        ver = pkg.candidate
        if ver is None: return

        # set flag if pkg is duplicated in app-install data
        if os.path.exists('/usr/share/app-install/desktop/' + ver.package.name):
            document.add_term('pkg_has_app')
            return

        if self.val_display_name != -1:
            name = ver.summary[0].upper() + ver.summary[1:]
            document.add_value(self.val_display_name, name);

    def indexDeb822(self, document, pkg):
        """
        Update the document with the information from this data source.

        This is alternative to index, and it is used when indexing with package
        data taken from a custom Packages file.

        document  is the document to update
        pkg       is the Deb822 object for this package
        """
        try:
            instSize = int(pkg["Installed-Size"])
            pkgSize = int(pkg["Size"])
        except:
            return

        if self.val_inst_size != -1:
            document.add_value(self.val_inst_size, xapian.sortable_serialise(instSize));
        if self.val_pkg_size != -1:
            document.add_value(self.val_pkg_size, xapian.sortable_serialise(pkgSize));

def init():
    """
    Create and return the plugin object.
    """
    return DisplayNames()
