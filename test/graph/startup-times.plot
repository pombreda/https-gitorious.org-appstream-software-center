set title "Startup times"
set xlabel "Revision number"
set ylabel "Startup time"
set term png size 800,600
set out 'startup-times.png'
# start with y-xais on 0
# FIXME: figure out ymax automatically
set yrange [0:10]
set grid
plot "startup-times.dat" with linespoint using 1:2 title "revno", \
 "startup-times.dat" using 2:3 title "time"
