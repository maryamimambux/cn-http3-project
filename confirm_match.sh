#!/bin/bash
cd ~/cnproj && source venv/bin/activate
sudo ip link set dev lo mtu 1500
for CFG in "h2 2" "h3 3.25" "h2 5" "h3 8.5"; do
  set -- $CFG
  P=$1; L=$2
  sudo tc qdisc del dev lo root 2>/dev/null
  sudo tc qdisc add dev lo root netem delay 25ms loss ${L}% limit 100000
  for i in 1 2 3 4 5 6 7 8; do python verify.py $P > /dev/null 2>&1; done
  echo "== $P, 8 loads, configured $L% =="
  tc -s qdisc show dev lo | awk '/Sent/ {gsub(/[(),]/," "); print "sent=" $4, "dropped=" $7, "loss%=" $7/($4+$7)*100}'
done
sudo tc qdisc del dev lo root 2>/dev/null
sudo ip link set dev lo mtu 65536
