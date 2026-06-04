# Laravel Octane Benchmark

**English** · [繁體中文](readmes/README.zh-Hant.md) · [简体中文](readmes/README.zh-Hans.md) · [日本語](readmes/README.ja.md) · [한국어](readmes/README.ko.md) · [Español](readmes/README.es.md) · [Deutsch](readmes/README.de.md) · [Русский](readmes/README.ru.md) · [Italiano](readmes/README.it.md) · [Français](readmes/README.fr.md) · [Português](readmes/README.pt.md)

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
is deployed to GitHub Pages (Settings → Pages → Source: GitHub Actions).

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
| Workers | **8** everywhere (FPM `pm=static, max_children=8`) | same budget; Octane's ~2 workers/CPU × 4 cores |
| CPU | **`cpus=4`, `cpuset=0-3`** per app container | each server gets the same 4 physical cores |
| Load generator | **`wrk` pinned via `${WRK_CPUSET}`** — `4-7` on an 8-core+ host (isolated), `0-3` on the 4-core default runner (co-resident) | isolates the generator when cores exist for it; disclosed per-cell as `generator_isolated` |
| Memory | `mem_limit=8g` (env `MEM_LIMIT`) | generous **equal** ceiling — never binds on the 16 GB runner, so no server is OOM-penalized and peak RSS reads the true high-water mark (not clamped). Set `MEM_LIMIT=512m` for a small-VPS scenario |
| OPcache | enabled, `validate_timestamps=0` | code compiled once, like Octane keeps it |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | production code paths |
| Sessions | `SESSION_DRIVER=array` | stateless endpoints — nothing serializes on a write lock |
| Versions | pinned: PHP 8.4, Laravel 13, Octane 2.17 (see manifest) | no moving parts |

The harness runs **one app server at a time** (all others stopped) so its CPU/RAM are
measured in isolation, not under contention from idle siblings.

**Default environment: a GitHub Actions `ubuntu-24.04` runner (4 vCPU / 16 GB RAM).**
`benchmark.sh` adapts to the core count: the SUT always gets `cpuset 0-3`, and the `wrk`
generator is isolated on cores `4-7` **only when the host has ≥ 8 cores**. On the 4-core
runner there are no cores `4-7`, so the generator shares `0-3` with the SUT — each cell
records `generator_isolated: false`. Because CI runners are also noisy neighbors, read
those runs as **relative-only**. For generator-isolated numbers, run on an 8-core+ box
(the harness picks `WRK_CPUSET=4-7` automatically, or set it yourself).

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

**In CI (the default):** trigger the **Benchmark** workflow
(`.github/workflows/benchmark.yml`) via *Actions → Run workflow*. It runs on
`ubuntu-24.04`, builds the report, and uploads `results/` + `docs/` as an artifact
(set the `publish` input to deploy `docs/` to GitHub Pages). Inputs let you scale the matrix.

**Locally** — **Prerequisite:** Docker (Compose v2).

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
- **Generator co-residence on 4 cores.** On the default `ubuntu-24.04` runner the load
  generator shares the SUT's cores (`generator_isolated: false`). The comparison stays
  fair — every server is measured under the *same* co-resident generator — but absolute
  latency is inflated versus an 8-core isolated run. It's a relative measurement either way.
- **`cpu`-group calibration.** `BENCH_HASH_ITERATIONS` (default 2000),
  `BENCH_MANDELBROT_REPEAT` (1), and `BENCH_JSON_ITERATIONS` (1000) should be tuned on
  your box so each `cpu`-group route's latency clearly dominates `/bench/hello`.

## Roadmap

- **Phase 2 — living benchmark:** the GitHub Actions workflow already runs the matrix on
  `ubuntu-24.04` and can deploy to GitHub Pages. Next: a `schedule:` trigger to auto-re-run
  on each PHP/Octane/server release. (Caveat: hosted runners are noisy; for isolated
  absolute numbers use a self-hosted 8-core+ runner — the harness will then pin `wrk` to
  `4-7` automatically.)
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
.github/workflows/benchmark.yml    # CI: run the matrix on ubuntu-24.04 (4 vCPU)
```
