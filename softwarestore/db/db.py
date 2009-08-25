

try:
    from appcenter.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from enums import *


class PackageDatabase(object):
    """abstraction for the various package data providers"""

    def __init__(self):
        pass


    
