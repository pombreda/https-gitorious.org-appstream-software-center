#!/bin/sh

set -e

TESTS_DIR="./tests"

if [ ! -x /usr/bin/python-coverage ]; then
    echo "please install python-coverage"
    exit 1
fi

if [ ! -x /usr/bin/xvfb-run ]; then
    echo "please install xvfb"
    exit 1
fi

if ! python -c 'import mock'; then
    echo "please install python-mock"
    exit 1
fi

if ! python -c 'import unittest2'; then
    echo "please install python-unittest2"
    exit 1
fi

if ! python -c 'import aptdaemon.test'; then
    echo "please install python-aptdaemon.test"
    exit 1
fi

if ! python -c 'import lxml'; then
    echo "please install python-lxml"
    exit 1
fi

if ! python -c 'import PyQt4'; then
    echo "please install python-qt4"
    exit 1
fi


# clear coverage data
# coverage erase will not erase the files from --parallel-mode
rm -f $TESTS_DIR/.coverage*

# run with xvfb and coverage

XVFB_CMDLINE=""
XVFB=$(which xvfb-run)
if [ $XVFB ]; then
    XVFB_CMDLINE="$XVFB -a"
fi

COVERAGE_CMDLINE=""
COVERAGE=$(which python-coverage)
if [ $COVERAGE ]; then
    # If you are measuring coverage in a multi-process program, or across a
    # number of machines, you’ll want the --parallel-mode switch to keep the
    # data separate during measurement. See Combining data files below.
#    COVERAGE_CMDLINE="$COVERAGE run --parallel-mode"
    echo "No coverage for now."
fi

PYTHON="$XVFB_CMDLINE $COVERAGE_CMDLINE python -m unittest"

# and record failures here
OUTPUT=$TESTS_DIR"/output"
rm -rf $OUTPUT

# run the requested tests if arguments were given,
# otherwise run the whole suite
# example of custom params (discover all the tests under the tests/gtk3 dir):

# ./run-tests.sh discover -v -s tests/gtk3/

# See http://docs.python.org/library/unittest.html#test-discovery
# for more info.
if [ $# ]; then
    RUN_TESTS="$PYTHON $@"
else
    RUN_TESTS="$PYTHON discover -v -c -b"
fi

echo "Running the command: $RUN_TESTS"
$RUN_TESTS

# gather the coverage data
#./gen-coverage-report.sh
