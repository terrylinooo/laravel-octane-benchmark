[English](../README.md) · [繁體中文](README.zh-Hant.md) · **简体中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

一套可复现的测试框架，针对各 Laravel Octane 应用服务器
（**Swoole**、**OpenSwoole**、**RoadRunner**、**FrankenPHP**）与传统的
**PHP-FPM + nginx** 对照组进行基准测试——并展示*每一个究竟在哪里胜出*。

大多数 Octane 基准测试只发布一个孤零零的"最快"数字，而且彼此互相矛盾，
因为它们在工作负载、worker 数量、压测工具、热态与冷态上悄悄各不相同，
却几乎从不披露这些差异。本项目锁定了每一个干扰变量，全部公开披露，
并发布**按工作负载划分的延迟交叉曲线**。结论明确就是"视情况而定——
而这里恰恰说清了取决于什么。去亲自跑一遍吧。"

> 方法论本身就是产品。如果你无法根据某个数字的清单（manifest）复现它，
> 那就是一个 bug。

## Results

跑一遍，然后打开 `docs/index.html`（图表）/ `RESULTS.md`（表格）。已发布的运行结果
存放在 `gh-pages` 分支上。

这些是**单机**结果。请把它们当作**相对**值来解读（哪个服务器胜出，以及在什么并发量下
胜者发生反转），而不是针对你硬件的绝对数字。

## What's measured

**头条指标：跨并发扫描的 p99 / p50 延迟。** 尾延迟才是这些服务器真正分道扬镳的地方；
平均吞吐量往往都在噪声范围内。吞吐量（req/s）会一并报告。**Peak RSS**（内存峰值水位）
是次要的"VPS 选型"指标。CPU% 被刻意*排除*在头条指标之外——cgroup CPU 采样噪声太大，
不足以作为引用依据。

每个单元格 = `{server, workload, concurrency, run}`，以一个 JSON 文件存储在
`results/` 中，内嵌一份清单（固定版本、上限值、commit SHA、主机、wrk 标志），
因此任何一个数据点都可复现。记录到 wrk 错误（非 2xx / 超时）的单元格会被标记出来，
绝不会被悄悄地平均进去。

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| Workers | 各处均为 **8**（FPM `pm=static, max_children=8`） | 相同预算；Octane 的约 2 个 worker/CPU × 4 核 |
| CPU | 每个应用容器 **`cpus=4`, `cpuset=0-3`** | 每个服务器都拿到相同的 4 个物理核心 |
| Load generator | **`wrk` 通过 `${WRK_CPUSET}` 固定绑核**——在 8 核以上的主机上绑到 `4-7`（隔离），在 4 核的默认 runner 上绑到 `0-3`（共驻） | 当有多余核心可用时隔离压测工具；按单元格披露为 `generator_isolated` |
| Memory | `mem_limit=512m` | 相同的上限 |
| OPcache | 启用，`validate_timestamps=0` | 代码只编译一次，就像 Octane 始终保持的那样 |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | 生产环境代码路径 |
| Sessions | `SESSION_DRIVER=array` | 无状态端点——写锁上不会序列化任何东西 |
| Versions | 固定：PHP 8.4、Laravel 13、Octane 2.17（见清单） | 没有任何会变动的部件 |

该工具**一次只运行一个应用服务器**（其余全部停止），因此它的 CPU/RAM 是在隔离状态下
测量的，而不是在空闲同类进程的争用之下。

**默认环境：一个 GitHub Actions `ubuntu-24.04` runner（4 vCPU / 16 GB RAM）。**
`benchmark.sh` 会根据核心数自适应：被测系统（SUT）始终拿到 `cpuset 0-3`，而 `wrk`
压测工具**仅当主机拥有 ≥ 8 个核心时**才会隔离到核心 `4-7` 上。在 4 核 runner 上不存在核心 `4-7`，
所以压测工具会与 SUT 共用 `0-3`——每个单元格都会记录 `generator_isolated: false`。由于 CI
runner 同样是嘈杂的邻居，请把那些运行结果**仅当作相对值**来解读。要获得压测工具已隔离的数字，
请在 8 核以上的机器上运行（测试框架会自动选用 `WRK_CPUSET=4-7`，你也可以自行设置）。

