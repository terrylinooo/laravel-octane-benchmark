[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · **日本語** · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Laravel Octane のアプリケーションサーバー（**Swoole**、**OpenSwoole**、**RoadRunner**、**FrankenPHP**）を、従来型の **PHP-FPM + nginx** 対照群と比較ベンチマークし、 *それぞれがどこで勝つのか* を示す再現可能なハーネスです。

ほとんどの Octane ベンチマークは単一の「最速」値だけを公表し、互いに矛盾しています。ワークロード、ワーカー数、負荷生成ツール、ウォームかコールドかといった条件がこっそり異なっているにもかかわらず、それらをほとんど開示しないからです。本プロジェクトは、あらゆる交絡変数を固定し、そのすべてを開示し、**ワークロードごとのレイテンシ交差曲線**を公表します。結論は明確に「場合による—そして、どう場合によるのかを正確にここに示す。自分で実行してみてほしい」です。

## なぜ 2 CPU / 4 GB なのか

過剰な性能を持つマシンで framework benchmark を実行しても、現代の多くのデプロイにとって実用的な価値はほとんどありません。現在はコンテナの時代であり、アプリケーションは通常、小さく再現可能な単位でデプロイされ、トラフィックの増加に応じて水平スケールします。本当に知りたいのは、潤沢なリソースを持つ高性能サーバーで framework がどこまで速く動くかではなく、一般的なコンテナが次の replica を追加するまでに、どれだけ安定したスループットとテールレイテンシを提供できるかです。

そのため、この benchmark では `2 CPU / 4 GB RAM` をアプリケーションコンテナの基本単位としています。これは小規模な本番環境で一般的な割り当てであり、Laravel を適切に動かせる一方で、worker の競合、メモリコスト、飽和挙動も明確に表れます。この規模で得られる結果は、単一の framework プロセスに専有させることがほとんどない高性能マシンのスコアよりも、キャパシティ計画、自動スケーリングのしきい値、コスト比較に役立ちます。

最速であることは、必ずしも最良であることを意味しません。Swoole/OpenSwoole、RoadRunner、 FrankenPHP にはそれぞれ異なるトレードオフがあり、向いているアプリケーションの形も異なります。実際の選定では、運用モデル、エコシステムのサポート、デプロイ方式、拡張との互換性、チームの習熟度も関わります。本プロジェクトはその選定判断を扱いません。公平で再現可能な環境でデータを出すことだけを目的としています。

## Results

実行して `docs/index.html`（チャート）/ `RESULTS.md`（テーブル）を開いてください。公開済みの実行結果は GitHub Pages にデプロイされます（Settings → Pages → Source: GitHub Actions）。サイトは小さなマルチページのダッシュボードです。**Compare** ページ（勝者ヒートマップ、ワークロードごとの p99 + スループット曲線とデータテーブル、ピーク RSS）に加え、各 Octane サーバー（Swoole / OpenSwoole / RoadRunner / FrankenPHP）ごとの **サーバー別ディープレポート** ページがあり、**worker-count トグル** でビュー全体をスイープ済みのワーカー数の間で切り替えられます。

これらは **単一マシン** の結果です。**相対的なもの**（どのサーバーが勝つか、どの並行数で勝者が入れ替わるか）として読み、あなたのハードウェアにおける絶対値としては読まないでください。

## What's measured

**主役: 並行数スイープにおける p99 / p50 レイテンシ。** テールレイテンシこそが、これらのサーバーが実際に分かれる場所です。平均スループットはノイズの範囲内に収まることがよくあります。スループット（req/s）も併せて報告します。**ピーク RSS**（メモリの最高水位）は副次的な「VPS サイジング」指標です。CPU% はあえて主役にしていません—cgroup の CPU サンプリングは引用するには騒がしすぎます。

各セル = `{server, workload, workers, concurrency, run}` で、`results/` に 1 つの JSON ファイルとして保存され、埋め込まれたマニフェスト（固定バージョン、上限、コミット SHA、ホスト、wrk フラグ）を含むため、どのデータポイントも再現可能です。wrk エラー（非 2xx / タイムアウト）を記録したセルはフラグ付けされ、黙って平均に混ぜ込まれることはありません。

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| Workers | **スイープ**（`WORKER_COUNTS`、2-worker の基準値、~2/cpu、その ×2 → 2-cpu ランナーでは `2 4 8`）。FPM の `max_children` を一致させる | マトリクスの一次元—各サーバーがワーカーとともにどうスケールするかを見る。1 パスごとにすべてのサーバー（FPM 対照群を含む）で同じ数。CPU が oversubscribe されると、ワーカーを増やすとかえって遅くなることがある |
| CPU | SUT は予約済みの 2 コアを除くすべてのホストコアを使用（4 コアランナーでは `cpuset 2-3`） | どのサーバーにも同じ CPU 予算を与える |
| 負荷生成 + DB | `wrk` と `mysql` に専用コアを 1 つずつ割り当てる（`0` と `1`）。SUT とは分離 | 生成ツールと DB は SUT の CPU を奪わず、`/bench/db` は MySQL の CPU 競合を受けない |
| Memory | `mem_limit=4g`（env `MEM_LIMIT`） | 寛大で **均等な** 上限—16 GB ランナーでは決して縛られないため、どのサーバーも OOM ペナルティを受けず、ピーク RSS は真の最高水位を読み取る（クランプされない）。小規模 VPS シナリオには `MEM_LIMIT=512m` を設定 |
| OPcache | 有効、`validate_timestamps=0` | Octane が保持するのと同様に、コードを一度だけコンパイル |
| App env | `APP_ENV=production`、`APP_DEBUG=false` | 本番のコードパス |
| Sessions | `SESSION_DRIVER=array` | ステートレスなエンドポイント—書き込みロックで直列化されるものがない |
| Versions | 固定: PHP 8.4、Laravel 13、Octane 2.17（マニフェスト参照） | 可動部分なし |

ハーネスは **一度に 1 つのアプリサーバーのみ** を実行する（他はすべて停止）ため、その CPU/RAM はアイドル状態の兄弟プロセスとの競合下ではなく、分離して計測されます。

**デフォルト環境: GitHub Actions `ubuntu-24.04`（4 vCPU / 16 GB RAM）。** `wrk` は core `0`、`mysql` は core `1`、SUT は `cpuset 2-3` を使用し、`cpus=2` と `mem_limit=4g` が設定されます。8 コアホストでは `wrk` と `mysql` は `0` と `1` のまま、SUT は `cpuset 2-7` を使用します。これにより生成ツールと DB は SUT から分離されます。共有 CI ランナーにはノイズがあるため、正確な数値より結果の形を重視してください。

## Workloads

ワークロードは 3 つの **グループ** に整理されており、チャートとテーブルが「overhead → CPU がどこに使われるか → I/O」と読めるようになっています。`cpu` グループの 3 つのルートはそれぞれ *異なる* 命令パスに負荷をかけるため、どのサーバーが勝つかについて意見が分かれる可能性があります。

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | ルーティング + レスポンスのオーバーヘッド | 固定長のボディ |
| cpu | `/bench/hash` | 整数 / ビット演算 | `sha256` チェーン ×`BENCH_HASH_ITERATIONS`（hello を ≫ 上回るよう調整） |
| cpu | `/bench/mandelbrot` | 浮動小数点 / FPU | エスケープ時間方式のマンデルブロ集合、`BENCH_MANDELBROT_DIM`²×4 グリッド、`…_MAX_ITER` 上限、×`…_REPEAT`（デフォルト ~30ms） |
| cpu | `/bench/json` | シリアライズ（codec） | 1000 要素の int 配列の `json_encode`+`json_decode` ラウンドトリップ ×`BENCH_JSON_ITERATIONS`（ルーティングではなく codec が支配的。デフォルト ~20ms） |
| io | `/bench/db` | 実際のクエリ | インデックス付き PK の `SELECT` 対 **MySQL 8** |

**`/bench/db` の注意点:** サーバーは接続処理が異なります（Swoole のコルーチンプール 対 RoadRunner 対 FrankenPHP）。このワークロードは **「各サーバーのデフォルトの Octane DB 挙動」** として位置づけられており、分離された生クエリの計測ではありません。チャートにもその旨が表示されます。

## Run it

このプロジェクトは、デフォルトでは GitHub Actions runner でベンチマークを実行し、レポートを生成するようになっています。このリポジトリの workflow をそのまま使うことも、fork して自分のリポジトリで実行することもできます。自分で管理するローカルマシンやリモートマシンで同じ harness を実行することもできます。

**CI で（デフォルト）:** **Benchmark** ワークフロー（`.github/workflows/benchmark.yml`）を *Actions → Run workflow* からトリガーします。`ubuntu-24.04` 上で実行され、レポートをビルドし、`results/` + `docs/` をアーティファクトとしてアップロードします（`publish` 入力を設定すると `docs/` を GitHub Pages にデプロイ）。入力でマトリクスをスケールできます。

**ローカルで** — **前提条件:** Docker（Compose v2）、および `make deps` 用にホスト上の PHP 8.4 + Composer（ホスト上で動くのは `composer install` だけで、それ以外はすべて Docker 内）。`Makefile` がワークフローをラップしています—`make help` ですべてのターゲットが一覧表示されます。

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

env で調整可能: `SERVERS`、`WORKLOADS`、`CONCURRENCIES`、`WORKER_COUNTS`、`RUNS`、`DURATION`、`WARMUP`、`TIMEOUT`、`BENCH_HASH_ITERATIONS`、`BENCH_MANDELBROT_DIM`、`BENCH_MANDELBROT_MAX_ITER`、`BENCH_MANDELBROT_REPEAT`、`BENCH_JSON_ITERATIONS`。各（server, workload）は実行前に **各並行数で**ウォームアップされ、`wrk --timeout`（デフォルト 15s）により、飽和した遅いセルもエラーとして打ち切らず計測できます。

`benchmark.sh` はデフォルトで 2-worker baseline を測定し、その後におよそ `2 * SUT_CPUS` のワーカー数と、その 2 倍をテストします。デフォルトの 4-vCPU ランナーでは SUT が 2 CPUs を得るため、デフォルトの worker sweep は `2 4 8` です。ワーカー数を増やしたときにスループットが低下したり p99 が悪化したりしても、それは有効な結果です。通常は、追加の PHP workers が scheduler contention、cache pressure、DB/socket contention を増やし、有効な CPU 容量を増やしていないことを示します。

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

`wrk` コンテナは小さな Lua レポーター（`docker/wrk/report.lua`）を実行し、完全なレイテンシパーセンタイルとクラス別エラー数を含む 1 行の JSON を出力します。

## Idle memory profiler

別のツールが、**Octane がワーカーごとにどれだけの RAM を常駐させるか**—フレームワークをウォームに保つメモリコスト—を、負荷なしで計測します:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

このフィットは、**固定** のフレームワーク/マスター/OPcache のオーバーヘッドを、ワーカーを 1 つ増やす **限界** コストから切り分けます。素朴な `RSS / N` の平均は誤解を招きます—N が増えると下がるのは、固定コストが償却されるためであって、ワーカーが安くなったからではありません。

## Caveats

- **単一マシン、絶対ではなく相対。** あなたの数値は異なります。移植可能な発見は *形* （どこで誰が勝つか）です。
- **Pinning セルフチェック。** ホストが `--cpuset-cpus` を尊重しない場合、すべてのセルは `pinning=unverified` とタグ付けされ、結果は生成ツール分離として提示されません。
- **4 コアランナー上の 2-cpu / 4 GB SUT。** 残りの 2 コアは `wrk` と `mysql` に 1 つずつ予約され、SUT との CPU 競合を防ぎます。
- **ワーカー数が多いほど速いとは限らない。** 4 workers から 8 workers で低下する場合は、このマシン上の 局所的な飽和点を benchmark が見つけたと解釈してください。特に CPU-bound workload やデフォルトの 2-CPU SUT 分割ではそうです。
- **`cpu` グループのキャリブレーション。** デフォルトは **~20-30ms/リクエスト** を狙います。`/bench/hello` を支配するのに十分重く、4 コアの箱で並行数 128 までのスイープが `wrk` のタイムアウトに飽和しない程度に軽い。`BENCH_HASH_ITERATIONS`（2000）、`BENCH_MANDELBROT_DIM`（32）/ `BENCH_MANDELBROT_MAX_ITER`（256）、`BENCH_JSON_ITERATIONS`（150）で自分のマシンに合わせて調整してください。`…_REPEAT` はより重いホスト向けにマンデルブロをスケールアップします。

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

## ベンチマーク概要

公開レポート: [Dashboard UI](https://terrylinooo.github.io/laravel-octane-benchmark) · [結果データ](https://terrylinooo.github.io/laravel-octane-benchmark/summary.json)

このベンチマークは制御された単一マシン環境で実行しました。SUT の Docker コンテナは `2 CPU / 4 GB RAM` に制限され、`wrk` と `mysql` は別の CPU コアを使用します。したがって、これは同じリソース制限下での相対比較であり、すべての本番環境に通用する順位ではありません。

- p99 レイテンシが最も安定: FrankenPHP
- 一部のワークロードでピークスループットが最高: Swoole / OpenSwoole
- メモリ使用量が最小: PHP-FPM + nginx
- この構成で効率が最も低い: RoadRunner
- `2 CPU` 制限では通常 8 workers より 4 workers が有利

FrankenPHP はレイテンシの安定性、競争力のあるスループット、中程度のメモリ使用量のバランスが最良でした。Octane server はピーク requests per second だけで選ぶべきではありません。

## License

この Laravel Octane benchmark は MIT License で公開され、[Terry L.](https://terryl.in) によってメンテナンスされています。Terry L. は Airygen の開発者でもあります。Airygen は、構造化されたコンテンツワークフローと検索を意識した公開ツールを必要とするチーム向けの、無料で強力な [WordPress SEO Plugin](https://www.airygen.com/en) です。

## 検討中

Google Cloud Run などの serverless container サービスは、この benchmark で使っている固定 2-CPU container とは挙動が異なる場合があります。これらのサービスは通常、割り当てられた compute に対して課金され、基盤 host には多くの CPU cores があることがあります。worker 数を増やすと、理論上は設定されたサービス上限に達するまで利用可能な compute を消費できる可能性があります。この環境では、`workers = CPU x 2` という経験則が最適なデフォルトとは限りません。worker count は、実際の CPU 割り当て、concurrency model、課金方式、latency target に合わせて調整すべきです。
