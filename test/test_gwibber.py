#!/usr/bin/python

import sys
import unittest
sys.path.insert(0,"../")

from gi.repository import Gwibber

class TestGwibber(unittest.TestCase):
    """ tests the "where is it in the menu" code """

    def setUp(self):
        pass

    def test_gwibber_helper(self):
        from softwarecenter.gwibber_helper import GwibberHelper
        gh = GwibberHelper()
        accounts = gh.accounts()
        print accounts
        gh.send_message ("test")

    def not_working_because_gi_does_not_provide_list_test_gwibber(self):
        #service = Gwibber.Service()
        #service.quit()
        # get account data
        accounts = Gwibber.Accounts()
        print dir(accounts)
        #print "list: ", accounts.list()
        # check single account for send enabled, only do if "True"
        #print accounts.send_enabled(accounts.list[0])
        # first check gwibber available
        service = Gwibber.Service()
        print dir(service)
        service.service_available(False)
        service.send_message ("test")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
