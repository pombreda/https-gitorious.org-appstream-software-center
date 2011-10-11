#!/usr/bin/make

all: check #mago_test

check:
	xvfb-run ./test-all.sh

clean:
	find  ../data/xapian/ ./data/aptroot/var/lib/apt/lists/ \
	 ./data/aptroot/var/cache/apt/ ./data/test.db/ -type f | xargs rm -f
	rm -f .coverage*
	rm -rf coverage_html


# mago tests
mago_test:
	# -sv makes mago not buffer output
	PYTHONPATH=.. mago -sv mago/mago_simple.py

