# -*- coding: utf-8 -*-

# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import gio
import gzip
import glib
import locale
import json
import random
import StringIO
import time
import weakref
import xml.dom.minidom

import softwarecenter.distro

from softwarecenter.db.database import Application
from softwarecenter.utils import *

class ReviewStats(object):
    def __init__(self, app):
        self.app = app
        self.rating = None
        self.nr_reviews = 0
        self.nr_ratings = 0
    def __repr__(self):
        return "[ReviewStats rating='%s' nr_ratings='%s', nr_reviews='%s']" % (self.rating, self.nr_ratings, self.nr_reviews)

class Review(object):
    """A individual review object """
    def __init__(self, app):
        # a softwarecenter.db.database.Application object
        self.app = app
        # the review items that the object fills in
        self.id = None
        self.language = None
        self.summary = None
        self.text = None
        self.date = None
        self.rating = None
        self.person = None
    def __repr__(self):
        return "[Review id=%s text='%s' person='%s']" % (self.id, self.text, self.person)
    def to_xml(self):
        return """<review review_app="%s" review_id="%s" review_language="%s" 
review_data="%s" review_rating="%s" review_person="%s">
<summary>%s</summary><text>%s</text></review>""" % (
            self.app, self.id, self.language, self.date, self.rating, 
            self.person, self.summary, self.text)

class ReviewLoader(object):
    """A loader that returns a review object list"""

    # cache the ReviewStats
    REVIEW_STATS_CACHE = weakref.WeakValueDictionary()

    def __init__(self, distro=None):
        self.distro = distro
        if not self.distro:
            self.distro = softwarecenter.distro.get_distro()

    def get_reviews(self, application, callback):
        """run callback f(app, review_list) 
           with list of review objects for the given
           db.database.Application object
        """
        return []

    def get_review_stats(self, application):
        """return a ReviewStats (number of reviews, rating)
           for a given application. this *must* be super-fast
           as it is called a lot during tree view display
        """
        # check cache
        if application in self.REVIEW_STATS_CACHE:
            return self.REVIEW_STATS_CACHE[application]
        # create new and add to cache
        stats = ReviewStats(application)
        self.REVIEW_STATS_CACHE[application]= stats
        return stats

class ReviewLoaderXMLAsync(ReviewLoader):
    """ get xml (or gzip compressed xml) """
    def _gio_review_input_callback(self, source, result):
        app = source.get_data("app")
        callback = source.get_data("callback")
        try:
            xml_str = source.read_finish(result)
        except glib.GError, e:
            # ignore read errors, most likely transient
            return callback(app, [])
        # check for gzip header
        if xml_str.startswith("\37\213"):
            gz=gzip.GzipFile(fileobj=StringIO.StringIO(xml_str))
            xml_str = gz.read()
        dom = xml.dom.minidom.parseString(xml_str)
        reviews = []
        for review_xml in dom.getElementsByTagName("review"):
            app = Application(review_xml.getAttribute("review_app"))
            review = Review(app)
            review.id = review_xml.getAttribute("review_id")
            review.date = review_xml.getAttribute("review_date")
            review.rating = review_xml.getAttribute("review_rating")
            review.person = review_xml.getAttribute("review_person")
            review.language = review_xml.getAttribute("review_language")
            review.summary = review_xml.getElementsByTagName("summary")[0].childNodes[0].data
            review.text = review_xml.getElementsByTagName("text")[0].childNodes[0].data
            reviews.append(review)
        # run callback
        callback(app, reviews)
    def _gio_review_read_callback(self, source, result):
        app = source.get_data("app")
        callback = source.get_data("callback")
        try:
            stream=source.read_finish(result)
        except glib.GError, e:
            # 404 means no review
            if e.code == 404:
                return callback(app, [])
            # raise other errors
            raise
        stream.set_data("app", app)
        stream.set_data("callback", callback)
        # FIXME: static size here as first argument sucks, but it seems
        #        like there is a bug in the python bindings, I can not pass
        #        -1 or anything like this
        stream.read_async(128*1024, self._gio_review_input_callback)
    def get_reviews(self, app, callback):
        url = self.distro.REVIEWS_URL % (
            hash_pkgname_for_changelogs(app.pkgname), app.pkgname, app.pkgname)
        f=gio.File(url)
        f.read_async(self._gio_review_read_callback)
        f.set_data("app", app)
        f.set_data("callback", callback)

