#!/bin/bash
# 在服务器上：把两个容器里已完成的 figure.html 复制到评测目录，逐个截图测交互；再拉回本机 shots/。
# 用法：bash shoot_all.sh [--redo]
REDO=${1:-}
ssh -o LogLevel=ERROR gpu-server "bash -s" <<EOF
cd /srv/lab/anatomy
mkdir -p work_a/eval/pages
for d in work/runs/*_B* work_a/runs/*_A* work_a/runs/*_C*; do
  [ -f \$d/figure.html ] || continue
  n=\$(basename \$d)
  if [ -n "$REDO" ] || [ ! -f work_a/eval/shots/\$n/shoot.json ]; then
    rm -rf work_a/eval/pages/\$n && cp -r \$d work_a/eval/pages/\$n
    docker exec an-lab-a bash -lc "cd /work/eval && timeout 180 node shoot.mjs pages/\$n/figure.html shots/\$n"
  fi
done
EOF
mkdir -p shots
scp -q -r -o LogLevel=ERROR gpu-server:/srv/lab/anatomy/work_a/eval/shots/. shots/
ls shots
