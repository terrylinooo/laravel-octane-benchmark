[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · **日本語** · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane ベンチマーク

Laravel Octane のアプリケーションサーバー（**Swoole**、**OpenSwoole**、**RoadRunner**、
**FrankenPHP**）を、従来型の **PHP-FPM + nginx** 対照群と比較ベンチマークし、
*それぞれがどこで勝つのか* を示す再現可能なハーネスです。

ほとんどの Octane ベンチマークは単一の「最速」値だけを公表し、互いに矛盾しています。
ワークロード、ワーカー数、負荷生成ツール、ウォームかコールドかといった条件がこっそり
異なっているにもかかわらず、それらをほとんど開示しないからです。本プロジェクトは、
あらゆる交絡変数を固定し、そのすべてを開示し、**ワークロードごとのレイテンシ交差曲線**を
公表します。結論は明確に「場合による—そして、どう場合によるのかを正確にここに示す。
自分で実行してみてほしい」です。

> 方法論こそがプロダクトです。マニフェストからある数値を再現できないなら、それはバグです。

## 結果

実行して `docs/index.html`（チャート）/ `RESULTS.md`（テーブル）を開いてください。
公開済みの実行結果は `gh-pages` ブランチにあります。

これらは **単一マシン** の結果です。**相対的なもの**（どのサーバーが勝つか、どの並行数で
勝者が入れ替わるか）として読み、あなたのハードウェアにおける絶対値としては読まないでください。

## 計測対象

**主役: 並行数スイープにおける p99 / p50 レイテンシ。** テールレイテンシこそが、これらの
サーバーが実際に分かれる場所です。平均スループットはノイズの範囲内に収まることがよくあります。
スループット（req/s）も併せて報告します。**ピーク RSS**（メモリの最高水位）は副次的な
「VPS サイジング」指標です。CPU% はあえて主役にしていません—cgroup の CPU サンプリングは
引用するには騒がしすぎます。

各セル = `{server, workload, concurrency, run}` で、`results/` に 1 つの JSON ファイルとして
保存され、埋め込まれたマニフェスト（固定バージョン、上限、コミット SHA、ホスト、wrk フラグ）を
含むため、どのデータポイントも再現可能です。wrk エラー（非 2xx / タイムアウト）を記録した
セルはフラグ付けされ、黙って平均に混ぜ込まれることはありません。

## 公平性のためのコントロール（すべてのサーバーで同一に保持）

| コントロール | 値 | 理由 |
|---|---|---|
| ワーカー | どこでも **8**（FPM は `pm=static, max_children=8`） | 同じ予算。Octane の約 2 ワーカー/CPU × 4 コア |
| CPU | アプリコンテナごとに **`cpus=4`、`cpuset=0-3`** | 各サーバーが同じ 4 つの物理コアを得る |
| 負荷生成ツール | **`${WRK_CPUSET}` で固定された `wrk`** — 8 コア以上のホストでは `4-7`（分離）、4 コアのデフォルトランナーでは `0-3`（同居） | コアに余裕があるときに生成ツールを分離。セルごとに `generator_isolated` として開示 |
| メモリ | `mem_limit=512m` | 同じ上限 |
| OPcache | 有効、`validate_timestamps=0` | Octane が保持するのと同様に、コードを一度だけコンパイル |
| アプリ環境 | `APP_ENV=production`、`APP_DEBUG=false` | 本番のコードパス |
| セッション | `SESSION_DRIVER=array` | ステートレスなエンドポイント—書き込みロックで直列化されるものがない |
| バージョン | 固定: PHP 8.4、Laravel 13、Octane 2.17（マニフェスト参照） | 可動部分なし |

ハーネスは **一度に 1 つのアプリサーバーのみ** を実行する（他はすべて停止）ため、その CPU/RAM は
アイドル状態の兄弟プロセスとの競合下ではなく、分離して計測されます。

**デフォルト環境: GitHub Actions `ubuntu-24.04` ランナー（4 vCPU / 16 GB RAM）。**
`benchmark.sh` はコア数に適応します。SUT は常に `cpuset 0-3` を得て、`wrk` 生成ツールは
**ホストが 8 コア以上を持つ場合にのみ** コア `4-7` に分離されます。4 コアのランナーには
コア `4-7` がないため、生成ツールは SUT と `0-3` を共有します—各セルは
`generator_isolated: false` を記録します。CI ランナーは騒がしい隣人でもあるため、それらの
実行は **相対的にのみ** 読んでください。生成ツール分離の数値については、8 コア以上のマシンで
実行してください（ハーネスが自動的に `WRK_CPUSET=4-7` を選ぶか、自分で設定します）。

## ワークロード

ワークロードは 3 つの **グループ** に整理されており、チャートとテーブルが
「オーバーヘッド → CPU がどこに使われるか → I/O」と読めるようになっています。`cpu` グループの
3 つのルートはそれぞれ *異なる* 命令パスに負荷をかけるため、どのサーバーが勝つかについて
意見が分かれる可能性があります。

| グループ | ルート | 分離する対象 | 備考 |
|---|---|---|---|
| overhead | `/bench/hello` | ルーティング + レスポンスのオーバーヘッド | 固定長のボディ |
| cpu | `/bench/hash` | 整数 / ビット演算 | `sha256` チェーン ×`BENCH_HASH_ITERATIONS`（hello を ≫ 上回るよう調整） |
| cpu | `/bench/mandelbrot` | 浮動小数点 / FPU | エスケープ時間方式のマンデルブロ集合、78×78 グリッド ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | シリアライズ（コーデック） | 1000 要素の int 配列の `json_encode`+`json_decode` ラウンドトリップ ×`BENCH_JSON_ITERATIONS`（ルーティングではなくコーデックが支配的） |
| io | `/bench/db` | 実際のクエリ | インデックス付き PK の `SELECT` 対 **MySQL 8** |

**`/bench/db` の注意点:** サーバーは接続処理が異なります（Swoole のコルーチンプール 対
RoadRunner 対 FrankenPHP）。このワークロードは **「各サーバーのデフォルトの Octane DB 挙動」** として
位置づけられており、分離された生クエリの計測ではありません。チャートにもその旨が表示されます。

## 実行方法

**CI で（デフォルト）:** **Benchmark** ワークフロー
（`.github/workflows/benchmark.yml`）を *Actions → Run workflow* からトリガーします。
`ubuntu-24.04` 上で実行され、レポートをビルドし、`results/` + `docs/` をアーティファクトとして
アップロードします（任意で `docs/` を `gh-pages` に公開）。入力でマトリクスをスケールできます。

**ローカルで** — **前提条件:** Docker（Compose v2）。

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

env で調整可能: `SERVERS`、`WORKLOADS`、`CONCURRENCIES`、`RUNS`、`DURATION`、`WARMUP`、
`BENCH_HASH_ITERATIONS`、`BENCH_MANDELBROT_REPEAT`、`BENCH_JSON_ITERATIONS`。

## 仕組み

```
benchmark.sh ── per (server, workload):
  stop all app servers → start this one (+ mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → warm (discarded) → sweep concurrency × runs via the pinned wrk container
  → write results/{server}_{workload}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup memory high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Chart.js)
```

`wrk` コンテナは小さな Lua レポーター（`docker/wrk/report.lua`）を実行し、完全なレイテンシ
パーセンタイルとクラス別エラー数を含む 1 行の JSON を出力します。

## 注意点

- **単一マシン、絶対ではなく相対。** あなたの数値は異なります。移植可能な発見は *形*
  （どこで誰が勝つか）です。
- **ピン留めのセルフチェック。** ホストが `--cpuset-cpus` を尊重しない場合、すべてのセルは
  `pinning=unverified` とタグ付けされ、結果は生成ツール分離として提示されません。
- **4 コアでの生成ツール同居。** デフォルトの `ubuntu-24.04` ランナーでは、負荷生成ツールは
  SUT のコアを共有します（`generator_isolated: false`）。すべてのサーバーが *同じ* 同居生成ツールの
  下で計測されるため比較は公平に保たれますが、絶対レイテンシは 8 コア分離実行と比べて膨らみます。
  いずれにしても相対計測です。
- **`cpu` グループのキャリブレーション。** `BENCH_HASH_ITERATIONS`（デフォルト 2000）、
  `BENCH_MANDELBROT_REPEAT`（1）、`BENCH_JSON_ITERATIONS`（1000）は、各 `cpu` グループのルートの
  レイテンシが `/bench/hello` を明確に上回るよう、あなたのマシンで調整してください。

## ロードマップ

- **フェーズ 2 — 生きたベンチマーク:** GitHub Actions ワークフローはすでに `ubuntu-24.04` 上で
  マトリクスを実行し、`gh-pages` に公開できます。次に: 各 PHP/Octane/サーバーのリリースごとに
  自動で再実行する `schedule:` トリガー。（注意点: ホスト型ランナーは騒がしいため、分離された
  絶対値にはセルフホストの 8 コア以上のランナーを使ってください—その場合、ハーネスは自動的に
  `wrk` を `4-7` にピン留めします。）
- **フェーズ 3 — 意思決定エンジン:** 「自分のアプリの形を教えて → どのサーバー + ワーカー数」。

## 構成

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
