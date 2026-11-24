#!/bin/bash
cd ~/cnproj && source venv/bin/activate
sudo ip link set dev lo mtu 1500
for L in 2.5 3 3.5 4 7 8 9 10; do
  sudo tc qdisc del dev lo root 2>/dev/null
  sudo tc qdisc add dev lo root netem delay 25ms loss ${L}% limit 100000
  for i in 1 2 3 4; do python verify.py h3 > /dev/null 2>&1; done
  echo "== h3, 4 loads, configured $L% =="
  tc -s qdisc show dev lo | awk '/Sent/ {gsub(/[(),]/," "); print "sent=" $4, "dropped=" $7, "loss%=" $7/($4+$7)*100}'
done
sudo tc qdisc del dev lo root 2>/dev/null
sudo ip link set dev lo mtu 65536
