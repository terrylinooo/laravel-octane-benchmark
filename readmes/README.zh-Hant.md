[English](../README.md) · **繁體中文** · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

一套可重現的測試框架，用來對 Laravel Octane 應用伺服器
（**Swoole**、**OpenSwoole**、**RoadRunner**、**FrankenPHP**）與傳統的
**PHP-FPM + nginx** 對照組進行基準測試——並揭示*每一種究竟在哪裡勝出*。

大多數 Octane 基準測試只發布一個「最快」的數字，而且彼此互相矛盾，
因為它們在工作負載、worker 數量、負載產生器、以及暖機與冷啟動之間悄悄有所差異，
卻幾乎從不公開這些細節。本框架固定了每一個干擾變數、全部公開，
並發布**各工作負載的延遲交叉曲線**。結論很明確：「看情況——而這裡就是它確切取決於什麼。
你自己跑跑看。」

> 方法論本身就是產品。如果你無法從某個數字的 manifest 重現它，
> 那就是一個 bug。

## 結果

跑起來後，打開 `docs/index.html`（圖表）/ `RESULTS.md`（表格）。一份已發布的執行結果
存放在 `gh-pages` 分支上。

這些是**單機**結果。請把它們當作**相對值**（哪個伺服器勝出、以及在哪個並行度下勝負翻轉）來解讀，
而不是你硬體上的絕對數字。

## 量測了什麼

**重點：橫跨並行度掃描的 p99 / p50 延遲。** 尾端延遲才是這些伺服器真正分歧之處；
平均吞吐量往往落在雜訊範圍內。吞吐量（req/s）會一併回報。**Peak RSS**
（記憶體高水位）是次要的「VPS 規格選型」指標。CPU% 刻意*不*列為重點——
cgroup 的 CPU 取樣雜訊太大，不適合引用。

每個儲存格 = `{server, workload, concurrency, run}`，並以一個 JSON 檔存放在
`results/`，內嵌一份 manifest（鎖定的版本、上限、commit SHA、主機、wrk 旗標），
因此任何一個資料點都可以重現。記錄到 wrk 錯誤（非 2xx／逾時）的儲存格
會被標記，絕不會默默平均進去。

## 公平性控制（每個伺服器都維持一致）

| Control | Value | Why |
|---|---|---|
| Workers | 全部 **8**（FPM `pm=static, max_children=8`） | 相同的並行預算；Octane 約為每核心 2 個 worker × 4 核心 |
| CPU | 每個 app 容器 **`cpus=4`、`cpuset=0-3`** | 每個伺服器都拿到相同的 4 顆實體核心 |
| Load generator | **`wrk` 透過 `${WRK_CPUSET}` 釘核心**——在 8 核心以上的主機上釘 `4-7`（隔離），在 4 核心的預設 runner 上釘 `0-3`（共駐） | 當有多餘核心時隔離產生器；以 `generator_isolated` 逐儲存格公開 |
| Memory | `mem_limit=512m` | 相同的上限 |
| OPcache | 啟用，`validate_timestamps=0` | 程式碼只編譯一次，就像 Octane 那樣保留著 |
| App env | `APP_ENV=production`、`APP_DEBUG=false` | 走正式環境的程式碼路徑 |
| Sessions | `SESSION_DRIVER=array` | 無狀態端點——寫入鎖上不會序列化任何東西 |
| Versions | 鎖定：PHP 8.4、Laravel 13、Octane 2.17（見 manifest） | 沒有變動的零件 |

此框架**一次只跑一個 app 伺服器**（其他全部停止），因此它的 CPU/RAM 是在隔離狀態下量測，
而不是在閒置同袍的爭用之下。

**預設環境：一台 GitHub Actions `ubuntu-24.04` runner（4 vCPU / 16 GB RAM）。**
`benchmark.sh` 會依核心數調整：SUT 永遠拿到 `cpuset 0-3`，而 `wrk`
產生器**只有在主機具備 ≥ 8 顆核心時**才會被隔離到核心 `4-7`。在 4 核心的
runner 上沒有核心 `4-7`，因此產生器會與 SUT 共用 `0-3`——每個儲存格都
記錄 `generator_isolated: false`。由於 CI runner 同樣是吵雜的鄰居，請把那些執行結果
當作**僅供相對參考**。若想要產生器隔離後的數字，請在 8 核心以上的機器上執行
（框架會自動選用 `WRK_CPUSET=4-7`，你也可以自行設定）。

