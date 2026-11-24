#!/bin/bash
cd ~/cnproj && source venv/bin/activate
sudo ip link set dev lo mtu 1500
for L in 2 5; do
 for P in h2 h3; do
  sudo tc qdisc del dev lo root 2>/dev/null
  sudo tc qdisc add dev lo root netem delay 25ms loss ${L}% limit 100000
  for i in 1 2 3; do python verify.py $P > /dev/null 2>&1; done
  echo "== $P, 3 loads at $L% =="
  tc -s qdisc show dev lo | awk '/Sent/ {gsub(/[(),]/," "); print "sent=" $4, "dropped=" $7, "loss%=" $7/($4+$7)*100}'
 done
done
sudo tc qdisc del dev lo root 2>/dev/null
sudo ip link set dev lo mtu 65536
