# Laravel Octane Benchmark

**English** · [繁體中文](readmes/README.zh-Hant.md) · [简体中文](readmes/README.zh-Hans.md) · [日本語](readmes/README.ja.md) · [한국어](readmes/README.ko.md) · [Español](readmes/README.es.md) · [Deutsch](readmes/README.de.md) · [Русский](readmes/README.ru.md) · [Italiano](readmes/README.it.md) · [Français](readmes/README.fr.md) · [Português](readmes/README.pt.md)

This project benchmarks Laravel Octane servers under the same conditions:

- Swoole
- OpenSwoole
- RoadRunner
- FrankenPHP
- PHP-FPM + nginx as the traditional control group

The goal is not to crown one server as "the fastest". Most Octane benchmarks end up arguing with each other because they use different workloads, worker counts, warm-up rules, and load generators. This repo tries to make those choices visible and repeatable, then shows where each server wins and where the result flips.

In short: run the matrix, open the report, and compare the curves instead of trusting one headline number.

Fastest also does not automatically mean best. Swoole/OpenSwoole, RoadRunner, and FrankenPHP each have their own trade-offs and fit different application shapes. Choosing between them involves operational model, ecosystem support, deployment style, extension compatibility, and team familiarity. This project does not try to settle that decision; it only runs the servers in a fair, repeatable environment and publishes the data.

## Results

After a run, open:

- `docs/index.html` for the dashboard
- `RESULTS.md` for the tables
- `results/*.json` for the raw per-cell data

The dashboard has a Compare page with winner heatmaps, p99 and throughput curves, data tables, and peak RSS. It also creates one deep-dive page per Octane server, with a worker count toggle so you can compare the same workload across different worker settings.

These are single-machine results. Treat them as relative results: which server wins for a given workload and when the winner changes. Do not treat the raw numbers as something your own hardware will exactly match.

## What Gets Measured

The main metric is latency across a concurrency sweep, especially p99. Tail latency is usually where these servers start to separate. p50 and throughput are reported too, but throughput alone often hides the interesting part.

Peak RSS is included as a practical memory signal for VPS sizing. CPU percentage is not a headline metric because cgroup CPU sampling is noisy enough to be misleading in this setup.

Every result cell is one JSON file:

```text
results/{server}_{workload}_w{workers}_c{concurrency}_r{run}.json
```

Each file includes the workload, server, worker count, concurrency, run number, wrk output, and a manifest with pinned versions, resource caps, commit SHA, host data, and wrk flags. If wrk reports timeouts or non-2xx responses, the cell is flagged instead of silently mixed into clean results.

## Fairness Rules

The benchmark runs one app server at a time. Idle sibling containers are stopped, so the server under test is not competing with the others for CPU or memory.

| Control | Value | Why it matters |
|---|---|---|
| Workers | Swept through `WORKER_COUNTS`; FPM `max_children` is matched | Worker count is part of the matrix, not a hidden constant; more workers can be slower once CPU is oversubscribed. |
| CPU | The server under test gets every host core above the two reserved ones (`cpuset 2-3` on the 4-core runner) | Every server gets the same CPU budget. |
| Load generator + DB | `wrk` and `mysql` each get a dedicated core (`0` and `1`), off the server's cores | The load generator and the database never steal CPU from the server being measured, and `/bench/db` has no MySQL contention. |
| Memory | `MEM_LIMIT=4g` by default | The limit is equal and generous on the default runner, so memory pressure does not decide the winner. |
| OPcache | Enabled with `validate_timestamps=0` | Code is compiled once, closer to a warm production setup. |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | Benchmarks production code paths. |
| Sessions | `SESSION_DRIVER=array` | Stateless routes avoid session write locks. |
| Versions | PHP 8.4, Laravel 13, Octane 2.17 | Versions are pinned and recorded in each manifest. |

On the default GitHub Actions runner (`ubuntu-24.04`, 4 vCPU, 16 GB RAM), the script reserves one core for the load generator and one for the database, then gives the rest to the server under test:

- `wrk`: `cpuset 0`
- `mysql`: `cpuset 1`
- server under test: `cpuset 2-3`, with `cpus=2` and `mem_limit=4g`, so it behaves like a Docker-contained 2-cpu / 4 GB server

On an 8-core host, the same rule keeps `wrk` on core `0` and `mysql` on core `1`, and gives the server `cpuset 2-7`. This keeps the generator and the database isolated from the server. Shared CI runners can still be noisy, so read the shape of the results more seriously than the exact numbers.

