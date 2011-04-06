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
import datetime
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
import thread
import weakref
import simplejson

from multiprocessing import Process, Queue

from softwarecenter.backend.rnrclient import RatingsAndReviewsAPI, ReviewDetails
from softwarecenter.db.database import Application
import softwarecenter.distro
from softwarecenter.utils import *
from softwarecenter.paths import *
from softwarecenter.enums import *
from piston_mini_client import APIError

from softwarecenter.netstatus import network_state_is_connected

LOG = logging.getLogger(__name__)

class ReviewStats(object):
    def __init__(self, app):
        self.app = app
        self.ratings_average = None
        self.ratings_total = 0
    def __repr__(self):
        return "[ReviewStats '%s' ratings_average='%s' ratings_total='%s']" % (self.app, self.ratings_average, self.ratings_total)

class UsefulnessCache(object):

    USEFULNESS_CACHE = {}
    
    def __init__(self):
        fname = "usefulness.p"
        self.USEFULNESS_CACHE_FILE = os.path.join(SOFTWARE_CENTER_CACHE_DIR,
                                                    fname)
        if os.path.exists(self.USEFULNESS_CACHE_FILE):
            try:
                self.USEFULNESS_CACHE = cPickle.load(open(self.USEFULNESS_CACHE_FILE))
            except:
                LOG.exception("usefulness cache load failure")
                os.rename(self.USEFULNESS_CACHE_FILE, self.USEFULNESS_CACHE_FILE+".fail")
    
    def save_usefulness_cache_file(self):
        """write the dict out to cache file"""
        cachedir = SOFTWARE_CENTER_CACHE_DIR
        try:
            if not os.path.exists(cachedir):
                os.makedirs(cachedir)
            cPickle.dump(self.USEFULNESS_CACHE,
                      open(self.USEFULNESS_CACHE_FILE, "w"))
            return True
        except:
            return False
    
    def add_usefulness_vote(self, review_id, useful):
        """pass a review id and useful boolean vote and save it into the dict, then try to save to cache file"""
        self.USEFULNESS_CACHE[str(review_id)] = useful
        if self.save_usefulness_cache_file():
            return True
        return False
    
    def check_for_usefulness(self, review_id):
        """pass a review id and get a True/False useful back or None if the review_id is not in the dict"""
        return self.USEFULNESS_CACHE.get(str(review_id))
    
    

class Review(object):
    """A individual review object """
    def __init__(self, app):
        # a softwarecenter.db.database.Application object
        self.app = app
        self.app_name = app.appname
        self.package_name = app.pkgname
        # the review items that the object fills in
        self.id = None
        self.language = None
        self.summary = ""
        self.review_text = ""
        self.package_version = None
        self.date_created = None
        self.rating = None
        self.reviewer_username = None
        self.reviewer_displayname = None
        self.version = ""
        self.usefulness_total = 0
        self.usefulness_favorable = 0
        # this will be set if tryint to submit usefulness for this review failed
        self.usefulness_submit_error = False
    def __repr__(self):
        return "[Review id=%s review_text='%s' reviewer_username='%s']" % (
            self.id, self.review_text, self.reviewer_username)
    def __cmp__(self, other):
        # first compare version, high version number first
        vc = version_compare(self.version, other.version)
        if vc != 0:
            return vc
        # then usefulness
        uc = cmp(self.usefulness_favorable, other.usefulness_favorable)
        if uc != 0:
            return uc
        # last is date
        t1 = datetime.datetime.strptime(self.date_created, '%Y-%m-%d %H:%M:%S')
        t2 = datetime.datetime.strptime(other.date_created, '%Y-%m-%d %H:%M:%S')
        return cmp(t1, t2)
        
    @classmethod
    def from_piston_mini_client(cls, other):
        """ converts the rnrclieent reviews we get into
            "our" Review object (we need this as we have more
            attributes then the rnrclient review object)
        """
        app = Application("", other.package_name)
        review = cls(app)
        for (attr, value) in other.__dict__.iteritems():
            if not attr.startswith("_"):
                setattr(review, attr, value)
        return review

    @classmethod
    def from_json(cls, other):
        """ convert json reviews into "out" review objects """
        app = Application("", other["package_name"])
        review = cls(app)
        for k, v in other.iteritems():
            setattr(review, k, v)
        return review

