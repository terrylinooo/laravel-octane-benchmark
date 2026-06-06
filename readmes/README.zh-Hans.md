[English](../README.md) · [繁體中文](README.zh-Hant.md) · **简体中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

一套可复现的测试框架，将 Laravel Octane 应用服务器（**Swoole**、**OpenSwoole**、**RoadRunner**、**FrankenPHP**）与传统的**PHP-FPM + nginx** 对照组进行基准测试——并展示*每一个究竟在哪里胜出*。

大多数 Octane 基准测试只发布一个"最快"的数字，而且彼此互相矛盾，因为它们在工作负载、worker 数量、压测工具、热态与冷态上悄悄各不相同，却几乎从不披露这些差异。本项目锁定了每一个干扰变量，全部公开披露，并发布**按工作负载划分的延迟交叉曲线**。结论明确就是"视情况而定——而这里恰恰说清了取决于什么。去亲自跑一遍吧。"

最快也不等于最好。Swoole/OpenSwoole、RoadRunner、FrankenPHP 各有各的取舍，也适合不同的应用场景。真正选型时还会牵涉到运维模式、生态支持、部署方式、extension 兼容性，以及团队熟悉度。这些不在本项目的讨论范围内；本项目只负责在公平、可复现的环境下把数据跑出来。

## Results

跑一遍，然后打开 `docs/index.html`（图表）/ `RESULTS.md`（表格）。已发布的运行结果会部署到 GitHub Pages（Settings → Pages → Source: GitHub Actions）。该站点是一个小型多页仪表盘：一个 **Compare** 页面（胜者热力图、按工作负载划分的 p99 + 吞吐量曲线及数据表、峰值 RSS），外加为每个 Octane 服务器（Swoole / OpenSwoole / RoadRunner / FrankenPHP）提供的**逐服务器深度报告**页面，并带有一个**worker 数量切换开关**，可在所扫描的各个 worker 数量之间切换整个视图。

这些是**单机**结果。请把它们当作**相对**值来解读（哪个服务器胜出，以及在什么并发量下胜者发生反转），而不是针对你硬件的绝对数字。

## What's measured

**头条指标：跨并发扫描的 p99 / p50 延迟。** 尾延迟才是这些服务器真正分道扬镳的地方；平均吞吐量往往都在噪声范围内。吞吐量（req/s）会一并报告。**Peak RSS**（内存峰值水位）是次要的"VPS 选型"指标。CPU% 被刻意*排除*在头条指标之外——cgroup CPU 采样噪声太大，不足以作为引用依据。

每个单元格 = `{server, workload, workers, concurrency, run}`，以一个 JSON 文件存储在 `results/` 中，内嵌一份清单（固定版本、上限值、commit SHA、主机、wrk 标志），因此任何一个数据点都可复现。记录到 wrk 错误（非 2xx / 超时）的单元格会被标记出来，绝不会被悄悄地平均进去。

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| Workers | **扫描**（`WORKER_COUNTS`，默认约 2/cpu 及其 ×2 → 在 2-cpu runner 上为 `4 8`）；FPM `max_children` 与之匹配 | 这是矩阵的一个维度——看每个服务器如何随 worker 数扩展。每一遍中，每个服务器（含 FPM 对照组）都用相同的数量；CPU 已经 oversubscribe 后，更多 workers 反而可能更慢 |
| CPU | SUT 使用扣除两个保留核心后的所有主机核心（4 核 runner 上为 `cpuset 2-3`） | 每个服务器都获得相同的 CPU 预算 |
| 压测工具 + DB | `wrk` 和 `mysql` 各使用一个独立核心（`0` 和 `1`），与 SUT 分离 | 压测工具和数据库都不会抢占 SUT 的 CPU，`/bench/db` 也不会受到 MySQL CPU 争用影响 |
| Memory | `mem_limit=4g`（环境变量 `MEM_LIMIT`） | 慷慨的**相等**上限——在 16 GB runner 上从不触顶，所以没有服务器会因 OOM 受罚，峰值 RSS 读到的是真实的峰值水位（未被钳制）。设置 `MEM_LIMIT=512m` 可模拟小型 VPS 场景 |
| OPcache | 启用，`validate_timestamps=0` | 代码只编译一次，就像 Octane 始终保持的那样 |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | 生产环境代码路径 |
| Sessions | `SESSION_DRIVER=array` | 无状态端点——写锁上不会序列化任何东西 |
| Versions | 固定：PHP 8.4、Laravel 13、Octane 2.17（见清单） | 没有任何会变动的部件 |

