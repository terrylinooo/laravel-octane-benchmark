[English](../README.md) · **繁體中文** · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

一套可重現的測試框架，將 Laravel Octane 應用伺服器
（**Swoole**、**OpenSwoole**、**RoadRunner**、**FrankenPHP**）與傳統的
**PHP-FPM + nginx** 對照組進行基準測試，並呈現*各自的勝出場景*。

大多數 Octane 基準測試只發布單一個「最快」的數字，且彼此互相矛盾，
因為它們在工作負載、worker 數量、負載產生器、以及暖啟動對比冷啟動上悄悄地各有不同，
而且很少揭露這些細節。本框架固定了每一個干擾變數、揭露了全部細節，
並發布**各工作負載的延遲交叉曲線**。結論明確就是「視情況而定——以下正是它如何視情況而定。
自己跑一遍看看。」

## 結果

執行後開啟 `docs/index.html`（圖表）/ `RESULTS.md`（表格）。已發布的執行結果
會部署到 GitHub Pages（Settings → Pages → Source: GitHub Actions）。網站是一個
小型的多頁儀表板：一個 **Compare** 頁面（勝出者熱圖、各工作負載的 p99 +
吞吐量曲線與資料表、peak RSS），外加每個 Octane 伺服器（Swoole / OpenSwoole /
RoadRunner / FrankenPHP）各自的**逐伺服器深度報告**頁面，並提供一個 **worker 數量
切換器**，可在掃描過的各個 worker 數量之間切換整個檢視。

這些是**單機**結果。請以**相對**的角度解讀（哪個伺服器勝出、以及勝出者在哪個並發數
翻轉），而非當作你硬體上的絕對數字。

## 量測內容

**頭條：在並發掃描下的 p99 / p50 延遲。** 尾端延遲才是這些
伺服器真正分歧之處；平均吞吐量往往落在雜訊範圍內。吞吐量（req/s）一併
回報。**Peak RSS**（記憶體高水位標記）是次要的「VPS 規格選型」
指標。CPU% 刻意*不*列為頭條——cgroup 的 CPU 取樣太雜訊，不足以引用。

每個 cell = `{server, workload, workers, concurrency, run}`，並以一個 JSON 檔
儲存於 `results/`，內嵌一份 manifest（釘選的版本、上限、commit SHA、host、wrk
旗標），因此任何資料點都可重現。記錄到 wrk 錯誤（非 2xx /
逾時）的 cell 會被標記，絕不會被悄悄地平均進去。

## 公平性控制（對每個伺服器都維持一致）

| 控制項 | 值 | 原因 |
|---|---|---|
| Workers | **掃描**（`WORKER_COUNTS`，預設約 2/cpu 及其 ×2 → 在 2-cpu runner 上為 `4 8`）；FPM `max_children` 與之匹配 | 一個矩陣維度——觀察每個伺服器如何隨 worker 擴展。每一趟每個伺服器（含 FPM 對照組）都用相同數量 |
| CPU | **host 的下半部**——在 4 核 runner 上為 `cpus=2`、`cpuset=0-1`（在 8 核 host 上為 `cpus=4`、`cpuset=0-3`） | 每個伺服器都拿到相同的核心；SUT 的 cpu 數量記錄在 manifest 的上限中 |
| 負載產生器 | **`wrk` 在 host 的上半部**（runner 上為 `cpuset=2-3`，8 核上為 `4-7`）——與 SUT 不相交 | 產生器**永遠是隔離的**：它絕不會搶走 SUT 的 CPU。每個 cell 以 `generator_isolated` 記錄 |
| 記憶體 | `mem_limit=4g`（env `MEM_LIMIT`） | 寬裕的**相等**上限——在 16 GB runner 上絕不會觸頂，所以沒有任何伺服器會被 OOM 懲罰，且 peak RSS 讀到的是真正的高水位（未被截斷）。設定 `MEM_LIMIT=512m` 以模擬小型 VPS 情境 |
| OPcache | 啟用，`validate_timestamps=0` | 程式碼編譯一次，就像 Octane 保持的那樣 |
| App env | `APP_ENV=production`、`APP_DEBUG=false` | 正式環境的程式碼路徑 |
| Sessions | `SESSION_DRIVER=array` | 無狀態端點——沒有任何東西會在寫入鎖上序列化 |
| 版本 | 釘選：PHP 8.4、Laravel 13、Octane 2.17（見 manifest） | 沒有變動的零件 |

此框架**一次只執行一個應用伺服器**（其他全部停止），因此它的 CPU/RAM 是在
隔離狀態下量測，而非在閒置兄弟程序競爭下量測。

**預設環境：一個 GitHub Actions `ubuntu-24.04` runner（4 vCPU / 16 GB RAM）。**
`benchmark.sh` 會**將 host 一分為二**：SUT 拿到下半部核心，`wrk`
產生器拿到上半部核心，因此產生器**永遠是隔離的**（它絕不會搶走
SUT 的 CPU）。在 4 核 runner 上，這代表 **SUT 是 2 cpus**（`cpuset 0-1`），而 `wrk`
在 `2-3` 上執行；在 8 核 host 上，SUT 拿到 4 cpus（`0-3`），`wrk` 拿 `4-7`。代價
是 SUT 只拿到**半台機器**——所以在預設 runner 上，報告針對的是一個 **2-cpu
伺服器**，記錄在 manifest 的上限中（`cpus=2`）。由於共享 CI runner 仍然是
吵雜的鄰居，請把這些數字當作**僅供相對比較**。

## 工作負載

工作負載被組織成三個**群組**，讓圖表與表格讀起來就像
「overhead → CPU 花在哪 → I/O」。三條 `cpu` 群組的路由各自施壓於一條
*不同的*指令路徑，所以它們對於哪個伺服器勝出可能會有分歧。

