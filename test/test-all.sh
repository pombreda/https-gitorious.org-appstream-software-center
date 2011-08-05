#!/bin/sh

set -e

OUTPUT="./output"
rm -rf $OUTPUT

FAILED=""
FILES=$(find . -name 'test_*.py')
for file in $FILES; do 
    if [ -f $file ]; then
	echo -n "Testing $file"
        mkdir -p ${OUTPUT}/$(dirname $file)
	if ! python $file  >output/$file.out 2>&1 ; then
	    FAILED="$FAILED $file"
	    echo " FAIL"
	else 
            echo " SUCCESS"
	    rm -f ${OUTPUT}/$file.out; 
	fi 
    fi 
done; 

if [ -n "$FAILED" ]; then 
    echo "FAILED: $FAILED"; 
    echo "Check ${OUTPUT}/ directory for the details"; 
    exit 1; 
fi
