
import logging
import subprocess

def get_distro():
    prefix = "distro"
    distro_id = subprocess.Popen(["lsb_release","-i","-s"], 
                                 stdout=subprocess.PIPE).communicate()[0].strip()
    logging.debug("get_distro: '%s'" % distro_id)
    distro_module = __import__(prefix+"."+distro_id)
    sub_distro_module = getattr(distro_module, distro_id)
    distro_class = getattr(sub_distro_module, distro_id)
    instance = distro_class()
    return instance


