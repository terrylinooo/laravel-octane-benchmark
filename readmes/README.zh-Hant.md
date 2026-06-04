[English](../README.md) · **繁體中文** · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

這個專案用同一套條件測 Laravel Octane 伺服器：

- Swoole
- OpenSwoole
- RoadRunner
- FrankenPHP
- PHP-FPM + nginx，作為傳統架構的對照組

它不是要硬選出一個「最快」的伺服器。很多 Octane benchmark 會互相打架，通常不是因為
誰對誰錯，而是因為工作負載、worker 數量、暖機方式、壓測工具怎麼跑都不一樣。這個 repo
把這些條件攤開來、固定下來，讓你看到每個伺服器在哪裡贏，以及勝負在什麼情況下會翻轉。

簡單講：跑一次矩陣，打開報告，看曲線，不要只相信單一個最快數字。

最快也不代表最好。Swoole/OpenSwoole、RoadRunner、FrankenPHP 各自有不同取捨，也各自適合
不同的應用情境。真正選型時還會牽涉到維運模式、生態支援、部署方式、extension 相容性，以及
團隊熟悉度。這些不在本專案討論範圍內；本專案只負責在公平、可重現的環境下把數據跑出來。

## 結果

跑完之後可以看：

- `docs/index.html`：互動式報表
- `RESULTS.md`：表格版結果
- `results/*.json`：每個測試 cell 的原始資料

報表裡有 Compare 頁面，包含勝出者熱圖、p99 與吞吐量曲線、資料表和 peak RSS。它也會替
每個 Octane server 產生一頁深入報告，並提供 worker 數量切換，方便用同一個 workload 比較
不同 worker 設定。

這些都是單機結果。請把它當成相對比較：哪個伺服器在某個 workload 下勝出，以及勝負在哪個
並發量附近翻轉。不要把原始數字當成你的硬體一定會跑出來的結果。

## 量測內容

主要指標是並發掃描下的延遲，尤其是 p99。這類伺服器真正拉開差距的地方通常是尾端延遲。
p50 和吞吐量也會一起列出，但只看吞吐量常常會漏掉最有用的訊號。

Peak RSS 會一起記錄，主要是給 VPS 規格評估用。CPU 百分比沒有被當成主要指標，因為這個
設定下的 cgroup CPU 取樣雜訊太高，拿來當結論容易誤導。

每個結果 cell 都是一個 JSON 檔：

```text
results/{server}_{workload}_w{workers}_c{concurrency}_r{run}.json
```

檔案裡會包含 workload、server、worker 數量、並發量、run 編號、wrk 輸出，以及 manifest。
manifest 會記錄釘選版本、資源上限、commit SHA、host 資訊和 wrk 參數。只要 wrk 有回報逾時或
非 2xx 回應，該 cell 就會被標記，不會偷偷混進乾淨結果裡平均。

## 公平性規則

Benchmark 一次只跑一個 app server。其他 server 會先停掉，所以被測的 server 不會和閒置的
同伴搶 CPU 或記憶體。

| 控制項 | 值 | 為什麼重要 |
|---|---|---|
| Workers | 透過 `WORKER_COUNTS` 掃描；FPM `max_children` 會對齊 | worker 數量是矩陣的一部分，不是藏起來的常數。 |
| CPU | 被測 server 使用 host 的下半部核心 | 每個 server 拿到一樣的 CPU 預算。 |
| 壓測工具 | `wrk` 使用 host 的上半部核心 | 壓測工具不會搶走被測 server 的 CPU。 |
| 記憶體 | 預設 `MEM_LIMIT=4g` | 預設 runner 上這個上限夠寬，避免記憶體壓力直接決定勝負。 |
| OPcache | 啟用，`validate_timestamps=0` | 程式碼只編譯一次，比較接近暖機後的正式環境。 |
| App env | `APP_ENV=production`、`APP_DEBUG=false` | 跑正式環境的程式路徑。 |
| Sessions | `SESSION_DRIVER=array` | 路由是無狀態的，避免 session 寫入鎖影響結果。 |
| 版本 | PHP 8.4、Laravel 13、Octane 2.17 | 版本會被釘選，也會記錄在每個 manifest 裡。 |

預設 GitHub Actions runner 是 `ubuntu-24.04`，有 4 vCPU 和 16 GB RAM。腳本會把 host 切成兩半：

- 被測 server：`cpuset 0-1`，也就是一台 2-cpu server
- `wrk`：`cpuset 2-3`

如果在 8-core host 上跑，同一套規則會讓 server 拿 `0-3`，`wrk` 拿 `4-7`。這樣可以隔離壓測工具，
但代價是 server 只拿到半台機器。共享 CI runner 還是會有雜訊，所以結果的形狀比精確數字更值得看。

## Workloads

Workload 分成幾組，讓圖表可以從框架開銷、CPU-heavy 路由一路看到 I/O。幾個 CPU workload
故意壓不同的執行路徑，所以它們對「誰比較快」可能會有不同答案。

