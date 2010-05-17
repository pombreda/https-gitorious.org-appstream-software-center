#!/usr/bin/python
import ldtp
import ldtputils
import os

# import the TestSuite class
from mago.test_suite.main import SingleApplicationTestSuite
from mago.application.main import Application 

class SoftwareCenterApp(Application):
    WINDOW       = "window_main"
    LAUNCHER     = "software-center"

    def do_search(self, search_term):
        application = ooldtp.context(self.name)
        # get search entry
        component = application.getchild("Search")
        # XXX add search with search_term
        return True


class SoftwareCenterTest(SingleApplicationTestSuite):

    APPLICATION_FACTORY = SoftwareCenterApp

    def setup(self):
        ldtp.waittillguinotexist(self.application.WINDOW, guiTimeOut=70)

    def teardown(self):
        ldtp.waittillguinotexist(self.application.WINDOW, guiTimeOut=70)

    def test_search(self):
        self.application.open(menu_schema)
        if self.do_search() == False:
            raise AssertionError, "Search failed"

if __name__ == "__main__":
     sc_test = SoftwareCenterTest()
     print sc_test, type(sc_test), dir(sc_test)
     print sc_test.application, type(sc_test.application), dir(sc_test.application)
     sc_test.run()
