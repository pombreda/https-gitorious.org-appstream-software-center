#!/usr/bin/python
import ldtp
import ooldtp
import ldtputils
import os

# import the TestSuite class
from mago.test_suite.main import SingleApplicationTestSuite
from mago.application.main import Application 

class SoftwareCenterApp(Application):
    WINDOW       = "frmUbuntuSoftwareCenter"
    LAUNCHER     = "software-center"
    CLOSE_NAME   = "mnuClose"

    def do_search(self, search_term):
        application = ooldtp.context(self.name)
        # get search entry
        component = application.getchild("Search")
        # XXX add search with search_term
        return True


class SoftwareCenterTest(SingleApplicationTestSuite):

    APPLICATION_FACTORY = SoftwareCenterApp

    def setup(self):
        self.application.set_close_name(self.application.CLOSE_NAME)
        self.application.open()

    def teardown(self):
        self.application.close()

    def test_search(self, search_term):
        if self.application.do_search(search_term) == False:
            raise AssertionError, "Search failed"

if __name__ == "__main__":
     sc_test = SoftwareCenterTest()
     print sc_test, type(sc_test), dir(sc_test)
     print sc_test.application, type(sc_test.application), dir(sc_test.application)
     sc_test.run()
