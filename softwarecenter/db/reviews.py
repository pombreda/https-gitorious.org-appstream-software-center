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

import cPickle
import gio
import gzip
import glib
import locale
import os
import json
import random
import StringIO
import subprocess
import time
import urllib
import weakref
import xml.dom.minidom

import softwarecenter.distro

from softwarecenter.db.database import Application
from softwarecenter.utils import *
from softwarecenter.paths import *

class ReviewStats(object):
    def __init__(self, app):
        self.app = app
        self.avg_rating = None
        self.nr_reviews = 0
    def __repr__(self):
        return "[ReviewStats '%s' rating='%s' nr_reviews='%s']" % (self.app, self.avg_rating, self.nr_reviews)

class Review(object):
    """A individual review object """
    def __init__(self, app):
        # a softwarecenter.db.database.Application object
        self.app = app
        # the review items that the object fills in
        self.id = None
        self.language = None
        self.summary = ""
        self.text = ""
        self.package_version = None
        self.date = None
        self.rating = None
        self.person = None
    def __repr__(self):
        return "[Review id=%s text='%s' person='%s']" % (self.id, self.text, self.person)
    def to_xml(self):
        return """<review app_name="%s" package_name="%s" id="%s" language="%s" 
data="%s" rating="%s" reviewer_name="%s">
<summary>%s</summary><text>%s</text></review>""" % (
            self.app.appname, self.app.pkgname,
            self.id, self.language, self.date, self.rating, 
            self.person, self.summary, self.text)

class ReviewLoader(object):
    """A loader that returns a review object list"""

    # cache the ReviewStats
    REVIEW_STATS_CACHE = {}
    REVIEW_STATS_CACHE_FILE = SOFTWARE_CENTER_CACHE_DIR+"/review-stats.p"

    def __init__(self, distro=None):
        self.distro = distro
        if not self.distro:
            self.distro = softwarecenter.distro.get_distro()
        self.language = get_language()
        if os.path.exists(self.REVIEW_STATS_CACHE_FILE):
            try:
                self.REVIEW_STATS_CACHE = cPickle.load(open(self.REVIEW_STATS_CACHE_FILE))
            except:
                logging.exception("review stats cache load failure")
                os.rename(self.REVIEW_STATS_CACHE_FILE, self.REVIEW_STATS_CACHE_FILE+".fail")

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
        return None

    def refresh_review_stats(self, callback):
        """ get the review statists and call callback when its there """
        pass

    def save_review_stats_cache_file(self):
        """ save review stats cache file in xdg cache dir """
        cachedir = SOFTWARE_CENTER_CACHE_DIR
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        cPickle.dump(self.REVIEW_STATS_CACHE,
                      open(self.REVIEW_STATS_CACHE_FILE, "w"))

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
            appname = review_xml.getAttribute("app_name")
            pkgname = review_xml.getAttribute("package_name")
            app = Application(appname, pkgname)
            review = Review(app)
            review.id = review_xml.getAttribute("id")
            review.date = review_xml.getAttribute("date")
            review.rating = review_xml.getAttribute("rating")
            review.person = review_xml.getAttribute("reviewer_name")
            review.language = review_xml.getAttribute("language")
            summary_elements = review_xml.getElementsByTagName("summary")
            if summary_elements and summary_elements[0].childNodes:
                review.summary = summary_elements[0].childNodes[0].data
            review_elements = review_xml.getElementsByTagName("text")
            if review_elements and review_elements[0].childNodes:
                review.text = review_elements[0].childNodes[0].data
            reviews.append(review)
        # run callback
        callback(app, reviews)

    def _gio_review_read_callback(self, source, result):
        app = source.get_data("app")
        callback = source.get_data("callback")
        try:
            stream=source.read_finish(result)
        except glib.GError, e:
            print e, source, result
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
        """ get a specific review and call callback when its available"""
        # FIXME: get this from the app details
        origin = "ubuntu"
        distroseries = self.distro.get_codename()
        url = self.distro.REVIEWS_URL % { 'pkgname' : app.pkgname,
                                          'appname' : app.appname,
                                          'language' : self.language,
                                          'origin' : origin,
                                          'distroseries' : distroseries,
                                         }
        print url
        #if app.appname:
        #    url += "/%s" % app.appname
        logging.debug("looking for review at '%s'" % url)
        f=gio.File(url)
        f.read_async(self._gio_review_read_callback)
        f.set_data("app", app)
        f.set_data("callback", callback)

    # review stats code
    def _gio_review_stats_input_callback(self, source, result):
        callback = source.get_data("callback")
        try:
            xml_str = source.read_finish(result)
        except glib.GError, e:
            # ignore read errors, most likely transient
            return
        # check for gzip header
        if xml_str.startswith("\37\213"):
            gz=gzip.GzipFile(fileobj=StringIO.StringIO(xml_str))
            xml_str = gz.read()
        dom = xml.dom.minidom.parseString(xml_str)
        review_stats = {}
        # FIXME: look at root element like:
        #  "<review-statistics origin="ubuntu" distroseries="lucid" language="en">"
        # to verify we got the data we expected
        for review_stats_xml in dom.getElementsByTagName("review"):
            appname = review_stats_xml.getAttribute("app_name")
            pkgname = review_stats_xml.getAttribute("package_name")
            app = Application(appname, pkgname)
            stats = ReviewStats(app)
            stats.nr_reviews = int(review_stats_xml.getAttribute("count"))
            stats.avg_rating = float(review_stats_xml.getAttribute("average"))
            review_stats[app] = stats
        # update review_stats dict
        self.REVIEW_STATS_CACHE = review_stats
        self.save_review_stats_cache_file()
        # run callback
        callback()

    def _gio_review_stats_read_callback(self, source, result):
        callback = source.get_data("callback")
        try:
            stream=source.read_finish(result)
        except glib.GError, e:
            print e, source, result
            raise
        stream.set_data("callback", callback)
        # FIXME: static size here as first argument sucks, but it seems
        #        like there is a bug in the python bindings, I can not pass
        #        -1 or anything like this
        stream.read_async(128*1024, self._gio_review_stats_input_callback)

    def refresh_review_stats(self, callback):
        """ get the review statists and call callback when its there """
        distroseries = self.distro.get_codename()
        url = self.distro.REVIEW_STATS_URL % { 'language' : language,
                                               'origin' : origin,
                                               'distroseries' : distroseries,
                                             }
        f=gio.File(url)
        f.set_data("callback", callback)
        f.read_async(self._gio_review_stats_read_callback)

