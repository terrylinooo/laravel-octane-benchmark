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
is deployed to GitHub Pages (Settings → Pages → Source: GitHub Actions). The site is a
small multi-page dashboard: a **Compare** page (winner heatmap, per-workload p99 +
throughput curves with data tables, peak RSS) plus a **per-server deep-report** page for
each Octane server (Swoole / OpenSwoole / RoadRunner / FrankenPHP), with a **worker-count
toggle** to switch the whole view between the swept worker counts.

These are **single-machine** results. Read them as **relative** (which server wins, and
at what concurrency the winner flips), not as absolute numbers for your hardware.

## What's measured

**Headline: p99 / p50 latency across a concurrency sweep.** Tail latency is where these
servers actually diverge; mean throughput is often within noise. Throughput (req/s) is
reported alongside. **Peak RSS** (memory high-water mark) is a secondary "VPS sizing"
metric. CPU% is deliberately *not* a headline — cgroup CPU sampling is too noisy to cite.

Each cell = `{server, workload, workers, concurrency, run}` and is stored as one JSON file
in `results/` with an embedded manifest (pinned versions, caps, commit SHA, host, wrk
flags) so any data point is reproducible. Cells that recorded wrk errors (non-2xx /
timeouts) are flagged, never silently averaged in.

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| Workers | **swept** (`WORKER_COUNTS`, default ~2/cpu and its ×2 → `4 8` on the 2-cpu runner); FPM `max_children` matched | a matrix dimension — see how each server scales with workers. Same count for every server (incl. the FPM control) per pass |
| CPU | **the host's lower half** — `cpus=2`, `cpuset=0-1` on the 4-core runner (`cpus=4`, `cpuset=0-3` on an 8-core host) | every server gets the same cores; the SUT cpu count is recorded in the manifest caps |
| Load generator | **`wrk` on the host's upper half** (`cpuset=2-3` on the runner, `4-7` on 8 cores) — disjoint from the SUT | the generator is **always isolated**: it never steals the SUT's CPU. Recorded per-cell as `generator_isolated` |
| Memory | `mem_limit=4g` (env `MEM_LIMIT`) | generous **equal** ceiling — never binds on the 16 GB runner, so no server is OOM-penalized and peak RSS reads the true high-water mark (not clamped). Set `MEM_LIMIT=512m` for a small-VPS scenario |
| OPcache | enabled, `validate_timestamps=0` | code compiled once, like Octane keeps it |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | production code paths |
| Sessions | `SESSION_DRIVER=array` | stateless endpoints — nothing serializes on a write lock |
| Versions | pinned: PHP 8.4, Laravel 13, Octane 2.17 (see manifest) | no moving parts |

The harness runs **one app server at a time** (all others stopped) so its CPU/RAM are
measured in isolation, not under contention from idle siblings.

