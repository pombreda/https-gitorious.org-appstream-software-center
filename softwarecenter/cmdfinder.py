import os


class CmdFinder:

    def __init__(self, cache):
        self._cache = cache
        return

    def _is_exec(self, f):
        return os.path.exists(f) and not os.path.isdir(f) and os.access(f, os.X_OK)

    def _get_exec_candidates(self, pkg):
        return filter(lambda f: 'bin' in f and self._is_exec(f),
                      pkg.installed_files)

    def cmds_from_pkgname(self, pkgname):
        try:
            pkg = self._cache[pkgname]
        except KeyError, e:
            print e
            return []

        if not pkg.is_installed:
            return []

        return self._get_exec_candidates(pkg)


#~ 
#~ class CmdFinderWidget(gtk.VBox, CmdFinder):
#~ 
    #~ def __init__(self, cache):
        #~ CmdFinder.__init__(self, cache)
        #~ return
#~ 
    #~ def cmds_from_pkgname(self, pkgname):
        #~ cmds = CmdFinder.cmds_from_pkgname(self, pkgname)
        

if __name__ == '__main__':
    import apt
    c = apt.Cache()
    c.open()

    finder = CmdFinder(c)
    print 'Gimp:', finder.cmds_from_pkgname('gimp')
    print 'Monodevelop:', finder.cmds_from_pkgname('monodevelop')
    print 'twf:', finder.cmds_from_pkgname('thewidgetfactory')