| 群組 | 路由 | 重點 | 備註 |
|---|---|---|---|
| overhead | `/bench/hello` | routing 和 response overhead | 固定大小的 response body。 |
| cpu | `/bench/hash` | integer 和 bitwise work | 透過 `BENCH_HASH_ITERATIONS` 重複做 SHA-256 chaining。 |
| cpu | `/bench/mandelbrot` | floating-point work | Mandelbrot escape-time calculation，可調大小、最大迭代次數和 repeat count。 |
| cpu | `/bench/json` | JSON codec work | 對 1000 個整數的陣列做 `json_encode` / `json_decode` round trip。 |
| io | `/bench/db` | 真實資料庫查詢 | 對 MySQL 8 做 indexed primary-key `SELECT`。 |

`/bench/db` 測的是每個 server 在 Octane 預設設定下的資料庫行為，不是純粹的 raw query
micro-benchmark。這點很重要，因為 Swoole、RoadRunner、FrankenPHP 的連線處理方式不一樣。

## 執行方式

這個專案預設會利用 GitHub Actions runner 跑 benchmark 並產生報表。你可以直接用本 repo
的 workflow，也可以 fork 到自己的 repo 裡跑，或是在你自己控制的本機、遠端機器上執行同一套
harness。

### GitHub Actions

使用 `.github/workflows/benchmark.yml` 裡的 **Benchmark** workflow：

1. 打開 Actions tab。
2. 選 **Benchmark**。
3. 點 **Run workflow**。

Workflow 會在 `ubuntu-24.04` 上跑，產生 `RESULTS.md` 和 `docs/`，然後把 `results/` 和 `docs/`
上傳成 artifacts。如果想部署到 GitHub Pages，把 `publish` input 打開即可。

### 本機

需要先有：

- Docker with Compose v2
- host 上的 PHP 8.4 和 Composer

只有 `composer install` 會在 host 上跑。app servers、MySQL 和 wrk 都在 Docker 裡跑。

```bash
make setup   # 第一次設定：.env、APP_KEY、vendor/
make bench   # 跑完整 benchmark matrix；可續跑，因為既有 result cell 會被略過
make report  # 用 results/ 重新產生 RESULTS.md 和 docs/
```

只想快速確認整套流程能跑：

```bash
make smoke
```

常用環境變數：

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

每個 server/workload 組合都會在每個並發量下先暖機，再進入正式測量。預設 wrk timeout 是
15 秒，這樣慢到飽和的 cell 仍然能被記錄，而不是直接被當成看不見的失敗。

## 運作方式

```text
benchmark.sh
  for each worker count:
    設定 Octane workers，並對齊 FPM pool
    for each server/workload:
      停掉其他 app servers
      啟動指定 server；/bench/db 會一起啟動 MySQL
      等到 server healthy
      在 host 支援時確認 cpuset pinning
      for each concurrency:
        暖機
        透過 pinned wrk container 執行壓測
        寫出一個 JSON result cell
      記錄 peak RSS
      停掉 server，讓 host 稍微 settle

bench/aggregate.py
  讀取 results/*.json
  計算 median 和 range
  產生 RESULTS.md 和 docs/
```

wrk container 會使用 `docker/wrk/report.lua` 輸出一行 JSON，裡面包含 latency percentiles、
request counts、throughput 和錯誤分類。

## Idle Memory Profile

專案另外有一個 memory profiler，用來看 Octane workers 在沒有流量時，為了保持暖機狀態會常駐多少
記憶體。

```bash
./bench/mem-profile.sh
python3 bench/mem_profile.py
```

Profiler 會用幾組 worker 數量啟動 server、暖機每個 worker、讀取 container working set，最後 fit：

```text
working_set(N) = fixed + marginal * N
```

這比直接看 `RSS / workers` 有用，因為平均 RSS 會隨 worker 數量增加而下降，通常只是 framework
和 OPcache 的固定成本被攤提掉，不代表每個 worker 真的變便宜。

## 注意事項

- 這是單機 benchmark：看相對形狀，不要執著於精確數字。
- Hosted runner 就算有 CPU pinning，仍然會有雜訊。
- 預設 4-core runner 上，被測 server 只拿 2 CPUs，另外 2 CPUs 保留給 wrk。
- 如果 host 不支援或不遵守 `--cpuset-cpus`，相關 cell 會被標記成 `pinning=unverified`。
- CPU workloads 預設校準在每個 request 約 20-30 ms。機器明顯更快或更慢時，可以調整 `BENCH_*` 變數。
- `/bench/db` 比的是每個 server 的預設 Octane database behavior，不是單獨的 database driver 效能。

## Roadmap

- Phase 2：把 workflow 變成 living benchmark，在 PHP、Octane、server release 時自動重跑。
- Phase 3：加一個小型決策工具，根據 app workload shape 建議 server 和 worker count。

## 專案結構

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
