import xapian

from softwarecenter.distro import get_distro
from softwarecenter.enums import (XapianValues,
                                  AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
                                  )


class AppFilter(xapian.MatchDecider):
    """
    Filter that can be hooked into xapian get_mset to filter for criteria that
    are based around the package details that are not listed in xapian
    (like installed_only) or archive section
    """
    def __init__(self, db, cache):
        xapian.MatchDecider.__init__(self)
        self.distro = get_distro()
        self.db = db
        self.cache = cache
        self.available_only = False
        self.supported_only = False
        self.installed_only = False
        self.not_installed_only = False
    @property
    def required(self):
        """ True if the filter is in a state that it should be part of a query """
        return (self.available_only or
                self.supported_only or
                self.installed_only or 
                self.not_installed_only)
    def set_available_only(self, v):
        self.available_only = v
    def set_supported_only(self, v):
        self.supported_only = v
    def set_installed_only(self, v):
        self.installed_only = v
    def set_not_installed_only(self, v):
        self.not_installed_only = v
    def get_supported_only(self):
        return self.supported_only
    def __eq__(self, other):
        if self is None and other is not None: 
            return True
        if self is None or other is None: 
            return False
        return (self.installed_only == other.installed_only and
                self.not_installed_only == other.not_installed_only and
                self.supported_only == other.supported_only)
    def __ne__(self, other):
        return not self.__eq__(other)
    def __call__(self, doc):
        """return True if the package should be displayed"""
        # get pkgname from document
        pkgname =  self.db.get_pkgname(doc)
        #logging.debug(
        #    "filter: supported_only: %s installed_only: %s '%s'" % (
        #        self.supported_only, self.installed_only, pkgname))
        if self.available_only:
            # an item is considered available if it is either found
            # in the cache or is available for purchase
            if (not pkgname in self.cache and 
                not doc.get_value(XapianValues.ARCHIVE_CHANNEL) == AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME):
                return False
        if self.installed_only:
            # use the lowlevel cache here, twice as fast
            lowlevel_cache = self.cache._cache._cache
            if (not pkgname in lowlevel_cache or
                not lowlevel_cache[pkgname].current_ver):
                return False
        if self.not_installed_only:
            if (pkgname in self.cache and
                self.cache[pkgname].is_installed):
                return False
        if self.supported_only:
            if not self.distro.is_supported(self.cache, doc, pkgname):
                return False
        return True