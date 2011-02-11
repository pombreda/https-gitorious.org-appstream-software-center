#!/usr/bin/make

all: check mago_test

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
	set -e; \
	rm -rf ../data/xapian


# mago tests
mago_test:
	# -sv makes mago not buffer output
	PYTHONPATH=.. mago -sv mago/test_with_mago.py

