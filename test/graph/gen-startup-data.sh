#/bin/sh

LOGFILE=startup-times.dat
BASE_BZR=lp:software-center
FIRST_BZR_REV=1277
LAST_BZR_REV=$(bzr revno)
#LAST_BZR_REV=1278

if [ ! -e "$LOGFILE" ]; then 
    echo "# statup time log" > $LOGFILE
    echo "#revno    startup-time" >> $LOGFILE
fi

i=$FIRST_BZR_REV
while [ $i -lt $LAST_BZR_REV ]; do
    if [ ! -d rev-$i ]; then
        bzr get -r $i $BASE_BZR rev-$i
    fi
    cd rev-$i
    # first run is to warm up the cache and rebuild the DB (if needed)
    PYTHONPATH=. ./software-center --measure-startup-time
    # 3 runs with the given revision
    for testrun in 1 2 3 4 5; do
        echo -n "$i   " >> ../$LOGFILE
        PYTHONPATH=. ./software-center --measure-startup-time >> ../$LOGFILE
    done
    cd ..
    i=$((i+1))
done

# plot it
gnuplot startup-times.plot