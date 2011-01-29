#!/usr/bin/env python

import distutils
import fnmatch
import glob
import os
import re
from subprocess import Popen, PIPE, call
import sys

from distutils.core import setup
from DistUtilsExtra.command import (build_extra, build_i18n, build_help,
                                    build_icons)


class PocketLint(distutils.cmd.Command):
    """ command class that runs pocketlint """
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def binary_in_path(self, binary):
        return any([os.path.exists(os.path.join(p, binary))
                    for p in os.environ["PATH"].split(":")])

    def run(self):
        if not self.binary_in_path("pocketlint"):
            sys.stderr.write("No pocketlint found in path\n"
                             "Use python-pocket-lint in natty or from "
                             "ppa:sinzui\n")
            return
        py_files = []
        for root, dirs, files in os.walk("."):
            pyl = fnmatch.filter(files, "*.py")
            py_files.extend([os.path.join(root, f) for f in pyl
                             if os.path.exists(os.path.join(root, f))])
        call(["pocketlint"]+py_files)


def merge_authors_into_about_dialog():
    fname="./data/ui/SoftwareCenter.ui"
    authors = open("AUTHORS").read()
    gtkbuilder = open(fname).read()
    gtkbuilder = re.sub(r'<property name="authors">.*</property>',
                        r'<property name="authors">%s</property>' % authors,
                        gtkbuilder)
    open(fname, "w").write(gtkbuilder)
    


# update version.py
line = open("debian/changelog").readline()
m = re.match("^[\w-]+ \(([\w\.~]+)\) ([\w-]+);", line)
VERSION = m.group(1)
CODENAME = m.group(2)
DISTRO = Popen(
    ["lsb_release", "-s", "-i"], stdout=PIPE).communicate()[0].strip()
RELEASE = Popen(
    ["lsb_release", "-s", "-r"], stdout=PIPE).communicate()[0].strip()
open("softwarecenter/version.py", "w").write("""
VERSION='%s'
CODENAME='%s'
DISTRO='%s'
RELEASE='%s'
""" % (VERSION, CODENAME, DISTRO, RELEASE))

# update po4a
if sys.argv[1] == "build":
    merge_authors_into_about_dialog()
    call(["po4a", "po/help/po4a.conf"])

# real setup
setup(name="software-center", version=VERSION,
      scripts=["software-center",
               "utils/submit_review.py",
               "utils/report_review.py",
               "utils/update-software-center",
               "utils/update-software-center-agent",
               ],
      packages = ['softwarecenter',
                  'softwarecenter.apt',
                  'softwarecenter.backend',
                  'softwarecenter.db',
                  'softwarecenter.distro',
                  'softwarecenter.models',
                  'softwarecenter.view',
                  'softwarecenter.view.widgets',
                 ],
      data_files=[
                  ('share/software-center/ui/',
                   glob.glob("data/ui/*.ui")),
                  ('share/software-center/templates/',
                   glob.glob("data/templates/*.html")),
                  ('../etc/dbus-1/system.d/',
                   ["data/com.ubuntu.SoftwareCenter.conf"]),
                  ('share/software-center/images/',
                   glob.glob("data/images/*.png")+
                   glob.glob("data/images/*.gif")),
                  ('share/software-center/icons/',
                   glob.glob("data/emblems/*.png")),
                  ('share/apt-xapian-index/plugins',
                   glob.glob("apt-xapian-index-plugin/*.py")),
                  ('share/application-registry',
                   ["data/software-center.applications"]),
                  ('../etc/firefox/pref/',
                   ["data/software-center.js"]),
#                  ('share/kde4/services/',
#                   ["data/apt.protocol"]),
                  ],
      cmdclass = {"build": build_extra.build_extra,
                  "build_i18n": build_i18n.build_i18n,
                  "build_help": build_help.build_help,
                  "build_icons": build_icons.build_icons,
                  "lint": PocketLint,
                 },
      )