## Workloads

The workloads are grouped so the charts move from framework overhead, to CPU-heavy routes, to I/O. The CPU routes intentionally stress different paths, so they may disagree on which server wins.

| Group | Route | Focus | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | routing and response overhead | Fixed-size response body. |
| cpu | `/bench/hash` | integer and bitwise work | Repeated SHA-256 chaining via `BENCH_HASH_ITERATIONS`. |
| cpu | `/bench/mandelbrot` | floating-point work | Mandelbrot escape-time calculation with tunable size, max iterations, and repeat count. |
| cpu | `/bench/json` | JSON codec work | `json_encode` and `json_decode` round trips over a 1000-int array. |
| io | `/bench/db` | real database query | Indexed primary-key `SELECT` against MySQL 8. |

The `/bench/db` route measures each server's default Octane database behavior. It is not a raw query micro-benchmark. That distinction matters because Swoole, RoadRunner, and FrankenPHP handle connections differently.

## Run It

This repo is set up to generate benchmark reports on a GitHub Actions runner by default. You can run it as-is from this repository, fork it and run the workflow in your own repo, or run the same harness on a local or remote machine when you want hardware you control.

### GitHub Actions

Use the **Benchmark** workflow in `.github/workflows/benchmark.yml`:

1. Open the Actions tab.
2. Choose **Benchmark**.
3. Click **Run workflow**.

The workflow runs on `ubuntu-24.04`, builds `RESULTS.md` and `docs/`, then uploads `results/` and `docs/` as artifacts. Set the `publish` input if you want the generated dashboard deployed to GitHub Pages.

### Local Machine

Prerequisites:

- Docker with Compose v2
- PHP 8.4 and Composer on the host

Only `composer install` runs on the host. The app servers, MySQL, and wrk run in Docker.

```bash
make setup   # one-time setup: .env, APP_KEY, and vendor/
make bench   # full benchmark matrix; resumable because existing result cells are skipped
make report  # rebuild RESULTS.md and docs/ from results/
```

For a quick end-to-end check:

```bash
make smoke
```

Useful environment variables:

```text
SERVERS
WORKLOADS
CONCURRENCIES
WORKER_COUNTS
RUNS
DURATION
WARMUP
TIMEOUT
MEM_LIMIT
BENCH_HASH_ITERATIONS
BENCH_MANDELBROT_DIM
BENCH_MANDELBROT_MAX_ITER
BENCH_MANDELBROT_REPEAT
BENCH_JSON_ITERATIONS
```

By default, `benchmark.sh` tests roughly `2 * SUT_CPUS` workers and then double that count. On the default 4-vCPU runner the server under test gets 2 CPUs, so the default worker sweep is `4 8`. If 8 workers shows lower throughput or worse p99 than 4, that is a valid result: it usually means the extra PHP workers are adding scheduler contention, cache pressure, or DB/socket contention without adding useful CPU capacity.

Each server/workload pair is warmed at every concurrency before the measured runs. The default wrk timeout is 15 seconds, which lets slow saturated cells be recorded instead of disappearing as censored failures.

## How The Harness Works

```text
benchmark.sh
  for each worker count:
    set Octane workers and match the FPM pool
    for each server/workload:
      stop the other app servers
      start the selected server, plus MySQL for /bench/db
      wait until the server is healthy
      verify cpuset pinning when the host supports it
      for each concurrency:
        warm up
        run wrk through the pinned wrk container
        write one JSON result cell
      capture peak RSS
      stop the server and let the host settle

bench/aggregate.py
  read results/*.json
  calculate medians and ranges
  build RESULTS.md and docs/
```

The wrk container uses `docker/wrk/report.lua` to emit one JSON line with latency percentiles, request counts, throughput, and error classes.

## Idle Memory Profile

The benchmark also includes a separate memory profiler for the cost of keeping Octane workers warm with no active load.

```bash
./bench/mem-profile.sh
python3 bench/mem_profile.py
```

The profiler boots each server with several worker counts, warms every worker, reads the container working set, then fits:

```text
working_set(N) = fixed + marginal * N
```

That split is more useful than `RSS / workers`, because average RSS per worker falls as the fixed framework and OPcache cost gets amortized.

## Caveats