class ReviewLoaderFake(ReviewLoader):

    USERS = ["Joe Doll", "John Foo", "Cat Lala", "Foo Grumpf", "Bar Tender", "Baz Lightyear"]
    SUMMARIES = ["Cool", "Medium", "Bad", "Too difficult"]
    IPSUM = "no ipsum\n\nstill no ipsum"

    def __init__(self):
        self._review_stats_cache = {}
        self._reviews_cache = {}
    def _random_person(self):
        return random.choice(self.USERS)
    def _random_text(self):
        return random.choice(self.LOREM.split("\n\n"))
    def _random_summary(self):
        return random.choice(self.SUMMARIES)
    def get_reviews(self, application, callback):
        if not application in self._review_stats_cache:
            self.get_review_stats(application)
        stats = self._review_stats_cache[application]
        if not application in self._reviews_cache:
            reviews = []
            for i in range(0, stats.nr_reviews):
                review = Review(application)
                review.id = random.randint(1,50000)
                # FIXME: instead of random, try to match the avg_rating
                review.rating = random.randint(1,5)
                review.summary = self._random_summary()
                review.date = time.ctime(time.time())
                review.person = self._random_person()
                review.text = self._random_text().replace("\n","")
                reviews.append(review)
            self._reviews_cache[application] = reviews
        reviews = self._reviews_cache[application]
        callback(application, reviews)
    def get_review_stats(self, application):
        if not application in self._review_stats_cache:
            stat = ReviewStats(application)
            stat.avg_rating = random.randint(1,5)
            stat.nr_reviews = random.randint(1,20)
            self._review_stats_cache[application] = stat
        return self._review_stats_cache[application]
    def refresh_review_stats(self, callback):
        review_stats = []
        callback(review_stats)

