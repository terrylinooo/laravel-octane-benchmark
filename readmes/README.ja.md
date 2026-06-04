[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · **日本語** · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Laravel Octane のアプリケーションサーバー（**Swoole**、**OpenSwoole**、**RoadRunner**、
**FrankenPHP**）を、従来型の **PHP-FPM + nginx** 対照群と比較ベンチマークし、
*それぞれがどこで勝つのか* を示す再現可能なハーネスです。

ほとんどの Octane ベンチマークは単一の「最速」値だけを公表し、互いに矛盾しています。
ワークロード、ワーカー数、負荷生成ツール、ウォームかコールドかといった条件がこっそり
異なっているにもかかわらず、それらをほとんど開示しないからです。本プロジェクトは、
あらゆる交絡変数を固定し、そのすべてを開示し、**ワークロードごとのレイテンシ交差曲線**を
公表します。結論は明確に「場合による—そして、どう場合によるのかを正確にここに示す。
自分で実行してみてほしい」です。

最速であることは、必ずしも最良であることを意味しません。Swoole/OpenSwoole、RoadRunner、
FrankenPHP にはそれぞれ異なるトレードオフがあり、向いているアプリケーションの形も異なります。
実際の選定では、運用モデル、エコシステムのサポート、デプロイ方式、拡張との互換性、チームの
習熟度も関わります。本プロジェクトはその選定判断を扱いません。公平で再現可能な環境でデータを
出すことだけを目的としています。

## Results

実行して `docs/index.html`（チャート）/ `RESULTS.md`（テーブル）を開いてください。
公開済みの実行結果は GitHub Pages にデプロイされます（Settings → Pages → Source: GitHub Actions）。
サイトは小さなマルチページのダッシュボードです。**Compare** ページ（勝者ヒートマップ、ワークロード
ごとの p99 + スループット曲線とデータテーブル、ピーク RSS）に加え、各 Octane サーバー
（Swoole / OpenSwoole / RoadRunner / FrankenPHP）ごとの **サーバー別ディープレポート** ページがあり、
**worker-count トグル** でビュー全体をスイープ済みのワーカー数の間で切り替えられます。

これらは **単一マシン** の結果です。**相対的なもの**（どのサーバーが勝つか、どの並行数で
勝者が入れ替わるか）として読み、あなたのハードウェアにおける絶対値としては読まないでください。

## What's measured

**主役: 並行数スイープにおける p99 / p50 レイテンシ。** テールレイテンシこそが、これらの
サーバーが実際に分かれる場所です。平均スループットはノイズの範囲内に収まることがよくあります。
スループット（req/s）も併せて報告します。**ピーク RSS**（メモリの最高水位）は副次的な
「VPS サイジング」指標です。CPU% はあえて主役にしていません—cgroup の CPU サンプリングは
引用するには騒がしすぎます。

各セル = `{server, workload, workers, concurrency, run}` で、`results/` に 1 つの JSON ファイルとして
保存され、埋め込まれたマニフェスト（固定バージョン、上限、コミット SHA、ホスト、wrk フラグ）を
含むため、どのデータポイントも再現可能です。wrk エラー（非 2xx / タイムアウト）を記録した
セルはフラグ付けされ、黙って平均に混ぜ込まれることはありません。

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| Workers | **スイープ**（`WORKER_COUNTS`、デフォルトは ~2/cpu とその ×2 → 2-cpu ランナーでは `4 8`）。FPM の `max_children` を一致させる | マトリクスの一次元—各サーバーがワーカーとともにどうスケールするかを見る。1 パスごとにすべてのサーバー（FPM 対照群を含む）で同じ数 |
| CPU | **ホストの下半分**—4 コアランナーで `cpus=2`、`cpuset=0-1`（8 コアホストでは `cpus=4`、`cpuset=0-3`） | どのサーバーも同じコアを得る。SUT の cpu 数はマニフェストの上限に記録される |
| Load generator | **ホストの上半分での `wrk`**（ランナーでは `cpuset=2-3`、8 コアでは `4-7`）—SUT とは交わらない | 生成ツールは **常に分離されている**。SUT の CPU を決して奪わない。セルごとに `generator_isolated` として記録される |
| Memory | `mem_limit=4g`（env `MEM_LIMIT`） | 寛大で **均等な** 上限—16 GB ランナーでは決して縛られないため、どのサーバーも OOM ペナルティを受けず、ピーク RSS は真の最高水位を読み取る（クランプされない）。小規模 VPS シナリオには `MEM_LIMIT=512m` を設定 |
| OPcache | 有効、`validate_timestamps=0` | Octane が保持するのと同様に、コードを一度だけコンパイル |
| App env | `APP_ENV=production`、`APP_DEBUG=false` | 本番のコードパス |
| Sessions | `SESSION_DRIVER=array` | ステートレスなエンドポイント—書き込みロックで直列化されるものがない |
| Versions | 固定: PHP 8.4、Laravel 13、Octane 2.17（マニフェスト参照） | 可動部分なし |

ハーネスは **一度に 1 つのアプリサーバーのみ** を実行する（他はすべて停止）ため、その CPU/RAM は
アイドル状態の兄弟プロセスとの競合下ではなく、分離して計測されます。

**デフォルト環境: GitHub Actions `ubuntu-24.04` ランナー（4 vCPU / 16 GB RAM）。**
`benchmark.sh` は **ホストを半分に分割** します。SUT は下位コアを、`wrk` 生成ツールは上位コアを
得るので、生成ツールは **常に分離されています**（SUT の CPU を決して奪わない）。4 コアランナーでは、
**SUT は 2 cpus**（`cpuset 0-1`）で `wrk` は `2-3` で動きます。8 コアホストでは SUT が 4 cpus（`0-3`）、
`wrk` が `4-7` を得ます。トレードオフは、SUT が **箱の半分しか** 得られないこと—なので、デフォルト
ランナーではレポートは **2-cpu サーバー** についてのもので、マニフェストの上限に記録されます（`cpus=2`）。
共有 CI ランナーは依然として騒がしい隣人なので、数値は **相対的なものとしてのみ** 読んでください。

## Workloads

ワークロードは 3 つの **グループ** に整理されており、チャートとテーブルが
「overhead → CPU がどこに使われるか → I/O」と読めるようになっています。`cpu` グループの
3 つのルートはそれぞれ *異なる* 命令パスに負荷をかけるため、どのサーバーが勝つかについて
意見が分かれる可能性があります。

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | ルーティング + レスポンスのオーバーヘッド | 固定長のボディ |
| cpu | `/bench/hash` | 整数 / ビット演算 | `sha256` チェーン ×`BENCH_HASH_ITERATIONS`（hello を ≫ 上回るよう調整） |
| cpu | `/bench/mandelbrot` | 浮動小数点 / FPU | エスケープ時間方式のマンデルブロ集合、`BENCH_MANDELBROT_DIM`²×4 グリッド、`…_MAX_ITER` 上限、×`…_REPEAT`（デフォルト ~30ms） |
| cpu | `/bench/json` | シリアライズ（codec） | 1000 要素の int 配列の `json_encode`+`json_decode` ラウンドトリップ ×`BENCH_JSON_ITERATIONS`（ルーティングではなく codec が支配的。デフォルト ~20ms） |
| io | `/bench/db` | 実際のクエリ | インデックス付き PK の `SELECT` 対 **MySQL 8** |

**`/bench/db` の注意点:** サーバーは接続処理が異なります（Swoole のコルーチンプール 対
RoadRunner 対 FrankenPHP）。このワークロードは **「各サーバーのデフォルトの Octane DB 挙動」** として
位置づけられており、分離された生クエリの計測ではありません。チャートにもその旨が表示されます。

## Run it

このプロジェクトは、デフォルトでは GitHub Actions runner でベンチマークを実行し、レポートを
生成するようになっています。このリポジトリの workflow をそのまま使うことも、fork して自分の
リポジトリで実行することもできます。自分で管理するローカルマシンやリモートマシンで同じ
harness を実行することもできます。

**CI で（デフォルト）:** **Benchmark** ワークフロー
（`.github/workflows/benchmark.yml`）を *Actions → Run workflow* からトリガーします。
`ubuntu-24.04` 上で実行され、レポートをビルドし、`results/` + `docs/` をアーティファクトとして
アップロードします（`publish` 入力を設定すると `docs/` を GitHub Pages にデプロイ）。入力で
マトリクスをスケールできます。

**ローカルで** — **前提条件:** Docker（Compose v2）、および `make deps` 用にホスト上の
PHP 8.4 + Composer（ホスト上で動くのは `composer install` だけで、それ以外はすべて Docker 内）。
`Makefile` がワークフローをラップしています—`make help` ですべてのターゲットが一覧表示されます。

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

env で調整可能: `SERVERS`、`WORKLOADS`、`CONCURRENCIES`、`WORKER_COUNTS`、`RUNS`、`DURATION`、`WARMUP`、
`TIMEOUT`、`BENCH_HASH_ITERATIONS`、`BENCH_MANDELBROT_DIM`、`BENCH_MANDELBROT_MAX_ITER`、
`BENCH_MANDELBROT_REPEAT`、`BENCH_JSON_ITERATIONS`。各（server, workload）は実行前に **各並行数で**
ウォームアップされ、`wrk --timeout`（デフォルト 15s）により、飽和した遅いセルもエラーとして打ち切らず
計測できます。

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

`wrk` コンテナは小さな Lua レポーター（`docker/wrk/report.lua`）を実行し、完全なレイテンシ
パーセンタイルとクラス別エラー数を含む 1 行の JSON を出力します。

## Idle memory profiler

別のツールが、**Octane がワーカーごとにどれだけの RAM を常駐させるか**—フレームワークを
ウォームに保つメモリコスト—を、負荷なしで計測します:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

このフィットは、**固定** のフレームワーク/マスター/OPcache のオーバーヘッドを、ワーカーを 1 つ
増やす **限界** コストから切り分けます。素朴な `RSS / N` の平均は誤解を招きます—N が増えると
下がるのは、固定コストが償却されるためであって、ワーカーが安くなったからではありません。

## Caveats

- **単一マシン、絶対ではなく相対。** あなたの数値は異なります。移植可能な発見は *形*
  （どこで誰が勝つか）です。
- **Pinning セルフチェック。** ホストが `--cpuset-cpus` を尊重しない場合、すべてのセルは
  `pinning=unverified` とタグ付けされ、結果は生成ツール分離として提示されません。
- **4 コアランナー上の 2-cpu SUT。** 生成ツールを分離するため、ホストは半分に分割されます—
  なのでデフォルトランナーでは各サーバーは **2-cpu** サーバーです（残りの 2 コアが `wrk` を駆動）。
  マニフェストにラベル付けされます（`cpus=2`）。生成ツールを分離した *まま* の 4-cpu SUT には
  8 コアホストが必要です（その分割では SUT に 4 コア、`wrk` に残りの 4 コアが与えられる）。
- **`cpu` グループのキャリブレーション。** デフォルトは **~20-30ms/リクエスト** を狙います。
  `/bench/hello` を支配するのに十分重く、4 コアの箱で並行数 128 までのスイープが `wrk` の
  タイムアウトに飽和しない程度に軽い。`BENCH_HASH_ITERATIONS`（2000）、
  `BENCH_MANDELBROT_DIM`（32）/ `BENCH_MANDELBROT_MAX_ITER`（256）、
  `BENCH_JSON_ITERATIONS`（150）で自分のマシンに合わせて調整してください。`…_REPEAT` はより
  重いホスト向けにマンデルブロをスケールアップします。

## Roadmap

- **Phase 2 — 生きたベンチマーク:** GitHub Actions ワークフローはすでに `ubuntu-24.04` 上で
  マトリクスを実行し、GitHub Pages にデプロイできます。次に: 各 PHP/Octane/サーバーのリリースごとに
  自動で再実行する `schedule:` トリガー。（注意点: ホスト型ランナーは騒がしいため、生成ツールを
  分離したままの **4-cpu** SUT には、セルフホストの 8 コア以上のランナーを使ってください—その分割は
  SUT に `0-3`、`wrk` に `4-7` を自動的に与えます。）
- **Phase 3 — 意思決定エンジン:** 「自分のアプリの形を教えて → どのサーバー + ワーカー数」。

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
