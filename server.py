#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATES = {
    "R": "Running",
    "S": "Sleeping",
    "D": "Uninterruptible sleep",
    "I": "Idle kernel thread",
    "T": "Stopped",
    "Z": "Zombie",
}


def run_command(*command):
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"LC_ALL": "C", "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
    ).stdout


def parse_memory(output):
    lines = output.splitlines()
    headings = lines[0].split()
    memory = dict(zip(headings, lines[1].split()[1:]))
    swap = dict(zip(headings, lines[2].split()[1:]))

    byte_output = run_command("free", "-b").splitlines()
    byte_headings = byte_output[0].split()
    byte_memory = dict(zip(byte_headings, byte_output[1].split()[1:]))
    total = int(byte_memory["total"])
    used = int(byte_memory["used"])

    return {
        "total": memory["total"],
        "used": memory["used"],
        "free": memory["free"],
        "shared": memory["shared"],
        "buff_cache": memory["buff/cache"],
        "available": memory["available"],
        "used_percent": round(used / total * 100, 1),
        "swap_total": swap["total"],
        "swap_used": swap["used"],
        "swap_free": swap["free"],
    }


def parse_top(output):
    lines = output.splitlines()
    cpu_line = next(line for line in lines if line.startswith("%Cpu(s):"))
    idle_match = re.search(r"([\d.]+)\s+id", cpu_line)
    cpu_percent = round(100.0 - float(idle_match.group(1)), 1) if idle_match else None

    header_index = next(i for i, line in enumerate(lines) if line.lstrip().startswith("PID "))
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
                "state": STATES.get(state_code, state_code),
                "cpu_percent": float(columns[8]),
                "memory_percent": float(columns[9]),
                "time": columns[10],
                "command": " ".join(columns[11:]),
            }
        )
        if len(processes) == 5:
            break

    return cpu_percent, processes


def collect_live_metrics():
    top_output = run_command("top", "-b", "-n", "1", "-w", "512")
    cpu_percent, processes = parse_top(top_output)
    return {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cpu_percent": cpu_percent,
        "memory": parse_memory(run_command("free", "-h")),
        "processes": processes,
    }


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/live":
            try:
                payload = json.dumps(collect_live_metrics()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)
            except (OSError, subprocess.SubprocessError, ValueError) as error:
                payload = json.dumps({"error": str(error)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)
            return

        super().do_GET()

    def end_headers(self):
        if self.path.endswith((".html", ".js", ".css", ".json")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description="Serve the live system dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Live dashboard: http://{args.host}:{args.port}")
    print("CPU, memory, and process data refresh every 2 seconds in the browser.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