class ReviewLoaderFortune(ReviewLoaderFake):
    def __init__(self):
        ReviewLoaderFake.__init__(self)
        self.LOREM = ""
        for i in range(10):
            out = subprocess.Popen(["fortune"], stdout=subprocess.PIPE).communicate()[0]
            self.LOREM += "\n\n%s" % out

class ReviewLoaderTechspeak(ReviewLoaderFake):
    """ a test review loader that does not do any network io
        and returns random review texts
    """
    LOREM=u"""This package is using cloud based technology that will
make it suitable in a distributed environment where soup and xml-rpc
are used. The backend is written in C++ but the frontend code will
utilize dynamic languages lika LUA to provide a execution environment
based on JIT technology.

The software in this packages has a wonderful GUI, its based on OpenGL
but can alternative use DirectX (on plattforms were it is
available). Dynamic shading utilizes all GPU cores and out-of-order
thread scheduling is used to visualize the data optimally on multi
core systems.

The database support in tthis application is bleding edge. Not only
classical SQL techniques are supported but also object-relational
models and advanced ORM technology that will do auto-lookups based on
dynamic join/select optimizations to leverage sharded or multihosted
databases to their peak performance.

The Enterprise computer system is controlled by three primary main
processing cores cross linked with a redundant melacortz ramistat and
fourteen kiloquad interface modules. The core elements are based on
FTL nanoprocessor units arranged into twenty-five bilateral
kelilactirals with twenty of those units being slaved to the central
heisenfram terminal. . . . Now this is the isopalavial interface which
controls the main firomactal drive unit. . . .  The ramistat kiloquad
capacity is a function of the square root of the intermix ratio times
the sum of the plasma injector quotient.

The iApp is using the new touch UI that feels more natural then
tranditional window based offerings. It supports a Job button that
will yell at you when pressed and a iAmCool mode where the logo of
your new device blinks so that you attract maximum attention.

This app is a lifestyle choice.
It sets you apart from those who are content with bland UI designed
around 1990's paradigms.  This app represents you as a dynamic trend
setter with taste.  The carefully controlled user interface is
perfectly tailored to the needs of a new age individual, and extreme
care has been taken to ensure that all buttons are large enough for even the
most robust digits.

Designed with the web 2.0 and touch screen portable technologies in
mind this app is the ultimate in media experience.  With this
lifestyle application you extend your social media and search reach.
Exciting innovations in display and video reinvigorates the user
experience, offering beautifully rendered advertisements straight to
your finger tips. This has limitless possibilities and will permeate
every facet of your life.  Believe the hype."""

class ReviewLoaderIpsum(ReviewLoaderFake):
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

review_loader = None
def get_review_loader():
    """ 
    factory that returns a reviews loader singelton
    """
    global review_loader
    if not review_loader:
        if "SOFTWARE_CENTER_IPSUM_REVIEWS" in os.environ:
            review_loader = ReviewLoaderIpsum()
        elif "SOFTWARE_CENTER_FORTUNE_REVIEWS" in os.environ:
            review_loader = ReviewLoaderFortune()
        elif "SOFTWARE_CENTER_TECHSPEAK_REVIEWS" in os.environ:
            review_loader = ReviewLoaderTechspeak()
        else:
            review_loader = ReviewLoaderXMLAsync()
    return review_loader

if __name__ == "__main__":
    def callback(app, reviews):
        print "app callback:"
        print app, reviews
    def stats_callback(stats):
        print "stats:"
        print stats
    from softwarecenter.db.database import Application
    app = Application(None, "7zip")
    #loader = ReviewLoaderIpsum()
    #print loader.get_reviews(app, callback)
    #print loader.get_review_stats(app)
    app = Application("totem","totem")
    loader = ReviewLoaderXMLAsync()
    loader.get_review_stats(stats_callback)
    loader.get_reviews(app, callback)
    import gtk
    gtk.main()
