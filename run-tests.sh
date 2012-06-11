#!/bin/sh

set -e

TESTS_DIR="tests"

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
    ##COVERAGE_CMDLINE="$COVERAGE run --parallel-mode"
    echo "No coverage for now."
fi

PYTHON="$XVFB_CMDLINE $COVERAGE_CMDLINE python -m unittest"

# and record failures here
OUTPUT=$TESTS_DIR"/output"

FAILED=""
run_tests_for_dir() {
    for i in $(find $1 -maxdepth 1 -name 'test_*.py'); do
        TEST_NAME=$(basename $i | cut -d '.' -f 1)
        TEST_PREFIX=$(echo `dirname $i` | sed -e s'/\//./g')
        printf '%-50s' "Testing $TEST_NAME..."
        if ! $PYTHON -v -c -b $TEST_PREFIX.$TEST_NAME > $OUTPUT/$TEST_NAME.out 2>&1; then
            FAILED="$FAILED $TEST_NAME"
            echo "[ FAIL ]"
        else
            echo "[  OK  ]"
            rm -f ${OUTPUT}/$file.out;
        fi
    done
}

if [ $# -gt 0 ]; then
    # run the requested tests if arguments were given,
    # otherwise run the whole suite
    # example of custom params (discover all the tests under the tests/gtk3 dir):

    # ./run-tests.sh discover -v -s tests/gtk3/

    # See http://docs.python.org/library/unittest.html#test-discovery
    # for more info.
    RUN_TESTS="$PYTHON $@"
    echo "Running the command: $RUN_TESTS"
    $RUN_TESTS
else
    # 2012-05-30, nessita: Ideally, we should be able to run the whole suite
    # using discovery, but there is too much interference between tests in
    # order to do so, so we need a new python process per test file.
    ##RUN_TESTS="$PYTHON discover -v -c -b"
    rm -rf $OUTPUT
    mkdir $OUTPUT
    run_tests_for_dir $TESTS_DIR
    run_tests_for_dir "$TESTS_DIR/gtk3"

    # gather the coverage data
    ##./gen-coverage-report.sh

    if [ -n "$FAILED" ]; then
        echo "FAILED: $FAILED"
        echo "Check ${OUTPUT}/ directory for the details"
        exit 1
    else
        echo "All OK!"
    fi
fi
