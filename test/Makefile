#!/usr/bin/make

all: check #mago_test

check:
	set -e; \
	find . -name 'test_*.py' | \
	while read file; do \
	    if [ -f $$file ]; then \
		echo "Testing $$file"; \
	    	python $$file ; \
	    fi \
	done

clean:
	find  ../data/xapian/ ./data/aptroot/var/lib/apt/lists/ \
	 ./data/aptroot/var/cache/apt/ ./data/test.db/ -type f | xargs rm -f


# mago tests
mago_test:
	# -sv makes mago not buffer output
	PYTHONPATH=.. mago -sv mago/mago_simple.py

