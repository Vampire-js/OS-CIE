#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p bin data

date --iso-8601=seconds > data/captured-at.txt
lscpu > data/lscpu.txt
free -h > data/free-h.txt
top -b -n 1 -w 512 > data/top.txt
ps -eLf > data/ps-eLf.txt
strace -c -o data/strace-c.txt /bin/ls data > data/strace-command-output.txt

cat > data/commands.txt <<'EOF'
lscpu > data/lscpu.txt
free -h > data/free-h.txt
top -b -n 1 -w 512 > data/top.txt
ps -eLf > data/ps-eLf.txt
strace -c -o data/strace-c.txt /bin/ls data > data/strace-command-output.txt
gcc -O2 -std=c11 -Wall -Wextra -pedantic locality.c -o bin/locality
./bin/locality --size 4096 --trials 7 > data/locality.json
python3 generate_results.py
EOF

gcc -O2 -std=c11 -Wall -Wextra -pedantic locality.c -o bin/locality
./bin/locality --size 4096 --trials 7 > data/locality.json
python3 generate_results.py

printf 'Dashboard data refreshed at %s\n' "$(cat data/captured-at.txt)"
printf 'Serve live dashboard with: python3 server.py\n'
