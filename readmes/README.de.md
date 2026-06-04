[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · **Deutsch** · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Ein reproduzierbares Harness, das die Laravel-Octane-Anwendungsserver
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) gegen eine traditionelle
**PHP-FPM + nginx**-Kontrollgruppe benchmarkt — und zeigt, *wo jeder einzelne gewinnt*.

Die meisten Octane-Benchmarks veröffentlichen eine einzige „schnellste" Zahl und
widersprechen sich gegenseitig, weil sie sich klammheimlich bei Workload, Worker-Anzahl,
Lastgenerator und Warm-vs-Kalt unterscheiden und davon selten etwas offenlegen. Dieses
hier fixiert jede Störvariable, legt sie alle offen und veröffentlicht
**Latenz-Crossover-Kurven pro Workload**. Das Urteil lautet ausdrücklich „es kommt darauf an
— und hier ist genau, worauf es ankommt. Lauf es selbst."

> Die Methodik ist das Produkt. Wenn du eine Zahl nicht aus ihrem Manifest reproduzieren
> kannst, ist das ein Bug.

## Ergebnisse

Lauf es und öffne `docs/index.html` (Charts) / `RESULTS.md` (Tabellen). Ein veröffentlichter
Lauf liegt im `gh-pages`-Branch.

Dies sind **Single-Machine**-Ergebnisse. Lies sie als **relativ** (welcher Server gewinnt und
bei welcher Concurrency der Gewinner kippt), nicht als absolute Zahlen für deine Hardware.

## Was gemessen wird

**Headline: p99 / p50 Latenz über einen Concurrency-Sweep.** Die Tail-Latenz ist der Punkt,
an dem diese Server tatsächlich auseinandergehen; der mittlere Durchsatz liegt oft im
Rauschen. Der Durchsatz (req/s) wird daneben berichtet. **Peak RSS** (Speicher-Höchststand)
ist eine sekundäre „VPS-Sizing"-Metrik. CPU% ist bewusst *keine* Headline — die
cgroup-CPU-Abtastung ist zu verrauscht, um sie zu zitieren.

Jede Zelle = `{server, workload, concurrency, run}` und wird als eine JSON-Datei in
`results/` mit einem eingebetteten Manifest gespeichert (gepinnte Versionen, Caps,
Commit-SHA, Host, wrk-Flags), sodass jeder Datenpunkt reproduzierbar ist. Zellen, die
wrk-Fehler aufgezeichnet haben (non-2xx / Timeouts), werden markiert und niemals
stillschweigend mit eingerechnet.

## Fairness-Kontrollen (für jeden Server identisch gehalten)

| Kontrolle | Wert | Warum |
|---|---|---|
| Worker | **8** überall (FPM `pm=static, max_children=8`) | gleiches Budget; Octanes ~2 Worker/CPU × 4 Kerne |
| CPU | **`cpus=4`, `cpuset=0-3`** pro App-Container | jeder Server bekommt dieselben 4 physischen Kerne |
| Lastgenerator | **`wrk` gepinnt via `${WRK_CPUSET}`** — `4-7` auf einem Host mit 8+ Kernen (isoliert), `0-3` auf dem standardmäßigen 4-Kern-Runner (co-resident) | isoliert den Generator, wenn dafür Kerne vorhanden sind; pro Zelle als `generator_isolated` offengelegt |
| Speicher | `mem_limit=512m` | gleiche Obergrenze |
| OPcache | aktiviert, `validate_timestamps=0` | Code einmal kompiliert, wie Octane ihn vorhält |
| App-Env | `APP_ENV=production`, `APP_DEBUG=false` | Produktions-Codepfade |
| Sessions | `SESSION_DRIVER=array` | zustandslose Endpunkte — nichts serialisiert auf einem Write-Lock |
| Versionen | gepinnt: PHP 8.4, Laravel 13, Octane 2.17 (siehe Manifest) | keine beweglichen Teile |

Das Harness lässt **immer nur einen App-Server gleichzeitig** laufen (alle anderen gestoppt),
sodass dessen CPU/RAM isoliert gemessen werden, nicht unter Konkurrenz durch untätige
Geschwister.

**Standardumgebung: ein GitHub Actions `ubuntu-24.04`-Runner (4 vCPU / 16 GB RAM).**
`benchmark.sh` passt sich an die Kern-Anzahl an: der SUT bekommt immer `cpuset 0-3`, und der
`wrk`-Generator wird auf den Kernen `4-7` isoliert, **nur wenn der Host ≥ 8 Kerne hat**. Auf
dem 4-Kern-Runner gibt es keine Kerne `4-7`, also teilt sich der Generator `0-3` mit dem SUT
— jede Zelle erfasst `generator_isolated: false`. Da CI-Runner ebenfalls lautstarke Nachbarn
sind, lies diese Läufe als **nur relativ**. Für generator-isolierte Zahlen lauf es auf einer
Maschine mit 8+ Kernen (das Harness wählt `WRK_CPUSET=4-7` automatisch, oder setze es selbst).

