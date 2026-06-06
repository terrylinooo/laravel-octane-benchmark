#!/usr/bin/env python3
"""
Generate a FULL synthetic result set (real cell schema) so the dashboard can be
previewed without a 3-4h run. NOT real measurements — an internally consistent
model that reproduces the qualitative story the harness is built to surface:

  * /bench/hello: Octane crushes FPM (no per-request bootstrap)
  * CPU workloads (hash/mandelbrot/json): servers converge — compute dominates
  * RoadRunner edges the float workload (mandelbrot) -> the winner FLIPS
  * more workers (8) HURT CPU-bound work on a 2-cpu SUT (oversubscription)
  * /bench/db: Octane wins on persistent connections; FPM reconnect tax
  * FPM tail (p99) blows up + drops requests at c=128 on CPU work (error flag)
  * Peak RSS: FPM tiny, Octane large (framework resident across workers)

Writes results/*.json in the exact schema benchmark.sh produces, then you run
`python3 bench/aggregate.py` to build docs/. Delete results/ before a real run.
"""
import json
import math
import os
import random

random.seed(42)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
os.makedirs(RESULTS, exist_ok=True)

SERVERS = ["swoole", "openswoole", "roadrunner", "frankenphp", "fpm"]
WORKLOADS = ["hello", "hash", "mandelbrot", "json", "db"]
CONC = [8, 16, 32, 64, 128]
WORKERS = [4, 8]
RUNS = 2

MANIFEST = {
    "php": "8.4.21", "laravel": "v13.13.0", "octane": "v2.17.4",
    "worker_counts": "4 8", "caps": "cpus=2,cpuset=2-3,mem=4g",
    "commit": "983f68f", "host": "Linux 6.8.0-1015-azure x86_64 (ubuntu-24.04 runner)",
    "nproc": 4, "wrk_cmd": "wrk -t4 -d30s --timeout 15s --latency",
    "wrk_cpuset": "0", "mysql_cpuset": "1", "generator_isolated": True,
    "generated_at": "2026-06-04T12:00:00Z", "demo": True,
}
DURATION = 30.0

# base single-request latency (ms) per workload
BASE_LAT = {"hello": 0.85, "hash": 18.0, "mandelbrot": 28.0, "json": 16.0, "db": 2.6}
BODY = {"hello": 2, "hash": 90, "mandelbrot": 110, "json": 70, "db": 180}

# max sustainable throughput (req/s) per workload x server on the 2-cpu SUT
CAP = {
    "hello":      {"swoole": 9000, "openswoole": 8700, "frankenphp": 8200, "roadrunner": 6800, "fpm": 2400},
    "hash":       {"swoole": 108,  "openswoole": 107,  "frankenphp": 106,  "roadrunner": 104,  "fpm": 96},
    "mandelbrot": {"roadrunner": 73, "swoole": 72, "frankenphp": 71, "openswoole": 70, "fpm": 66},  # rr edges float
    "json":       {"swoole": 120,  "openswoole": 118,  "frankenphp": 112,  "roadrunner": 108,  "fpm": 100},
    "db":         {"swoole": 3400, "openswoole": 3300, "frankenphp": 2900, "roadrunner": 2700, "fpm": 1700},
}
CPU_WORKLOADS = {"hash", "mandelbrot", "json"}


def worker_factor(workload, workers):
    # 8 workers on a 2-cpu SUT: helps light/io work, hurts CPU-bound (oversubscription)
    if workers == 8:
        return 0.92 if workload in CPU_WORKLOADS else 1.06
    return 1.0


def rss_mib(server, workload, workers):
    base = {"swoole": 300, "openswoole": 296, "roadrunner": 250, "frankenphp": 220, "fpm": 52}[server]
    per_worker = {"swoole": 12, "openswoole": 12, "roadrunner": 9, "frankenphp": 8, "fpm": 4}[server]
    wl_extra = {"hello": 0, "hash": 6, "mandelbrot": 8, "json": 10, "db": 18}[workload]
    return int(base + per_worker * workers + wl_extra + random.uniform(-4, 4))


def cell(server, workload, workers, conc, run):
    cap = CAP[workload][server] * worker_factor(workload, workers)
    base_s = BASE_LAT[workload] / 1000.0
    sat = cap * base_s  # concurrency at half-saturation
    # saturating throughput: ~ c/base_lat at low c, -> cap at high c
    rps = cap * conc / (conc + sat)
    rps *= random.uniform(0.975, 1.025)
    mean_s = conc / rps
    mean_ms = mean_s * 1000.0
    overload = conc / sat
    tail99 = 2.1 + 0.55 * min(overload, 6)        # tail grows under load
    p = {
        "min": round(BASE_LAT[workload] * random.uniform(0.7, 0.9), 3),
        "mean": round(mean_ms, 3),
        "p50": round(mean_ms * 0.78, 3),
        "p75": round(mean_ms * 1.05, 3),
        "p90": round(mean_ms * 1.45, 3),
        "p95": round(mean_ms * 1.75, 3),
        "p99": round(mean_ms * tail99, 3),
        "p99_9": round(mean_ms * tail99 * 1.5, 3),
    }
    p["max"] = round(p["p99_9"] * random.uniform(1.2, 1.8), 3)
    p["stdev"] = round(mean_ms * 0.6, 3)

    requests = int(rps * DURATION)
    errors = {"connect": 0, "read": 0, "write": 0, "status": 0, "timeout": 0}
    # FPM drops a few requests under CPU saturation at the top concurrency
    if server == "fpm" and workload in CPU_WORKLOADS and conc == 128 and workers == 8:
        errors["timeout"] = random.randint(3, 12)
        errors["status"] = random.randint(0, 4)

    return {
        "server": server, "workload": workload, "route": f"/bench/{workload}",
        "workers": workers, "concurrency": conc, "run": run, "pinning": "verified",
        "wrk": {
            "requests": requests, "duration_s": DURATION, "bytes": requests * BODY[workload],
            "rps": round(rps, 2), "errors": errors,
            "latency_ms": {k: p[k] for k in
                           ["min", "max", "mean", "stdev", "p50", "p75", "p90", "p95", "p99", "p99_9"]},
        },
        "manifest": MANIFEST,
    }


def main():
    n = 0
    for workers in WORKERS:
        for server in SERVERS:
            for workload in WORKLOADS:
                for conc in CONC:
                    for run in range(1, RUNS + 1):
                        d = cell(server, workload, workers, conc, run)
                        fn = f"{server}_{workload}_w{workers}_c{conc}_r{run}.json"
                        with open(os.path.join(RESULTS, fn), "w") as fh:
                            json.dump(d, fh)
                        n += 1
                # rss sidecar
                rss = rss_mib(server, workload, workers)
                fn = f"{server}_{workload}_w{workers}_rss.json"
                with open(os.path.join(RESULTS, fn), "w") as fh:
                    json.dump({"server": server, "workload": workload, "workers": workers,
                               "peak_rss_bytes": rss * 1048576, "peak_rss_mib": rss,
                               "pinning": "verified"}, fh)
    print(f"Generated {n} demo cells + rss for "
          f"{len(SERVERS)} servers x {len(WORKLOADS)} workloads x {len(CONC)} conc x "
          f"{len(WORKERS)} worker-counts x {RUNS} runs into results/")


if __name__ == "__main__":
    main()
