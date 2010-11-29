set title "Startup times"
set xlabel "Revision number"
set ylabel "Startup time"
set term png size 800,600
set out 'startup-times.png'
plot "startup-times.dat" using 1:2 title "revno", "startup-times.dat" using 2:3 title "time"