class ReviewLoader(object):
    """A loader that returns a review object list"""

    # cache the ReviewStats
    REVIEW_STATS_CACHE = {}

    def __init__(self, cache, db, distro=None):
        self.cache = cache
        self.db = db
        self.distro = distro
        if not self.distro:
            self.distro = softwarecenter.distro.get_distro()
        fname = "%s_%s" % (uri_to_filename(self.distro.REVIEWS_SERVER),
                           "review-stats-pkgnames.p")
        self.REVIEW_STATS_CACHE_FILE = os.path.join(SOFTWARE_CENTER_CACHE_DIR,
                                                    fname)
        self.language = get_language()
        if os.path.exists(self.REVIEW_STATS_CACHE_FILE):
            try:
                self.REVIEW_STATS_CACHE = cPickle.load(open(self.REVIEW_STATS_CACHE_FILE))
            except:
                LOG.exception("review stats cache load failure")
                os.rename(self.REVIEW_STATS_CACHE_FILE, self.REVIEW_STATS_CACHE_FILE+".fail")

    def get_reviews(self, application, callback):
        """run callback f(app, review_list) 
           with list of review objects for the given
           db.database.Application object
        """
        return []

    def update_review_stats(self, translated_application, stats):
        application = Application("", translated_application.pkgname)
        self.REVIEW_STATS_CACHE[application] = stats

    def get_review_stats(self, translated_application):
        """return a ReviewStats (number of reviews, rating)
           for a given application. this *must* be super-fast
           as it is called a lot during tree view display
        """
        # check cache
        application = Application("", translated_application.pkgname)
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

    # writing new reviews spawns external helper
    # FIXME: instead of the callback we should add proper gobject signals
    def spawn_write_new_review_ui(self, translated_app, version, iconname, 
                                  origin, parent_xid, datadir, callback):
        """ this spawns the UI for writing a new review and
            adds it automatically to the reviews DB """
        app = translated_app.get_untranslated_app(self.db)
        cmd = [os.path.join(datadir, SUBMIT_REVIEW_APP), 
               "--pkgname", app.pkgname,
               "--iconname", iconname,
               "--parent-xid", "%s" % parent_xid,
               "--version", version,
               "--origin", origin,
               "--datadir", datadir,
               ]
        if app.appname:
            # needs to be (utf8 encoded) str, otherwise call fails
            cmd += ["--appname", app.appname.encode("utf-8")]
        (pid, stdin, stdout, stderr) = glib.spawn_async(
            cmd, flags=glib.SPAWN_DO_NOT_REAP_CHILD, standard_output=True)
        glib.child_watch_add(pid, self._on_submit_review_finished, (app, stdout, callback))

    def spawn_report_abuse_ui(self, review_id, parent_xid, datadir, callback):
        """ this spawns the UI for reporting a review as inappropriate
            and adds the review-id to the internal hide list. once the
            operation is complete it will call callback with the updated
            review list
        """
        cmd = [os.path.join(datadir, REPORT_REVIEW_APP), 
               "--review-id", review_id,
               "--parent-xid", "%s" % parent_xid,
               "--datadir", datadir,
              ]
        (pid, stdin, stdout, stderr) = glib.spawn_async(
            cmd, flags=glib.SPAWN_DO_NOT_REAP_CHILD, standard_output=True)
        glib.child_watch_add(pid, self._on_report_abuse_finished, (review_id, callback))

    def spawn_submit_usefulness_ui(self, review_id, is_useful, parent_xid, datadir, callback):
        cmd = [os.path.join(datadir, SUBMIT_USEFULNESS_APP), 
               "--review-id", "%s" % review_id,
               "--is-useful", "%s" % int(is_useful),
               "--parent-xid", "%s" % parent_xid,
               "--datadir", datadir,
              ]
        (pid, stdin, stdout, stderr) = glib.spawn_async(
            cmd, flags=glib.SPAWN_DO_NOT_REAP_CHILD, standard_output=True)
        glib.child_watch_add(pid, self._on_submit_usefulness_finished, (review_id, is_useful, stdout, callback))

    # internal callbacks/helpers
    def _on_submit_review_finished(self, pid, status, (app, stdout_fd, callback)):
        """ called when submit_review finished, when the review was send
            successfully the callback is triggered with the new reviews
        """
        LOG.debug("_on_submit_review_finished")
        # read stdout from submit_review
        stdout = ""
        while True:
            s = os.read(stdout_fd, 1024)
            if not s: break
            stdout += s
        LOG.debug("stdout from submit_review: '%s'" % stdout)
        if os.WEXITSTATUS(status) == 0:
            try:
                review_json = simplejson.loads(stdout)
            except simplejson.decoder.JSONDecodeError:
                LOG.error("failed to parse '%s'" % stdout)
                return
            review = ReviewDetails.from_dict(review_json)
            # FIXME: ideally this would be stored in ubuntu-sso-client
            #        but it dosn't so we store it here
            save_person_to_config(review.reviewer_username)
            if not app in self._reviews: 
                self._reviews[app] = []
            self._reviews[app].insert(0, Review.from_piston_mini_client(review))
            callback(app, self._reviews[app])

    def _on_report_abuse_finished(self, pid, status, (review_id, callback)):
        """ called when report_absuse finished """
        if os.WEXITSTATUS(status) == 0:
            LOG.debug("hide id %s " % review_id)
            for (app, reviews) in self._reviews.iteritems():
                for review in reviews:
                    if str(review.id) == str(review_id):
                        # remove the one we don't want to see anymore
                        self._reviews[app].remove(review)
                        callback(app, self._reviews[app])
                        break

    def _on_submit_usefulness_finished(self, pid, status, (review_id, is_useful, stdout_fd, callback)):
        """ called when report_usefulness finished """
        exitcode = os.WEXITSTATUS(status)
        # "Created", "Updated", "Not modified" - 
        # once lp:~mvo/rnr-server/submit-usefulness-result-strings makes it
        response = os.read(stdout_fd, 512)
        if response == '"Not modified"':
            return
        if exitcode == 0:
            LOG.debug("usefulness id %s " % review_id)
            useful_votes = UsefulnessCache()
            useful_votes.add_usefulness_vote(review_id, is_useful)
            for (app, reviews) in self._reviews.iteritems():
                for review in reviews:
                    if str(review.id) == str(review_id):
                        # update usefulness, older servers do not send
                        # usefulness_{total,favorable} so we use getattr
                        review.usefulness_total = getattr(review, "usefulness_total", 0) + 1
                        if is_useful:
                            review.usefulness_favorable = getattr(review, "usefulness_favorable", 0) + 1
                        callback(app, self._reviews[app], useful_votes)
                        break
        else:
            LOG.debug("submit usefulness id=%s failed with exitcode %s" % (
                review_id, exitcode))
            for (app, reviews) in self._reviews.iteritems():
                for review in reviews:
                    if str(review.id) == str(review_id):
                        review.usefulness_submit_error = exitcode
                        callback(app, self._reviews[app])
                        break