## 工作負載

工作負載被組織成三個**群組**，讓圖表和表格讀起來像是
「overhead → CPU 花在哪 → I/O」。`cpu` 群組的三條路由各自施壓於一條*不同的*
指令路徑，因此它們對於哪個伺服器勝出可能各執一詞。

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | 路由 + 回應開銷 | 固定長度的 body |
| cpu | `/bench/hash` | 整數／位元運算 | `sha256` 鏈式運算 ×`BENCH_HASH_ITERATIONS`（校準到它 ≫ hello） |
| cpu | `/bench/mandelbrot` | 浮點／FPU | 逃逸時間 Mandelbrot，78×78 網格 ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | 序列化（codec） | 對一個 1000 整數陣列做 `json_encode`+`json_decode` 來回 ×`BENCH_JSON_ITERATIONS`（由 codec 主導，而非路由） |
| io | `/bench/db` | 一筆真實查詢 | 索引 PK 的 `SELECT`，對上 **MySQL 8** |

**`/bench/db` 注意事項：** 各伺服器在連線處理上有所不同（Swoole 協程連線池 vs
RoadRunner vs FrankenPHP）。此工作負載的範圍被界定為**「各伺服器預設的 Octane DB
行為」**，而非孤立的原始查詢量測。它在圖表上也是這樣標示的。

## 跑起來

**在 CI 中（預設）：** 透過 *Actions → Run workflow* 觸發 **Benchmark** workflow
（`.github/workflows/benchmark.yml`）。它在 `ubuntu-24.04` 上執行、建立報告，
並把 `results/` + `docs/` 以 artifact 上傳（可選擇將 `docs/` 發布到 `gh-pages`）。
輸入參數讓你能調整矩陣規模。

**在本機** —— **先決條件：** Docker（Compose v2）。

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

可透過環境變數調整：`SERVERS`、`WORKLOADS`、`CONCURRENCIES`、`RUNS`、`DURATION`、`WARMUP`、
`BENCH_HASH_ITERATIONS`、`BENCH_MANDELBROT_REPEAT`、`BENCH_JSON_ITERATIONS`。

## 運作原理

```
benchmark.sh ── per (server, workload):
  stop all app servers → start this one (+ mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → warm (discarded) → sweep concurrency × runs via the pinned wrk container
  → write results/{server}_{workload}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup memory high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Chart.js)
```

`wrk` 容器會跑一個小型的 Lua 回報器（`docker/wrk/report.lua`），輸出一行
JSON，包含完整的延遲百分位數以及各類別的錯誤計數。

## 注意事項

- **單機，相對而非絕對。** 你的數字會有所不同；*形狀*（誰在哪裡勝出）才是可移植的發現。
- **釘核心自我檢查。** 如果主機不遵守 `--cpuset-cpus`，每個儲存格都會被標記為
  `pinning=unverified`，而結果就不會被當作產生器隔離的數據呈現。
- **4 核心上的產生器共駐。** 在預設的 `ubuntu-24.04` runner 上，負載產生器會
  共用 SUT 的核心（`generator_isolated: false`）。比較依然公平——每個伺服器都在
  *同一個*共駐產生器之下量測——但相較於 8 核心的隔離執行，絕對延遲會被膨脹。
  無論如何，它都是一個相對量測。
- **`cpu` 群組校準。** `BENCH_HASH_ITERATIONS`（預設 2000）、
  `BENCH_MANDELBROT_REPEAT`（1）、以及 `BENCH_JSON_ITERATIONS`（1000）應該在
  你的機器上調校，讓每條 `cpu` 群組路由的延遲明顯主導於 `/bench/hello`。

## 路線圖

- **Phase 2 — 持續運行的基準測試：** GitHub Actions workflow 已經在
  `ubuntu-24.04` 上執行矩陣，並能發布到 `gh-pages`。下一步：加入 `schedule:` 觸發，
  在每次 PHP/Octane/伺服器發布時自動重新執行。（注意：託管 runner 雜訊很大；若要取得隔離的
  絕對數字，請使用自架的 8 核心以上 runner——屆時框架會自動把 `wrk` 釘到
  `4-7`。）
- **Phase 3 — 決策引擎：**「告訴我我的 app 的形狀 → 該選哪個伺服器 + worker 數量。」

## 目錄結構

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