class ReviewLoaderIpsum(ReviewLoader):
    """ a test review loader that does not do any network io
        and returns random lorem ipsum review texts
    """
    #This text is under public domain
    #Lorem ipsum
    #Cicero
    LOREM=u"""lorem ipsum "dolor" äöü sit amet consetetur sadipscing elitr sed diam nonumy
eirmod tempor invidunt ut labore et dolore magna aliquyam erat sed diam
voluptua at vero eos et accusam et justo duo dolores et ea rebum stet clita
kasd gubergren no sea takimata sanctus est lorem ipsum dolor sit amet lorem
ipsum dolor sit amet consetetur sadipscing elitr sed diam nonumy eirmod
tempor invidunt ut labore et dolore magna aliquyam erat sed diam voluptua at
vero eos et accusam et justo duo dolores et ea rebum stet clita kasd
gubergren no sea takimata sanctus est lorem ipsum dolor sit amet lorem ipsum
dolor sit amet consetetur sadipscing elitr sed diam nonumy eirmod tempor
invidunt ut labore et dolore magna aliquyam erat sed diam voluptua at vero
eos et accusam et justo duo dolores et ea rebum stet clita kasd gubergren no
sea takimata sanctus est lorem ipsum dolor sit amet

duis autem vel eum iriure dolor in hendrerit in vulputate velit esse
molestie consequat vel illum dolore eu feugiat nulla facilisis at vero eros
et accumsan et iusto odio dignissim qui blandit praesent luptatum zzril
delenit augue duis dolore te feugait nulla facilisi lorem ipsum dolor sit
amet consectetuer adipiscing elit sed diam nonummy nibh euismod tincidunt ut
laoreet dolore magna aliquam erat volutpat

ut wisi enim ad minim veniam quis nostrud exerci tation ullamcorper suscipit
lobortis nisl ut aliquip ex ea commodo consequat duis autem vel eum iriure
dolor in hendrerit in vulputate velit esse molestie consequat vel illum
dolore eu feugiat nulla facilisis at vero eros et accumsan et iusto odio
dignissim qui blandit praesent luptatum zzril delenit augue duis dolore te
feugait nulla facilisi

nam liber tempor cum soluta nobis eleifend option congue nihil imperdiet
doming id quod mazim placerat facer possim assum lorem ipsum dolor sit amet
consectetuer adipiscing elit sed diam nonummy nibh euismod tincidunt ut
laoreet dolore magna aliquam erat volutpat ut wisi enim ad minim veniam quis
nostrud exerci tation ullamcorper suscipit lobortis nisl ut aliquip ex ea
commodo consequat

duis autem vel eum iriure dolor in hendrerit in vulputate velit esse
molestie consequat vel illum dolore eu feugiat nulla facilisis

at vero eos et accusam et justo duo dolores et ea rebum stet clita kasd
gubergren no sea takimata sanctus est lorem ipsum dolor sit amet lorem ipsum
dolor sit amet consetetur sadipscing elitr sed diam nonumy eirmod tempor
invidunt ut labore et dolore magna aliquyam erat sed diam voluptua at vero
eos et accusam et justo duo dolores et ea rebum stet clita kasd gubergren no
sea takimata sanctus est lorem ipsum dolor sit amet lorem ipsum dolor sit
amet consetetur sadipscing elitr at accusam aliquyam diam diam dolore
dolores duo eirmod eos erat et nonumy sed tempor et et invidunt justo labore
stet clita ea et gubergren kasd magna no rebum sanctus sea sed takimata ut
vero voluptua est lorem ipsum dolor sit amet lorem ipsum dolor sit amet
consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore
et dolore magna aliquyam erat

consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore
et dolore magna aliquyam erat sed diam voluptua at vero eos et accusam et
justo duo dolores et ea rebum stet clita kasd gubergren no sea takimata
sanctus est lorem ipsum dolor sit amet lorem ipsum dolor sit amet consetetur
sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore et dolore
magna aliquyam erat sed diam voluptua at vero eos et accusam et justo duo
dolores et ea rebum stet clita kasd gubergren no sea takimata sanctus est
lorem ipsum dolor sit amet lorem ipsum dolor sit amet consetetur sadipscing
elitr sed diam nonumy eirmod tempor invidunt ut labore et dolore magna
aliquyam erat sed diam voluptua at vero eos et accusam et justo duo dolores
et ea rebum stet clita kasd gubergren no sea takimata sanctus est lorem
ipsum dolor sit amet"""
    USERS = ["Joe Doll", "John Foo", "Cat Lala", "Foo Grumpf", "Bar Tender", "Baz Lightyear"]
    SUMMARIES = ["Cool", "Medium", "Bad", "Too difficult"]
    def _random_person(self):
        return random.choice(self.USERS)
    def _random_text(self):
        return random.choice(self.LOREM.split("\n\n"))
    def _random_summary(self):
        return random.choice(self.SUMMARIES)
    def get_reviews(self, application, callback):
        reviews = []
        for i in range(0,random.randint(0,6)):
            review = Review(application)
            review.id = random.randint(1,500)
            review.rating = random.randint(1,5)
            review.summary = self._random_summary()
            review.date = time.ctime(time.time())
            review.person = self._random_person()
            review.text = self._random_text().replace("\n","")
            reviews.append(review)
        callback(application, reviews)

if __name__ == "__main__":
    def callback(app, reviews):
        print app, reviews
    from softwarecenter.db.database import Application
    app = Application("7zip",None)
    loader = ReviewLoaderIpsum()
    print loader.get_reviews(app, callback)
    print loader.get_review_stats(app)
    app = Application("totem","totem")
    loader = ReviewLoaderXMLAsync()
    loader.get_reviews(app, callback)
    import gtk
    gtk.main()
