#!/usr/bin/env python3

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def read_text(name):
    return (DATA / name).read_text(encoding="utf-8")


def parse_lscpu():
    values = {}
    for line in read_text("lscpu.txt").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()

    flags = values.get("Flags", "").split()
    notable = [
        flag
        for flag in ("sse", "sse2", "sse4_1", "sse4_2", "avx", "avx2", "fma", "aes")
        if flag in flags
    ]
    return {
        "architecture": values.get("Architecture"),
        "op_modes": values.get("CPU op-mode(s)"),
        "byte_order": values.get("Byte Order"),
        "model": values.get("Model name"),
        "logical_cpus": values.get("CPU(s)"),
        "cores_per_socket": values.get("Core(s) per socket"),
        "threads_per_core": values.get("Thread(s) per core"),
        "sockets": values.get("Socket(s)"),
        "max_mhz": values.get("CPU max MHz"),
        "l1d_cache": values.get("L1d cache"),
        "l2_cache": values.get("L2 cache"),
        "l3_cache": values.get("L3 cache"),
        "isa_extensions": notable,
    }


def parse_memory():
    lines = read_text("free-h.txt").splitlines()
    headings = lines[0].split()
    memory_values = lines[1].split()[1:]
    swap_values = lines[2].split()[1:]
    memory = dict(zip(headings, memory_values))
    swap = dict(zip(headings, swap_values))

    top_text = read_text("top.txt")
    match = re.search(
        r"MiB Mem\s*:\s*([\d.]+) total,\s*([\d.]+) free,\s*"
        r"([\d.]+) used,\s*([\d.]+) buff/cache",
        top_text,
    )
    used_percent = None
    if match:
        total_mib = float(match.group(1))
        used_mib = float(match.group(3))
        used_percent = round(used_mib / total_mib * 100, 1)

    return {
        "total": memory.get("total"),
        "used": memory.get("used"),
        "free": memory.get("free"),
        "shared": memory.get("shared"),
        "buff_cache": memory.get("buff/cache"),
        "available": memory.get("available"),
        "used_percent": used_percent,
        "swap_total": swap.get("total"),
        "swap_used": swap.get("used"),
        "swap_free": swap.get("free"),
    }


def parse_processes():
    lines = read_text("top.txt").splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.lstrip().startswith("PID "))
    states = {
        "R": "Running",
        "S": "Sleeping",
        "D": "Uninterruptible sleep",
        "I": "Idle kernel thread",
        "T": "Stopped",
        "Z": "Zombie",
    }
    processes = []

    for line in lines[header_index + 1 :]:
        columns = line.split()
        if len(columns) < 12 or not columns[0].isdigit():
            continue
        state_code = columns[7]
        processes.append(
            {
                "pid": int(columns[0]),
                "user": columns[1],
                "state_code": state_code,
                "state": states.get(state_code, state_code),
                "cpu_percent": float(columns[8]),
                "memory_percent": float(columns[9]),
                "time": columns[10],
                "command": " ".join(columns[11:]),
            }
        )
        if len(processes) == 5:
            break

    return processes


def main():
    locality = json.loads(read_text("locality.json"))
    result = {
        "captured_at": read_text("captured-at.txt").strip(),
        "cpu": parse_lscpu(),
        "memory": parse_memory(),
        "processes": parse_processes(),
        "locality": locality,
        "commands": read_text("commands.txt").splitlines(),
        "raw_files": [
            "lscpu.txt",
            "free-h.txt",
            "top.txt",
            "ps-eLf.txt",
            "strace-c.txt",
            "locality.json",
        ],
    }
    (DATA / "results.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