## Workloads

Die Workloads sind in drei **Gruppen** organisiert, sodass sich die Charts und Tabellen wie
„Overhead → wohin die CPU geht → I/O" lesen lassen. Die drei Routen der `cpu`-Gruppe belasten
jeweils einen *anderen* Instruktionspfad, sodass sie sich darin uneinig sein können, welcher
Server gewinnt.

| Gruppe | Route | Isoliert | Hinweise |
|---|---|---|---|
| overhead | `/bench/hello` | Routing + Response-Overhead | Body fester Länge |
| cpu | `/bench/hash` | Integer / Bitweise | `sha256`-Verkettung ×`BENCH_HASH_ITERATIONS` (so kalibrieren, dass ≫ hello) |
| cpu | `/bench/mandelbrot` | Float / FPU | Escape-Time-Mandelbrot, 78×78-Raster ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | Serialisierung (Codec) | `json_encode`+`json_decode` Round-Trip eines 1000-Integer-Arrays ×`BENCH_JSON_ITERATIONS` (Codec dominiert, nicht Routing) |
| io | `/bench/db` | eine echte Query | indizierter PK-`SELECT` gegen **MySQL 8** |

**`/bench/db`-Vorbehalt:** Die Server unterscheiden sich in der Verbindungsbehandlung
(Swoole-Coroutine-Pool vs RoadRunner vs FrankenPHP). Dieser Workload ist abgegrenzt als
**„das jeweils standardmäßige Octane-DB-Verhalten jedes Servers"**, nicht als isolierte
Roh-Query-Messung. Im Chart ist er entsprechend gekennzeichnet.

## Lauf es

**In CI (Standard):** Löse den **Benchmark**-Workflow
(`.github/workflows/benchmark.yml`) über *Actions → Run workflow* aus. Er läuft auf
`ubuntu-24.04`, baut den Report und lädt `results/` + `docs/` als Artefakt hoch
(optional wird `docs/` nach `gh-pages` veröffentlicht). Über Inputs lässt sich die Matrix
skalieren.

**Lokal** — **Voraussetzung:** Docker (Compose v2).

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

Einstellbar über Env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `RUNS`, `DURATION`, `WARMUP`,
`BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`.

## Wie es funktioniert

```
benchmark.sh ── per (server, workload):
  stop all app servers → start this one (+ mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → warm (discarded) → sweep concurrency × runs via the pinned wrk container
  → write results/{server}_{workload}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup memory high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Chart.js)
```

Der `wrk`-Container führt einen kleinen Lua-Reporter (`docker/wrk/report.lua`) aus, der eine
JSON-Zeile mit vollständigen Latenz-Perzentilen und Fehleranzahlen pro Klasse ausgibt.

## Vorbehalte

- **Single-Machine, relativ nicht absolut.** Deine Zahlen werden abweichen; die *Form* (wer
  wo gewinnt) ist der übertragbare Befund.
- **Pinning-Self-Check.** Wenn der Host `--cpuset-cpus` nicht respektiert, wird jede Zelle mit
  `pinning=unverified` markiert und das Ergebnis nicht als generator-isoliert dargestellt.
- **Generator-Co-Residenz auf 4 Kernen.** Auf dem standardmäßigen `ubuntu-24.04`-Runner teilt
  sich der Lastgenerator die Kerne des SUT (`generator_isolated: false`). Der Vergleich bleibt
  fair — jeder Server wird unter dem *gleichen* co-residenten Generator gemessen — aber die
  absolute Latenz ist gegenüber einem isolierten 8-Kern-Lauf aufgebläht. So oder so ist es
  eine relative Messung.
- **Kalibrierung der `cpu`-Gruppe.** `BENCH_HASH_ITERATIONS` (Default 2000),
  `BENCH_MANDELBROT_REPEAT` (1) und `BENCH_JSON_ITERATIONS` (1000) sollten auf
  deiner Maschine so abgestimmt werden, dass die Latenz jeder Route der `cpu`-Gruppe `/bench/hello` klar dominiert.

## Roadmap

- **Phase 2 — lebendiger Benchmark:** Der GitHub-Actions-Workflow führt die Matrix bereits auf
  `ubuntu-24.04` aus und kann nach `gh-pages` veröffentlichen. Als Nächstes: ein
  `schedule:`-Trigger zum automatischen erneuten Lauf bei jedem PHP-/Octane-/Server-Release.
  (Vorbehalt: gehostete Runner sind verrauscht; für isolierte absolute Zahlen verwende einen
  self-hosted Runner mit 8+ Kernen — das Harness pinnt `wrk` dann automatisch auf `4-7`.)
- **Phase 3 — Entscheidungsmaschine:** „sag mir die Form meiner App → welcher Server + welche Worker-Anzahl."

## Aufbau

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