- Single-machine benchmark: use the relative shape, not the exact numbers.
- Hosted runners are noisy, even with CPU pinning.
- On the default 4-core runner, the server under test gets 2 CPUs because the other 2 are reserved one for `wrk` and one for `mysql`. The tested Docker app container is also capped at 4 GB RAM.
- Higher worker counts are not automatically better. Treat a drop from 4 to 8 workers as the benchmark finding the local saturation point, especially on CPU-bound workloads or the default 2-CPU SUT split.
- If the host does not honor `--cpuset-cpus`, affected cells are tagged `pinning=unverified`.
- CPU workloads are calibrated to land around 20-30 ms per request by default. Tune the `BENCH_*` variables if your machine is much faster or slower.
- `/bench/db` compares default Octane database behavior per server, not isolated database driver performance.

## Project Layout

```text
routes/web.php              # /bench/{hello,hash,mandelbrot,json,db}
compose.yml                 # app servers, MySQL, wrk, CPU caps, cpusets
docker/wrk/                 # wrk image and Lua JSON reporter
docker/fpm/                 # FPM pool and OPcache parity config
docker/nginx/               # nginx FastCGI front for the FPM control
Makefile                    # local workflow helpers
benchmark.sh                # benchmark matrix runner
bench/aggregate.py          # results -> RESULTS.md and docs/
bench/mem-profile.sh        # idle memory profiler runner
bench/mem_profile.py        # memory profile fitting/report script
database/migrations/        # bench table migration and seed data
.github/workflows/          # CI benchmark workflow
readmes/                    # translated README files
```

## Benchmark Summary

Published report:

- Dashboard UI: <https://terrylinooo.github.io/laravel-octane-benchmark>
- Result data: <https://terrylinooo.github.io/laravel-octane-benchmark/summary.json>

This benchmark was run in a controlled single-machine environment. The tested app Docker container was capped at `2 CPU / 4 GB RAM`, while `wrk` ran on separate CPU cores. The results should therefore be read as a relative comparison under the same resource limits, not as a universal ranking for every production machine.

FrankenPHP has the strongest overall latency profile in this dataset. Across nearly all workloads, concurrency levels, and both 4-worker and 8-worker settings, it delivers the lowest or near-lowest p99 latency. It is not always the absolute throughput winner, but its tail-latency curve is the most stable.

Swoole and OpenSwoole reach the highest peak throughput in several workloads, especially `hello`, `hash`, `json`, and `db`. However, their p99 latency is often much worse at higher concurrency. In this run, they are better described as throughput-oriented results rather than the most latency-stable results.

RoadRunner is the weakest Octane result in this configuration. It does not show a clear throughput or p99 advantage, and it uses the most memory among the Octane servers, especially with 8 workers.

PHP-FPM + nginx remains the lightest in memory usage by a wide margin, but it trails the Octane servers in throughput and latency. This is the expected tradeoff: lower resident memory, but higher per-request framework overhead.

The worker-count sweep is also important. Under the `2 CPU` app limit, increasing from 4 workers to 8 workers usually does not improve performance. In many cases it lowers throughput or worsens p99 latency, which indicates that 4 workers is already close to the useful saturation point for this environment. The extra workers mainly add scheduler contention, cache pressure, and DB/socket contention without adding CPU capacity.

In practical terms:

- Best p99 latency stability: FrankenPHP
- Highest peak throughput in some workloads: Swoole / OpenSwoole
- Lowest memory usage: PHP-FPM + nginx
- Weakest efficiency profile in this run: RoadRunner
- Better worker count under the 2-CPU limit: usually 4 workers, not 8 workers

The main engineering conclusion is that Octane server choice should not be based on peak requests per second alone. For this dataset, FrankenPHP provides the best overall balance between latency stability, competitive throughput, and moderate memory usage.

## License

This Laravel Octane benchmark is released under the MIT License and maintained by [Terry L.](https://terryl.in). Terry L. is also the developer of Airygen, a free and powerful [WordPress SEO Plugin](https://www.airygen.com/en) for teams that need structured content workflows and search-focused publishing tools.

## Open Discussion

Serverless container platforms such as Google Cloud Run can behave differently from the fixed 2-CPU container used in this benchmark. Because those services are billed by allocated compute and may run on hosts with many underlying CPU cores, a larger worker count may be able to consume available compute until it reaches the configured service limit. In that environment, the usual `workers = CPU x 2` rule of thumb may not be the right default; worker counts should be tuned against the platform's actual CPU allocation, concurrency model, billing behavior, and latency target.