该工具**一次只运行一个应用服务器**（其余全部停止），因此它的 CPU/RAM 是在隔离状态下测量的，而不是在空闲同类进程的争用之下。

**默认环境：GitHub Actions `ubuntu-24.04` runner（4 vCPU / 16 GB RAM）。** 脚本将 core `0` 分配给 `wrk`，core `1` 分配给 `mysql`，SUT 使用 `cpuset 2-3`，并设置 `cpus=2`、`mem_limit=4g`。在 8 核主机上，`wrk` 和 `mysql` 仍分别使用 core `0` 和 `1`，SUT 则使用 `cpuset 2-7`。这样压测工具和数据库都与 SUT 隔离。共享 CI runner 仍可能有噪声，因此应更重视结果曲线，而非精确数字。

## Workloads

工作负载被组织为三个**组（group）**，使图表和表格读起来呈现为"开销 → CPU 花在哪里 → I/O"。`cpu` 组中的三条路由各自施压于一条*不同*的指令路径，所以它们在"哪个服务器胜出"上可能各执一词。

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | 路由 + 响应开销 | 定长响应体 |
| cpu | `/bench/hash` | 整数 / 位运算 | `sha256` 链式计算 ×`BENCH_HASH_ITERATIONS`（标定使其 ≫ hello） |
| cpu | `/bench/mandelbrot` | 浮点 / FPU | 逃逸时间 Mandelbrot，`BENCH_MANDELBROT_DIM`²×4 网格，`…_MAX_ITER` 上限，×`…_REPEAT`（默认约 30ms） |
| cpu | `/bench/json` | 序列化（编解码器） | 对一个 1000 个整数的数组进行 `json_encode`+`json_decode` 往返 ×`BENCH_JSON_ITERATIONS`（由编解码器主导，而非路由；默认约 20ms） |
| io | `/bench/db` | 一次真实查询 | 索引主键 `SELECT`，对接 **MySQL 8** |

**`/bench/db` 注意事项：** 各服务器在连接处理上各不相同（Swoole 协程池 vs RoadRunner vs FrankenPHP）。该工作负载的范畴被界定为**"每个服务器默认的 Octane DB 行为"**，而非一次隔离的原始查询测量。图表上也是如此标注的。

## Run it

本项目默认会使用 GitHub Actions runner 跑 benchmark 并生成报表。你可以直接使用本 repo 的 workflow，也可以 fork 到自己的 repo 中运行，或者在你自己控制的本机、远程机器上执行同一套 harness。

**在 CI 中（默认方式）：** 通过 *Actions → Run workflow* 触发 **Benchmark** 工作流（`.github/workflows/benchmark.yml`）。它在 `ubuntu-24.04` 上运行，构建报告，并将 `results/` + `docs/` 作为 artifact 上传（把 `publish` 输入设为部署，即可将 `docs/` 部署到 GitHub Pages）。输入参数让你能够调整矩阵规模。

**在本地** — **前置条件：** Docker（Compose v2），以及主机上的 PHP 8.4 + Composer 用于 `make deps`（只有 `composer install` 在主机上运行；其余一切都在 Docker 中）。一个 `Makefile` 封装了整个流程——`make help` 列出每个 target。

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

可通过环境变量调节：`SERVERS`、`WORKLOADS`、`CONCURRENCIES`、`WORKER_COUNTS`、`RUNS`、`DURATION`、`WARMUP`、`TIMEOUT`、`BENCH_HASH_ITERATIONS`、`BENCH_MANDELBROT_DIM`、`BENCH_MANDELBROT_MAX_ITER`、`BENCH_MANDELBROT_REPEAT`、`BENCH_JSON_ITERATIONS`。每个 (server, workload) 在其运行之前都会**在每个并发量上**预热，而 `wrk --timeout`（默认 15s）让一个缓慢、饱和的单元格得以被测量，而不是作为错误被剔除。

