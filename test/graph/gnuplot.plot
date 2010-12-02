set title "Startup times"
set xlabel "Revision number"
set ylabel "Startup time [seconds]"
set term png size 800,600
set out 'startup-times.png'
# start with y-xais on 0
set yrange [0:]
set grid
plot "startup-times-gnuplot.dat" using 1:2:3:4 with yerrorbars \
 title "Startup time data", \
 "startup-times-gnuplot.dat" using 1:2 smooth csplines \
 with lines lt 3 title "Startup time trend"
