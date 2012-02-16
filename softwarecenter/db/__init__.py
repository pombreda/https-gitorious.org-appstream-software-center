import logging
try:
    from debfile import DebFileApplication
    DebFileApplication # pyflakes
except:
    logging.exception("DebFileApplication import")
    class DebFileApplication(): 
        pass