| 群組 | 路由 | 隔離項 | 備註 |
|---|---|---|---|
| overhead | `/bench/hello` | routing + 回應開銷 | 固定長度的 body |
| cpu | `/bench/hash` | 整數 / 位元運算 | `sha256` 串接 ×`BENCH_HASH_ITERATIONS`（校準到讓它 ≫ hello） |
| cpu | `/bench/mandelbrot` | 浮點 / FPU | escape-time Mandelbrot，`BENCH_MANDELBROT_DIM`²×4 網格，`…_MAX_ITER` 上限，×`…_REPEAT`（預設約 30ms） |
| cpu | `/bench/json` | 序列化（codec） | 對一個 1000 個整數的陣列做 `json_encode`+`json_decode` 往返 ×`BENCH_JSON_ITERATIONS`（由 codec 主導，而非 routing；預設約 20ms） |
| io | `/bench/db` | 一次真實查詢 | 對 **MySQL 8** 做帶索引的 PK `SELECT` |

**`/bench/db` 注意事項：** 各伺服器在連線處理上有所不同（Swoole 協程池 vs
RoadRunner vs FrankenPHP）。此工作負載的範疇界定為**「各伺服器的預設 Octane DB
行為」**，而非一次隔離的原始查詢量測。它在圖表上也是如此標示。

## 執行方式

**在 CI（預設）：** 透過 *Actions → Run workflow* 觸發 **Benchmark** 工作流程
（`.github/workflows/benchmark.yml`）。它在
`ubuntu-24.04` 上執行、建置報告，並把 `results/` + `docs/` 上傳為一個 artifact
（將 `publish` 輸入設定為部署 `docs/` 到 GitHub Pages）。輸入可讓你擴展矩陣。

**本機執行**——**先決條件：** Docker（Compose v2），以及 host 上的 PHP 8.4 + Composer
供 `make deps` 使用（只有 `composer install` 在 host 上執行；其餘全部在 Docker 中）。
一個 `Makefile` 包裝了整個工作流程——`make help` 會列出每個 target。

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

可透過 env 調整：`SERVERS`、`WORKLOADS`、`CONCURRENCIES`、`WORKER_COUNTS`、`RUNS`、`DURATION`、`WARMUP`、
`TIMEOUT`、`BENCH_HASH_ITERATIONS`、`BENCH_MANDELBROT_DIM`、`BENCH_MANDELBROT_MAX_ITER`、
`BENCH_MANDELBROT_REPEAT`、`BENCH_JSON_ITERATIONS`。每個（server, workload）在其各次執行前
會**在每個並發數**都先暖機，而 `wrk --timeout`（預設 15s）讓一個緩慢、
飽和的 cell 能夠被量測，而非被當成錯誤而審查刪除。

## 運作原理

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

`wrk` 容器執行一個小型的 Lua 回報器（`docker/wrk/report.lua`），它輸出一行
JSON，包含完整的延遲百分位數與各類別的錯誤計數。

## 閒置記憶體分析器

一個獨立工具量測 **Octane 每個 worker 常駐多少 RAM**——讓
框架保持暖機的記憶體成本——且在無負載狀態下進行：

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

此擬合將**固定的**框架/master/OPcache 開銷與多一個 worker 的**邊際**
成本分離開來。天真的 `RSS / N` 平均值會造成誤導——它隨 N 增大而下降
只是因為固定成本被攤提了，而非因為一個 worker 變便宜了。

## 注意事項

- **單機，相對而非絕對。** 你的數字會有所不同；*形狀*（誰在哪裡
  勝出）才是可移植的發現。
- **Pinning 自我檢查。** 如果 host 不遵循 `--cpuset-cpus`，每個 cell 都會被標記為
  `pinning=unverified`，且結果不會被當成 generator-isolated 呈現。
- **4 核 runner 上的 2-cpu SUT。** 為了讓產生器保持隔離，host 被
  一分為二——所以在預設 runner 上每個伺服器都是一個 **2-cpu** 伺服器（另外 2 個核心
  驅動 `wrk`）。它標示在 manifest 中（`cpus=2`）。若要一個 4-cpu SUT *並*帶有一個隔離的
  產生器，你需要一台 8 核 host（此時的切分會給 SUT 4 個核心，`wrk` 拿另外 4 個）。
- **`cpu` 群組校準。** 預設值的目標是**每個請求約 20-30ms**：夠重以
  主導 `/bench/hello`，又夠輕讓掃描到並發 128 時不會在 4 核機器上飽和而
  進入 `wrk` 逾時。在你的機器上透過 `BENCH_HASH_ITERATIONS`（2000）、
  `BENCH_MANDELBROT_DIM`（32）/ `BENCH_MANDELBROT_MAX_ITER`（256）、以及
  `BENCH_JSON_ITERATIONS`（150）來調整；`…_REPEAT` 為更重的 host 把 mandelbrot 放大。

## 藍圖

- **Phase 2 — 活的基準測試：** GitHub Actions 工作流程已經在
  `ubuntu-24.04` 上執行矩陣，並可部署到 GitHub Pages。下一步：一個 `schedule:` 觸發器，
  在每次 PHP/Octane/伺服器發布時自動重新執行。（注意事項：託管 runner 很吵雜；若要一個 **4-cpu**
  SUT 並讓產生器仍然隔離，請使用一台自架的 8 核以上 runner——此時的切分會
  自動給 SUT `0-3`、`wrk` `4-7`。）
- **Phase 3 — 決策引擎：** 「告訴我我的 app 的形狀 → 該選哪個伺服器 + worker 數量。」

## 結構

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
