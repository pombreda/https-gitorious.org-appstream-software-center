#/bin/sh

BASE_BZR=lp:software-center
FIRST_BZR_REV=1277
#LAST_BZR_REV=$(bzr revno)
LAST_BZR_REV=1278

i=$FIRST_BZR_REV
while [ $i -lt $LAST_BZR_REV ]; do
    if [ ! -d rev-$i ]; then
        bzr get -r $i $BASE_BZR rev-$i
    fi
    cd rev-$i
    # first run is to warm up the cache and rebuild the DB (if needed)
    PYTHONPATH=. ./software-center --measure-startup-time
    # 5 runs with the given revision
    for testrun in 1 2 3 4 5; do
        PYTHONPATH=. ./software-center --measure-startup-time >> startup_time.log
    done
    cd ..
    i=$((i+1))
done