**Default environment: a GitHub Actions `ubuntu-24.04` runner (4 vCPU / 16 GB RAM).**
`benchmark.sh` **splits the host in half**: the SUT gets the lower cores, the `wrk`
generator the upper cores, so the generator is **always isolated** (it never steals the
SUT's CPU). On the 4-core runner that means the **SUT is 2 cpus** (`cpuset 0-1`) and `wrk`
runs on `2-3`; on an 8-core host the SUT gets 4 cpus (`0-3`) and `wrk` `4-7`. The trade-off
is the SUT only gets **half the box** — so on the default runner reports are for a **2-cpu
server**, recorded in the manifest caps (`cpus=2`). Because shared CI runners are still
noisy neighbors, read the numbers as **relative-only**.

## Workloads

Workloads are organized into three **groups** so the charts and tables read as
"overhead → where the CPU goes → I/O". The three `cpu`-group routes each stress a
*different* instruction path, so they can disagree on which server wins.

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | routing + response overhead | fixed-length body |
| cpu | `/bench/hash` | integer / bitwise | `sha256` chaining ×`BENCH_HASH_ITERATIONS` (calibrate so it ≫ hello) |
| cpu | `/bench/mandelbrot` | float / FPU | escape-time Mandelbrot, `BENCH_MANDELBROT_DIM`²×4 grid, `…_MAX_ITER` cap, ×`…_REPEAT` (~30ms default) |
| cpu | `/bench/json` | serialization (codec) | `json_encode`+`json_decode` round-trip of a 1000-int array ×`BENCH_JSON_ITERATIONS` (codec dominates, not routing; ~20ms default) |
| io | `/bench/db` | a real query | indexed PK `SELECT` vs **MySQL 8** |

**`/bench/db` caveat:** servers differ in connection handling (Swoole coroutine pool vs
RoadRunner vs FrankenPHP). This workload is scoped as **"each server's default Octane DB
behavior,"** not an isolated raw-query measurement. It's labeled as such on the chart.

## Run it

**In CI (the default):** trigger the **Benchmark** workflow
(`.github/workflows/benchmark.yml`) via *Actions → Run workflow*. It runs on
`ubuntu-24.04`, builds the report, and uploads `results/` + `docs/` as an artifact
(set the `publish` input to deploy `docs/` to GitHub Pages). Inputs let you scale the matrix.

**Locally** — **Prerequisites:** Docker (Compose v2), and PHP 8.4 + Composer on the host
for `make deps` (only `composer install` runs on the host; everything else is in Docker).
A `Makefile` wraps the workflow — `make help` lists every target.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

Tunable via env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `WORKER_COUNTS`, `RUNS`, `DURATION`, `WARMUP`,
`TIMEOUT`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_DIM`, `BENCH_MANDELBROT_MAX_ITER`,
`BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`. Each (server, workload) is warmed
**at every concurrency** before its runs, and `wrk --timeout` (default 15s) lets a slow,
saturated cell be measured rather than censored as errors.

## How it works

```
benchmark.sh ── per worker count (split host: SUT = lower cores, wrk = upper cores):
  set OCTANE_WORKERS + match the FPM pool, then per (server, workload):
  stop all app servers → start this one (force-recreate; + mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → per concurrency: warm (discarded) → runs via the pinned wrk container (--timeout)
  → write results/{server}_{workload}_w{workers}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup v2 memory.peak / v1 high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Compare +
  per-server pages, Chart.js, logo embedded)
```

The `wrk` container runs a small Lua reporter (`docker/wrk/report.lua`) that emits one
JSON line with full latency percentiles and per-class error counts.

## Idle memory profiler

A separate tool measures **how much RAM Octane keeps resident per worker** — the memory
cost of keeping the framework warm — with no load:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

The fit separates the **fixed** framework/master/OPcache overhead from the **marginal**
cost of one more worker. The naive `RSS / N` average is misleading — it falls as N grows
only because the fixed cost is amortized, not because a worker got cheaper.

## Caveats

- **Single machine, relative not absolute.** Your numbers will differ; the *shape* (who
  wins where) is the portable finding.
- **Pinning self-check.** If the host doesn't honor `--cpuset-cpus`, every cell is tagged
  `pinning=unverified` and the result is not presented as generator-isolated.
- **2-cpu SUT on the 4-core runner.** To keep the generator isolated, the host is split
  in half — so on the default runner each server is a **2-cpu** server (the other 2 cores
  drive `wrk`). It's labelled in the manifest (`cpus=2`). For a 4-cpu SUT *with* an isolated
  generator you need an 8-core host (the split then gives the SUT 4 cores, `wrk` the other 4).
- **`cpu`-group calibration.** Defaults aim for **~20-30ms per request**: heavy enough to
  dominate `/bench/hello`, light enough that a sweep to concurrency 128 doesn't saturate
  into `wrk` timeouts on a 4-core box. Tune on your box via `BENCH_HASH_ITERATIONS` (2000),
  `BENCH_MANDELBROT_DIM` (32) / `BENCH_MANDELBROT_MAX_ITER` (256), and
  `BENCH_JSON_ITERATIONS` (150); `…_REPEAT` scales mandelbrot up for heavier hosts.

## Roadmap

- **Phase 2 — living benchmark:** the GitHub Actions workflow already runs the matrix on
  `ubuntu-24.04` and can deploy to GitHub Pages. Next: a `schedule:` trigger to auto-re-run
  on each PHP/Octane/server release. (Caveat: hosted runners are noisy; for a **4-cpu**
  SUT with the generator still isolated, use a self-hosted 8-core+ runner — the split then
  gives the SUT `0-3` and `wrk` `4-7` automatically.)
- **Phase 3 — decision engine:** "tell me my app's shape → which server + worker count."

## Layout

```
routes/web.php              # /bench/{hello,hash,mandelbrot,json,db} workloads
compose.yml                 # 5 servers + mysql + pinned wrk (caps & cpuset here)
docker/wrk/                 # wrk image + Lua JSON reporter
docker/fpm/ , docker/nginx/ # FPM pool + opcache parity, nginx FastCGI front
Makefile                    # container-first workflow (make help)
benchmark.sh                # the matrix harness
bench/aggregate.py          # results → RESULTS.md + docs/ (Compare + per-server pages)
bench/dashboard_template.html , bench/server_template.html  # docs/ page templates
bench/mem-profile.sh , bench/mem_profile.py  # idle per-worker memory profiler
database/migrations/*bench_items*  # seeds the /bench/db table
.github/workflows/benchmark.yml    # CI: run the matrix on ubuntu-24.04 (4 vCPU)
readmes/                    # README translations (10 languages)
```
