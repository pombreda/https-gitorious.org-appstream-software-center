set title "Startup times"
set xlabel "Revision number"
set ylabel "Startup time [seconds]"
set term png size 800,600
set out 'startup-times.png'
# start with y-xais on 0
set yrange [0:]
set grid
plot "startup-times.dat" with linespoint using 1:2 
