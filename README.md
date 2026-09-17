# Computer System Assessment Dashboard

This project captures system information from the machine where it is run,
measures 2D-array cache locality, and displays the results in a web dashboard.
All displayed measurements are generated from saved command output in `data/`.

## Run

```bash
./run.sh
python3 server.py
```

Open <http://localhost:8000>.

The page polls `/api/live` every two seconds. CPU usage, memory usage, and the
top five processes update without reloading the page. CPU identity and locality
timings remain tied to the last reproducible `./run.sh` capture.

`run.sh` executes and saves:

- `lscpu`
- `free -h`
- `top -b -n 1`
- `ps -eLf`
- `strace -c`
- the compiled locality benchmark

## Locality experiment

The benchmark allocates a `4096 x 4096` C array (64 MiB) in row-major layout.
It measures row-major and column-major summation over seven alternating trials,
flushes the cache between traversals, and reports the median. The checksum keeps
the compiler from removing the memory accesses.

Raw command output and benchmark timings remain available in `data/` for
inspection and live reproduction.
