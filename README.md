# Laravel Octane Benchmark

A reproducible harness that benchmarks the Laravel Octane application servers
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) against a traditional
**PHP-FPM + nginx** control group — and shows *where each one wins*.

Most Octane benchmarks publish a single "fastest" number and contradict each other,
because they quietly differ on workload, worker count, load generator, and warm-vs-cold,
and rarely disclose any of it. This one fixes every confounding variable, discloses all
of them, and publishes **per-workload latency crossover curves**. The verdict is
explicitly "it depends — here's exactly how it depends. Go run it yourself."

> The methodology is the product. If you can't reproduce a number from its manifest,
> it's a bug.

## Results

Run it and open `docs/index.html` (charts) / `RESULTS.md` (tables). A published run
lives on the `gh-pages` branch.

These are **single-machine** results. Read them as **relative** (which server wins, and
at what concurrency the winner flips), not as absolute numbers for your hardware.

## What's measured

**Headline: p99 / p50 latency across a concurrency sweep.** Tail latency is where these
servers actually diverge; mean throughput is often within noise. Throughput (req/s) is
reported alongside. **Peak RSS** (memory high-water mark) is a secondary "VPS sizing"
metric. CPU% is deliberately *not* a headline — cgroup CPU sampling is too noisy to cite.

Each cell = `{server, workload, concurrency, run}` and is stored as one JSON file in
`results/` with an embedded manifest (pinned versions, caps, commit SHA, host, wrk flags)
so any data point is reproducible. Cells that recorded wrk errors (non-2xx / timeouts)
are flagged, never silently averaged in.

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| Workers | **8** everywhere (FPM `pm=static, max_children=8`) | same concurrency budget |
| CPU | **`cpus=4`, `cpuset=0-3`** per app container | each server gets the same 4 physical cores |
| Load generator | **`wrk` pinned to `cpuset=4-7`** | the generator never steals the server's CPU |
| Memory | `mem_limit=512m` | same ceiling |
| OPcache | enabled, `validate_timestamps=0` | code compiled once, like Octane keeps it |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | production code paths |
| Sessions | `SESSION_DRIVER=array` | stateless endpoints — nothing serializes on a write lock |
| Versions | pinned: PHP 8.4, Laravel 13, Octane 2.17 (see manifest) | no moving parts |

The harness runs **one app server at a time** (all others stopped) so its CPU/RAM are
measured in isolation, not under contention from idle siblings.

## Workloads

Workloads are organized into three **groups** so the charts and tables read as
"overhead → where the CPU goes → I/O". The three `cpu`-group routes each stress a
*different* instruction path, so they can disagree on which server wins.

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | routing + response overhead | fixed-length body |
| cpu | `/bench/hash` | integer / bitwise | `sha256` chaining ×`BENCH_HASH_ITERATIONS` (calibrate so it ≫ hello) |
| cpu | `/bench/mandelbrot` | float / FPU | escape-time Mandelbrot, 78×78 grid ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | serialization (codec) | `json_encode`+`json_decode` round-trip of a 1000-int array ×`BENCH_JSON_ITERATIONS` (codec dominates, not routing) |
| io | `/bench/db` | a real query | indexed PK `SELECT` vs **MySQL 8** |

**`/bench/db` caveat:** servers differ in connection handling (Swoole coroutine pool vs
RoadRunner vs FrankenPHP). This workload is scoped as **"each server's default Octane DB
behavior,"** not an isolated raw-query measurement. It's labeled as such on the chart.

## Run it

**Prerequisite:** Docker (Compose v2).

```bash
# Full matrix (5 servers × 5 workloads × concurrency 8/32/128 × 3 runs ≈ 4-5 hours).
# Resumable — a cell whose JSON exists is skipped, so a crash never restarts from zero.
./benchmark.sh

# Build the tables + charts from results/.
python3 bench/aggregate.py
#   -> RESULTS.md, docs/summary.json, docs/index.html

# Quick smoke run (a few minutes) to verify the pipeline end to end:
SERVERS="swoole fpm" WORKLOADS="hello db" CONCURRENCIES=8 RUNS=1 DURATION=5 WARMUP=2 ./benchmark.sh
```

Tunable via env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `RUNS`, `DURATION`, `WARMUP`,
`BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`.

## How it works

```
benchmark.sh ── per (server, workload):
  stop all app servers → start this one (+ mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → warm (discarded) → sweep concurrency × runs via the pinned wrk container
  → write results/{server}_{workload}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup memory high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Chart.js)
```

The `wrk` container runs a small Lua reporter (`docker/wrk/report.lua`) that emits one
JSON line with full latency percentiles and per-class error counts.

## Caveats

- **Single machine, relative not absolute.** Your numbers will differ; the *shape* (who
  wins where) is the portable finding.
- **Pinning self-check.** If the host doesn't honor `--cpuset-cpus`, every cell is tagged
  `pinning=unverified` and the result is not presented as generator-isolated.
- **`cpu`-group calibration.** `BENCH_HASH_ITERATIONS` (default 2000),
  `BENCH_MANDELBROT_REPEAT` (1), and `BENCH_JSON_ITERATIONS` (1000) should be tuned on
  your box so each `cpu`-group route's latency clearly dominates `/bench/hello`.

## Roadmap

- **Phase 2 — living benchmark:** GitHub Actions re-runs on each PHP/Octane/server release
  and auto-publishes to `gh-pages`. (Caveat: CI runners are noisy; needs a self-hosted
  runner or a loud relative-only disclaimer.)
- **Phase 3 — decision engine:** "tell me my app's shape → which server + worker count."

## Layout

```
routes/web.php              # /bench/{hello,hash,mandelbrot,json,db} workloads
compose.yml                 # 5 servers + mysql + pinned wrk (caps & cpuset here)
docker/wrk/                 # wrk image + Lua JSON reporter
docker/fpm/ , docker/nginx/ # FPM pool + opcache parity, nginx FastCGI front
benchmark.sh               # the matrix harness
bench/aggregate.py         # results → RESULTS.md + docs/ charts
database/migrations/*bench_items*  # seeds the /bench/db table
```
