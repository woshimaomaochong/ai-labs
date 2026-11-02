#!/bin/bash
# 跑一次爬虫，同时每 0.2 秒记下连到 443 端口的本地端口，最后数一共开过几个连接
e=$1
node /work/bench.mjs $e 1 30 > /tmp/r_$e.txt & P=$!
: > /tmp/ports_$e.txt
while kill -0 $P 2>/dev/null; do
  python3 -c '
for f in ("/proc/net/tcp", "/proc/net/tcp6"):
    for l in open(f).readlines()[1:]:
        p = l.split()
        if p[2].endswith(":01BB") and p[3] == "01": print(p[1])' >> /tmp/ports_$e.txt
  sleep 0.2
done
echo "$e $(cut -c1-100 /tmp/r_$e.txt) 共开过连接=$(sort -u /tmp/ports_$e.txt | wc -l)"