# using multiprocessing here because threading interface was terrible
# slow and full of latency
class ReviewLoaderThreadedRNRClient(ReviewLoader):
    """ loader that uses multiprocessing to call rnrclient and
        a glib timeout watcher that polls periodically for the
        data 
    """

    def __init__(self, cache, db, distro=None):
        super(ReviewLoaderThreadedRNRClient, self).__init__(cache, db, distro)
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
        self.rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)
        self._reviews = {}
        # this is a dict of queue objects
        self._new_reviews = {}
        self._new_review_stats = Queue()

    def _update_rnrclient_offline_state(self):
        # this needs the lp:~mvo/piston-mini-client/offline-mode branch
        self.rnrclient._offline_mode = not network_state_is_connected()

    # reviews
    def get_reviews(self, translated_app, callback):
        """ public api, triggers fetching a review and calls callback
            when its ready
        """
        app = translated_app.get_untranslated_app(self.db)
        self._update_rnrclient_offline_state()
        self._new_reviews[app] = Queue()
        p = Process(target=self._get_reviews_threaded, args=(app, ))
        p.start()
        glib.timeout_add(500, self._reviews_timeout_watcher, app, callback)

    def _reviews_timeout_watcher(self, app, callback):
        """ watcher function in parent using glib """
        # another watcher collected the result already, nothing to do for
        # us (LP: #709548)
        if not app in self._new_reviews:
            return False
        # check if we have data waiting
        if not self._new_reviews[app].empty():
            self._reviews[app] = self._new_reviews[app].get()
            del self._new_reviews[app]
            callback(app, self._reviews[app])
            return False
        return True

    def _get_reviews_threaded(self, app):
        """ threaded part of the fetching """
        origin = self.cache.get_origin(app.pkgname)
        # special case for not-enabled PPAs
        if not origin and self.db:
            details = app.get_details(self.db)
            ppa = details.ppaname
            if ppa:
                origin = "lp-ppa-%s" % ppa.replace("/", "-")
        if not origin:
            return
        distroseries = self.distro.get_codename()
        try:
            kwargs = {"language":self.language, 
                      "origin":origin,
                      "distroseries":distroseries,
                      "packagename":app.pkgname,
                      }
            if app.appname:
                # FIXME: the appname will get quote_plus() later again,
                #        but it appears the server has currently a bug
                #        so it expects it this way
                kwargs["appname"] = urllib.quote_plus(app.appname.encode("utf-8"))
            piston_reviews = self.rnrclient.get_reviews(**kwargs)
            # the backend sometimes returns None here
            if piston_reviews is None:
                piston_reviews = []
        except simplejson.decoder.JSONDecodeError, e:
            LOG.error("failed to parse '%s'" % e.doc)
            piston_reviews = []
        #bug lp:709408 - don't print 404 errors as traceback when api request returns 404 error
        except APIError, e:
            LOG.warn("_get_reviews_threaded: no reviews able to be retrieved for package: %s (%s, origin: %s)" % (app.pkgname, distroseries, origin))
            LOG.debug("_get_reviews_threaded: no reviews able to be retrieved: %s" % e)
            piston_reviews = []
        except:
            LOG.exception("get_reviews")
            piston_reviews = []
        # add "app" attribute
        reviews = []
        for r in piston_reviews:
            reviews.append(Review.from_piston_mini_client(r))
        # push into the queue
        self._new_reviews[app].put(sorted(reviews, reverse=True))

    # stats
    def refresh_review_stats(self, callback):
        """ public api, refresh the available statistics """
        p = Process(target=self._refresh_review_stats_threaded, args=())
        p.start()
        glib.timeout_add(500, self._review_stats_timeout_watcher, callback)

    def _review_stats_timeout_watcher(self, callback):
        """ glib timeout that waits for the process that gets the data
            to finish and emits callback then """
        if not self._new_review_stats.empty():
            review_stats = self._new_review_stats.get()
            self.REVIEW_STATS_CACHE = review_stats
            callback(review_stats)
            self.save_review_stats_cache_file()
            return False
        return True

    def _refresh_review_stats_threaded(self):
        """ process that actually fetches the statistics """
        try:
            mtime = os.path.getmtime(self.REVIEW_STATS_CACHE_FILE)
            days_delta = int((time.time() - mtime) // (24*60*60))
            days_delta += 1
        except OSError:
            days_delta = 0
        LOG.debug("refresh with days_delta: %s" % days_delta)
        try:
            # depending on the time delta, use a different call
            if days_delta:
                piston_review_stats = self.rnrclient.review_stats(days_delta)
            else:
                piston_review_stats = self.rnrclient.review_stats()
        except:
            LOG.exception("refresh_review_stats")
            return
        # convert to the format that s-c uses
        review_stats = self.REVIEW_STATS_CACHE
        for r in piston_review_stats:
            s = ReviewStats(Application("", r.package_name))
            s.ratings_average = float(r.ratings_average)
            s.ratings_total = float(r.ratings_total)
            review_stats[s.app] = s
        # push into the queue in one, for all practical purposes there
        # is no limit for the queue size, even millions of review stats
        # are ok
        self._new_review_stats.put(review_stats)

class ReviewLoaderJsonAsync(ReviewLoader):
    """ get json (or gzip compressed json) """

    def _gio_review_download_complete_callback(self, source, result):
        app = source.get_data("app")
        callback = source.get_data("callback")
        try:
            (json_str, length, etag) = source.load_contents_finish(result)
        except glib.GError, e:
            # ignore read errors, most likely transient
            return callback(app, [])
        # check for gzip header
        if json_str.startswith("\37\213"):
            gz=gzip.GzipFile(fileobj=StringIO.StringIO(json_str))
            json_str = gz.read()
        reviews_json = simplejson.loads(json_str)
        reviews = []
        for review_json in reviews_json:
            print "review_json", review_json
            review = Review.from_json(review_json)
            reviews.append(review)
        # run callback
        callback(app, reviews)

    def get_reviews(self, app, callback):
        """ get a specific review and call callback when its available"""
        # FIXME: get this from the app details
        origin = self.cache.get_origin(app.pkgname)
        distroseries = self.distro.get_codename()
        if app.appname:
            appname = ";"+app.appname
        else:
            appname = ""
        url = self.distro.REVIEWS_URL % { 'pkgname' : app.pkgname,
                                          'appname' : urllib.quote_plus(appname.encode("utf-8")),
                                          'language' : self.language,
                                          'origin' : origin,
                                          'distroseries' : distroseries,
                                          'version' : 'any',
                                         }
        LOG.debug("looking for review at '%s'" % url)
        f=gio.File(url)
        f.set_data("app", app)
        f.set_data("callback", callback)
        f.load_contents_async(self._gio_review_download_complete_callback)

    # review stats code
    def _gio_review_stats_download_finished_callback(self, source, result):
        callback = source.get_data("callback")
        try:
            (json_str, length, etag) = source.load_contents_finish(result)
        except glib.GError, e:
            # ignore read errors, most likely transient
            return
        # check for gzip header
        if json_str.startswith("\37\213"):
            gz=gzip.GzipFile(fileobj=StringIO.StringIO(json_str))
            json_str = gz.read()
        review_stats_json = simplejson.loads(json_str)
        review_stats = {}
        for review_stat_json in review_stats_json:
            appname = review_stat_json["app_name"]
            pkgname = review_stat_json["package_name"]
            app = Application('', pkgname)
            stats = ReviewStats(app)
            stats.ratings_total = int(review_stat_json["ratings_total"])
            stats.ratings_average = float(review_stat_json["ratings_average"])
            review_stats[app] = stats
        # update review_stats dict
        self.REVIEW_STATS_CACHE = review_stats
        self.save_review_stats_cache_file()
        # run callback
        callback(review_stats)

    def refresh_review_stats(self, callback):
        """ get the review statists and call callback when its there """
        f=gio.File(self.distro.REVIEW_STATS_URL)
        f.set_data("callback", callback)
        f.load_contents_async(self._gio_review_stats_download_finished_callback)

class ReviewLoaderFake(ReviewLoader):

    USERS = ["Joe Doll", "John Foo", "Cat Lala", "Foo Grumpf", "Bar Tender", "Baz Lightyear"]
    SUMMARIES = ["Cool", "Medium", "Bad", "Too difficult"]
    IPSUM = "no ipsum\n\nstill no ipsum"

    def __init__(self, cache, db):
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
            for i in range(0, stats.ratings_total):
                review = Review(application)
                review.id = random.randint(1,50000)
                # FIXME: instead of random, try to match the avg_rating
                review.rating = random.randint(1,5)
                review.summary = self._random_summary()
                review.date_created = time.ctime(time.time())
                review.reviewer_username = self._random_person()
                review.review_text = self._random_text().replace("\n","")
                reviews.append(review)
            self._reviews_cache[application] = reviews
        reviews = self._reviews_cache[application]
        callback(application, reviews)
    def get_review_stats(self, application):
        if not application in self._review_stats_cache:
            stat = ReviewStats(application)
            stat.ratings_average = random.randint(1,5)
            stat.ratings_total = random.randint(1,20)
            self._review_stats_cache[application] = stat
        return self._review_stats_cache[application]
    def refresh_review_stats(self, callback):
        review_stats = []
        callback(review_stats)

class ReviewLoaderFortune(ReviewLoaderFake):
    def __init__(self, cache, db):
        ReviewLoaderFake.__init__(self, cache, db)
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
def get_review_loader(cache, db=None):
    """ 
    factory that returns a reviews loader singelton
    """
    global review_loader
    if not review_loader:
        try: # in the guest session this fails
            Queue()
            gio = False
        except:
            gio = True
        if "SOFTWARE_CENTER_IPSUM_REVIEWS" in os.environ:
            review_loader = ReviewLoaderIpsum(cache, db)
        elif "SOFTWARE_CENTER_FORTUNE_REVIEWS" in os.environ:
            review_loader = ReviewLoaderFortune(cache, db)
        elif "SOFTWARE_CENTER_TECHSPEAK_REVIEWS" in os.environ:
            review_loader = ReviewLoaderTechspeak(cache, db)
        elif gio or "SOFTWARE_CENTER_GIO_REVIEWS" in os.environ:
            review_loader = ReviewLoaderJsonAsync(cache, db)
        else:
            review_loader = ReviewLoaderThreadedRNRClient(cache, db)
    return review_loader

if __name__ == "__main__":
    def callback(app, reviews):
        print "app callback:"
        print app, reviews
    def stats_callback(stats):
        print "stats callback:"
        print stats
    # cache
    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()
    cache.open()
    # rnrclient loader
    app = Application("ACE", "unace")
    #app = Application("", "2vcard")
    loader = ReviewLoaderThreadedRNRClient(cache)
    print loader.refresh_review_stats(stats_callback)
    print loader.get_reviews(app, callback)
    
    print "default loader, press ctrl-c for next loader"
    gtk.main()

    # default loader
    app = Application("","2vcard")
    loader = get_review_loader(cache)
    loader.refresh_review_stats(stats_callback)
    loader.get_reviews(app, callback)
    import gtk
    gtk.main()
