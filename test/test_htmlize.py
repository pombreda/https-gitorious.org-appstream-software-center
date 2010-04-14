#!/usr/bin/python

from softwarecenter.utils import htmlize_package_desc


d = """
File-roller is an archive manager for the GNOME environment. It allows you to:

* Create and modify archives.
* View the content of an archive.
* View a file contained in an archive.
* Extract files from the archive.
File-roller supports the following formats:
* Tar (.tar) archives, including those compressed with
  gzip (.tar.gz, .tgz), bzip (.tar.bz, .tbz), bzip2 (.tar.bz2, .tbz2),
  compress (.tar.Z, .taz), lzip (.tar.lz, .tlz), lzop (.tar.lzo, .tzo),
  lzma (.tar.lzma) and xz (.tar.xz)
* Zip archives (.zip)
* Jar archives (.jar, .ear, .war)
* 7z archives (.7z)
* iso9660 CD images (.iso)
* Lha archives (.lzh)
* Single files compressed with gzip (.gz), bzip (.bz), bzip2 (.bz2),
  compress (.Z), lzip (.lz), lzop (.lzo), lzma (.lzma) and xz (.xz)
File-roller doesn't perform archive operations by itself, but relies on standard tools for this.
"""


html_descr = "\n".join(htmlize_package_desc(d))
print html_descr