`benchmark.sh` 默认会测试大约 `2 * SUT_CPUS` 的 worker 数，然后再测试它的两倍。默认 4-vCPU runner 会让被测 server 拿 2 CPUs，所以默认 worker sweep 是 `4 8`。如果 8 workers 的吞吐量低于 4，或 p99 更差，这是有效结果：通常代表额外 PHP workers 带来 scheduler contention、cache pressure，或 DB/socket contention，但没有增加真正可用的 CPU 容量。

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

`wrk` 容器运行一个小型 Lua 报告器（`docker/wrk/report.lua`），输出一行 JSON，包含完整的延迟百分位数和按类别统计的错误计数。

## Idle memory profiler

一个独立工具测量 **Octane 每个 worker 常驻占用多少 RAM**——即让框架保持热态的内存成本——在没有负载的情况下：

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

该拟合将**固定的**框架/master/OPcache 开销与多一个 worker 的**边际**成本区分开来。朴素的 `RSS / N` 平均值具有误导性——它随 N 增大而下降，只是因为固定成本被摊薄了，而不是因为某个 worker 变便宜了。

## Caveats

- **单机，相对而非绝对。** 你的数字会有所不同；那个*形态*（谁在哪里胜出）才是可移植的发现。
- **绑核自检。** 如果主机不遵从 `--cpuset-cpus`，每个单元格都会被标记为 `pinning=unverified`，其结果也不会作为"压测工具已隔离"来呈现。
- **4 核 runner 上的 2-cpu / 4 GB SUT。** 另外两个核心分别保留给 `wrk` 和 `mysql`，避免它们与 SUT 争用 CPU。
- **更多 workers 不一定更快。** 4 workers 到 8 workers 反而下降时，应解读成 benchmark 找到 这台机器上的局部饱和点，尤其是在 CPU-bound workload 或默认 2-CPU SUT 切分下。
- **`cpu` 组标定。** 默认值瞄准**每个请求约 20-30ms**：足够重以主导 `/bench/hello`，又足够轻以使扫描到并发 128 时不会在 4 核机器上饱和成 `wrk` 超时。在你的机器上通过 `BENCH_HASH_ITERATIONS`（2000）、`BENCH_MANDELBROT_DIM`（32）/ `BENCH_MANDELBROT_MAX_ITER`（256）以及 `BENCH_JSON_ITERATIONS`（150）来调校；`…_REPEAT` 把 mandelbrot 加重以适配更强的主机。

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

## 压测总结

公开报告：[Dashboard UI](https://terrylinooo.github.io/laravel-octane-benchmark) · [结果数据](https://terrylinooo.github.io/laravel-octane-benchmark/summary.json)

本次测试在受控的单机环境中进行。SUT Docker 容器限制为 `2 CPU / 4 GB RAM`，`wrk` 和 `mysql` 使用独立 CPU 核心。因此这些数据应作为相同资源限制下的相对比较，而不是所有生产环境的通用排名。

- 最稳定的 p99 延迟：FrankenPHP
- 部分 workload 的最高峰值吞吐量：Swoole / OpenSwoole
- 最低内存占用：PHP-FPM + nginx
- 本次配置下效率最弱：RoadRunner
- `2 CPU` 限制下通常 4 workers 优于 8 workers

FrankenPHP 在延迟稳定性、有竞争力的吞吐量和适中的内存占用之间取得了最佳整体平衡。核心结论是：选择 Octane server 时不能只看峰值 requests per second。

## License

这份 Laravel Octane benchmark 以 MIT License 发布，由 [Terry L.](https://terryl.in) 维护。Terry L. 同时也是 Airygen 的开发者，它是一套免费且强大的 [WordPress SEO Plugin](https://www.airygen.com/en)，适合需要结构化内容流程与搜索导向发布工具的团队。

## 待讨论

Serverless container 服务，例如 Google Cloud Run，和本 benchmark 使用的固定 2-CPU container 不一定是同一种行为。这类服务通常按配置算力计费，而且底层 host 可能有很多 CPU cores；worker 数量较多时，理论上可以持续消费可用算力，直到撞到服务设置的算力上限。在这种环境下，`workers = CPU x 2` 这个经验公式不一定适合作为默认值；worker count 应该根据平台实际 CPU 配置、concurrency model、计费方式与 latency target 重新调整。