## Workloads

工作负载被组织为三个**组（group）**，使图表和表格读起来呈现为
"开销 → CPU 花在哪里 → I/O"。`cpu` 组中的三条路由各自施压于一条*不同*的指令路径，
所以它们在"哪个服务器胜出"上可能各执一词。

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | 路由 + 响应开销 | 定长响应体 |
| cpu | `/bench/hash` | 整数 / 位运算 | `sha256` 链式计算 ×`BENCH_HASH_ITERATIONS`（标定使其 ≫ hello） |
| cpu | `/bench/mandelbrot` | 浮点 / FPU | 逃逸时间 Mandelbrot，78×78 网格 ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | 序列化（编解码器） | 对一个 1000 个整数的数组进行 `json_encode`+`json_decode` 往返 ×`BENCH_JSON_ITERATIONS`（由编解码器主导，而非路由） |
| io | `/bench/db` | 一次真实查询 | 索引主键 `SELECT`，对接 **MySQL 8** |

**`/bench/db` 注意事项：** 各服务器在连接处理上各不相同（Swoole 协程池 vs
RoadRunner vs FrankenPHP）。该工作负载的范畴被界定为**"每个服务器默认的 Octane DB
行为"**，而非一次隔离的原始查询测量。图表上也是如此标注的。

## Run it

**在 CI 中（默认方式）：** 通过 *Actions → Run workflow* 触发 **Benchmark** 工作流
（`.github/workflows/benchmark.yml`）。它在 `ubuntu-24.04` 上运行，构建报告，
并将 `results/` + `docs/` 作为 artifact 上传（可选地把 `docs/` 发布到 `gh-pages`）。
输入参数让你能够调整矩阵规模。

**在本地** — **前置条件：** Docker（Compose v2）。

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

可通过环境变量调节：`SERVERS`、`WORKLOADS`、`CONCURRENCIES`、`RUNS`、`DURATION`、`WARMUP`、
`BENCH_HASH_ITERATIONS`、`BENCH_MANDELBROT_REPEAT`、`BENCH_JSON_ITERATIONS`。

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

`wrk` 容器运行一个小型 Lua 报告器（`docker/wrk/report.lua`），输出一行
JSON，包含完整的延迟百分位数和按类别统计的错误计数。

## Caveats

- **单机，相对而非绝对。** 你的数字会有所不同；那个*形态*（谁在哪里胜出）才是可移植的发现。
- **绑核自检。** 如果主机不遵从 `--cpuset-cpus`，每个单元格都会被标记为
  `pinning=unverified`，其结果也不会作为"压测工具已隔离"来呈现。
- **4 核上的压测工具共驻。** 在默认的 `ubuntu-24.04` runner 上，压测工具会与 SUT 共用核心
  （`generator_isolated: false`）。比较依然公平——每个服务器都在*相同*的共驻压测工具下测量——
  但相对于 8 核隔离运行，绝对延迟会被抬高。无论哪种方式，它都是一次相对测量。
- **`cpu` 组标定。** `BENCH_HASH_ITERATIONS`（默认 2000）、
  `BENCH_MANDELBROT_REPEAT`（1）和 `BENCH_JSON_ITERATIONS`（1000）应在
  你的机器上调校，使每条 `cpu` 组路由的延迟都明显主导 `/bench/hello`。

## Roadmap

- **Phase 2 — 活的基准测试：** GitHub Actions 工作流已经在 `ubuntu-24.04` 上运行该矩阵，
  并能发布到 `gh-pages`。接下来：一个 `schedule:` 触发器，在每次 PHP/Octane/服务器发布时
  自动重新运行。（注意事项：托管 runner 噪声很大；要获得隔离的绝对数字，请使用自托管的
  8 核以上 runner——届时测试框架会自动把 `wrk` 绑核到 `4-7`。）
- **Phase 3 — 决策引擎：** "告诉我我的应用的形态 → 该用哪个服务器 + 多少个 worker。"

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
