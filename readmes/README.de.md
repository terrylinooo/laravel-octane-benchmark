[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · **Deutsch** · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Ein reproduzierbares Harness, das die Laravel-Octane-Anwendungsserver
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) gegen eine traditionelle
**PHP-FPM + nginx**-Kontrollgruppe testet — und zeigt, *wo jeder einzelne gewinnt*.

Die meisten Octane-Benchmarks veröffentlichen eine einzige „schnellste" Zahl und
widersprechen sich gegenseitig, weil sie sich stillschweigend bei Workload, Worker-Anzahl,
Lastgenerator und warm-vs-kalt unterscheiden — und davon selten etwas offenlegen. Dieses
Harness fixiert jede Störvariable, legt sie alle offen und veröffentlicht
**Latenz-Crossover-Kurven pro Workload**. Das Urteil lautet ausdrücklich „es kommt darauf an —
und hier ist genau, worauf. Führe es selbst aus."

Am schnellsten zu sein bedeutet nicht automatisch, am besten zu sein. Swoole/OpenSwoole,
RoadRunner und FrankenPHP haben jeweils eigene Stärken, Schwächen und passende
Einsatzszenarien. Eine echte Auswahl hängt auch vom Betriebsmodell, der Unterstützung im
Ökosystem, der Deployment-Form, der Kompatibilität von Extensions und der Vertrautheit des
Teams ab. Dieses Projekt versucht diese Entscheidung nicht zu treffen; es führt die Server
nur in einer fairen, reproduzierbaren Umgebung aus und veröffentlicht die Daten.

## Ergebnisse

Führe es aus und öffne `docs/index.html` (Diagramme) / `RESULTS.md` (Tabellen). Ein
veröffentlichter Lauf wird auf GitHub Pages deployt (Settings → Pages → Source: GitHub Actions).
Die Seite ist ein kleines mehrseitiges Dashboard: eine **Compare**-Seite (Gewinner-Heatmap,
p99- und Durchsatzkurven pro Workload mit Datentabellen, Peak RSS) plus eine
**Deep-Report-Seite pro Server** für jeden Octane-Server (Swoole / OpenSwoole / RoadRunner /
FrankenPHP), mit einem **Worker-Anzahl-Umschalter**, um die gesamte Ansicht zwischen den
durchlaufenen Worker-Anzahlen zu wechseln.

Dies sind **Einzelmaschinen**-Ergebnisse. Lies sie **relativ** (welcher Server gewinnt und
bei welcher Nebenläufigkeit der Gewinner kippt), nicht als absolute Zahlen für deine Hardware.

## Was gemessen wird

**Schlagzeile: p99 / p50-Latenz über einen Nebenläufigkeits-Sweep.** Die Tail-Latenz ist der
Punkt, an dem diese Server tatsächlich auseinanderlaufen; der mittlere Durchsatz liegt oft im
Rauschen. Der Durchsatz (req/s) wird daneben ausgewiesen. **Peak RSS** (Speicher-Höchststand)
ist eine sekundäre „VPS-Sizing"-Metrik. CPU% ist absichtlich *keine* Schlagzeile — das
cgroup-CPU-Sampling ist zu verrauscht, um zitierbar zu sein.

Jede Zelle = `{server, workload, workers, concurrency, run}` und wird als eine JSON-Datei in
`results/` mit eingebettetem Manifest (gepinnte Versionen, Caps, Commit-SHA, Host, wrk-Flags)
gespeichert, sodass jeder Datenpunkt reproduzierbar ist. Zellen, die wrk-Fehler aufgezeichnet
haben (non-2xx / Timeouts), werden markiert und niemals stillschweigend mit eingerechnet.

## Fairness-Kontrollen (für jeden Server identisch gehalten)

| Kontrolle | Wert | Warum |
|---|---|---|
| Workers | **durchlaufen** (`WORKER_COUNTS`, Standard ~2/cpu und sein ×2 → `4 8` auf dem 2-cpu-Runner); FPM `max_children` abgeglichen | eine Matrix-Dimension — sieh, wie jeder Server mit Workern skaliert. Gleiche Anzahl für jeden Server (inkl. der FPM-Kontrolle) pro Durchlauf |
| CPU | **die untere Hälfte des Hosts** — `cpus=2`, `cpuset=0-1` auf dem 4-Kern-Runner (`cpus=4`, `cpuset=0-3` auf einem 8-Kern-Host) | jeder Server bekommt dieselben Kerne; die SUT-cpu-Anzahl wird in den Manifest-Caps festgehalten |
| Lastgenerator | **`wrk` auf der oberen Hälfte des Hosts** (`cpuset=2-3` auf dem Runner, `4-7` bei 8 Kernen) — disjunkt von der SUT | der Generator ist **immer isoliert**: er stiehlt der SUT nie die CPU. Pro Zelle als `generator_isolated` festgehalten |
| Memory | `mem_limit=4g` (env `MEM_LIMIT`) | großzügige **gleiche** Obergrenze — greift auf dem 16-GB-Runner nie, sodass kein Server OOM-bestraft wird und Peak RSS den echten Höchststand liest (nicht gedeckelt). Setze `MEM_LIMIT=512m` für ein Small-VPS-Szenario |
| OPcache | aktiviert, `validate_timestamps=0` | Code einmal kompiliert, so wie Octane ihn behält |
| App-env | `APP_ENV=production`, `APP_DEBUG=false` | Produktions-Code-Pfade |
| Sessions | `SESSION_DRIVER=array` | zustandslose Endpunkte — nichts serialisiert unter einem Write-Lock |
| Versionen | gepinnt: PHP 8.4, Laravel 13, Octane 2.17 (siehe Manifest) | keine beweglichen Teile |

Das Harness führt **immer nur einen App-Server gleichzeitig** aus (alle anderen gestoppt),
sodass dessen CPU/RAM isoliert gemessen werden, nicht unter Konkurrenz durch untätige
Geschwister.

**Standardumgebung: ein GitHub Actions `ubuntu-24.04`-Runner (4 vCPU / 16 GB RAM).**
`benchmark.sh` **teilt den Host in zwei Hälften**: die SUT bekommt die unteren Kerne, der
`wrk`-Generator die oberen Kerne, sodass der Generator **immer isoliert** ist (er stiehlt der
SUT nie die CPU). Auf dem 4-Kern-Runner bedeutet das, dass die **SUT 2 cpus** hat (`cpuset 0-1`)
und `wrk` auf `2-3` läuft; auf einem 8-Kern-Host bekommt die SUT 4 cpus (`0-3`) und `wrk` `4-7`.
Der Kompromiss ist, dass die SUT nur **die halbe Maschine** bekommt — auf dem Standard-Runner
gelten die Berichte also für einen **2-cpu-Server**, festgehalten in den Manifest-Caps
(`cpus=2`). Da geteilte CI-Runner immer noch lärmende Nachbarn sind, lies die Zahlen als
**ausschließlich relativ**.

## Workloads

Workloads sind in drei **Gruppen** organisiert, sodass sich die Diagramme und Tabellen als
„overhead → wohin die CPU geht → I/O" lesen. Die drei Routen der `cpu`-Gruppe belasten jeweils
einen *anderen* Instruktionspfad, sodass sie sich uneinig sein können, welcher Server gewinnt.

| Gruppe | Route | Isoliert | Hinweise |
|---|---|---|---|
| overhead | `/bench/hello` | Routing + Response-Overhead | Body fester Länge |
| cpu | `/bench/hash` | Integer / bitweise | `sha256`-Verkettung ×`BENCH_HASH_ITERATIONS` (so kalibrieren, dass es ≫ hello) |
| cpu | `/bench/mandelbrot` | Float / FPU | Escape-Time-Mandelbrot, `BENCH_MANDELBROT_DIM`²×4-Gitter, `…_MAX_ITER`-Cap, ×`…_REPEAT` (~30ms Standard) |
| cpu | `/bench/json` | Serialisierung (codec) | `json_encode`+`json_decode`-Round-Trip eines 1000-int-Arrays ×`BENCH_JSON_ITERATIONS` (codec dominiert, nicht Routing; ~20ms Standard) |
| io | `/bench/db` | eine echte Query | indizierter PK-`SELECT` gegen **MySQL 8** |

**`/bench/db`-Vorbehalt:** Server unterscheiden sich in der Verbindungsbehandlung
(Swoole-Coroutine-Pool vs RoadRunner vs FrankenPHP). Dieser Workload ist als **„das
Standard-Octane-DB-Verhalten jedes Servers"** abgegrenzt, nicht als isolierte
Raw-Query-Messung. Er ist im Diagramm entsprechend gekennzeichnet.

## Ausführen

Standardmäßig erzeugt dieses Projekt die Benchmark-Berichte auf einem GitHub-Actions-Runner.
Du kannst den Workflow dieses Repositories direkt nutzen, das Projekt forken und in deinem
eigenen Repo ausführen, oder dasselbe Harness auf einer lokalen oder entfernten Maschine
starten, die du selbst kontrollierst.

**In CI (der Standard):** löse den **Benchmark**-Workflow (`.github/workflows/benchmark.yml`)
über *Actions → Run workflow* aus. Er läuft auf `ubuntu-24.04`, erstellt den Bericht und lädt
`results/` + `docs/` als Artefakt hoch (setze die `publish`-Eingabe, um `docs/` auf GitHub
Pages zu deployen). Mit den Eingaben kannst du die Matrix skalieren.

**Lokal** — **Voraussetzungen:** Docker (Compose v2) sowie PHP 8.4 + Composer auf dem Host für
`make deps` (nur `composer install` läuft auf dem Host; alles andere läuft in Docker). Ein
`Makefile` umschließt den Workflow — `make help` listet jedes Target auf.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

Anpassbar per env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `WORKER_COUNTS`, `RUNS`, `DURATION`, `WARMUP`,
`TIMEOUT`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_DIM`, `BENCH_MANDELBROT_MAX_ITER`,
`BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`. Jedes (server, workload) wird **bei jeder
Nebenläufigkeit** vor seinen Läufen aufgewärmt, und `wrk --timeout` (Standard 15s) lässt eine
langsame, gesättigte Zelle messen, statt sie als Fehler zu zensieren.

## Wie es funktioniert

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

Der `wrk`-Container führt einen kleinen Lua-Reporter (`docker/wrk/report.lua`) aus, der eine
JSON-Zeile mit vollständigen Latenz-Perzentilen und Fehleranzahlen pro Klasse ausgibt.

## Idle-Speicher-Profiler

Ein separates Werkzeug misst, **wie viel RAM Octane pro Worker resident hält** — die
Speicherkosten dafür, das Framework warm zu halten — ohne Last:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

Der Fit trennt den **fixen** Framework-/Master-/OPcache-Overhead von den **marginalen** Kosten
eines weiteren Workers. Der naive `RSS / N`-Durchschnitt ist irreführend — er fällt mit
wachsendem N nur deshalb, weil die fixen Kosten amortisiert werden, nicht weil ein Worker
billiger geworden wäre.

## Vorbehalte

- **Einzelmaschine, relativ nicht absolut.** Deine Zahlen werden abweichen; die *Form* (wer wo
  gewinnt) ist der übertragbare Befund.
- **Pinning-Selbstcheck.** Wenn der Host `--cpuset-cpus` nicht respektiert, wird jede Zelle als
  `pinning=unverified` markiert und das Ergebnis nicht als generator-isoliert präsentiert.
- **2-cpu-SUT auf dem 4-Kern-Runner.** Um den Generator isoliert zu halten, wird der Host
  halbiert — auf dem Standard-Runner ist also jeder Server ein **2-cpu**-Server (die anderen 2
  Kerne treiben `wrk` an). Es ist im Manifest gekennzeichnet (`cpus=2`). Für eine 4-cpu-SUT *mit*
  isoliertem Generator brauchst du einen 8-Kern-Host (die Aufteilung gibt der SUT dann 4 Kerne,
  `wrk` die anderen 4).
- **`cpu`-Gruppen-Kalibrierung.** Die Standardwerte zielen auf **~20-30ms pro Request**: schwer
  genug, um `/bench/hello` zu dominieren, leicht genug, dass ein Sweep bis zu Nebenläufigkeit
  128 auf einer 4-Kern-Maschine nicht in `wrk`-Timeouts sättigt. Stelle es auf deiner Maschine
  über `BENCH_HASH_ITERATIONS` (2000), `BENCH_MANDELBROT_DIM` (32) /
  `BENCH_MANDELBROT_MAX_ITER` (256) und `BENCH_JSON_ITERATIONS` (150) ein; `…_REPEAT` skaliert
  Mandelbrot für schwerere Hosts hoch.

## Roadmap

- **Phase 2 — lebender Benchmark:** der GitHub-Actions-Workflow führt die Matrix bereits auf
  `ubuntu-24.04` aus und kann auf GitHub Pages deployen. Als Nächstes: ein `schedule:`-Trigger
  zum automatischen Neu-Ausführen bei jedem PHP-/Octane-/Server-Release. (Vorbehalt: gehostete
  Runner sind verrauscht; für eine **4-cpu**-SUT mit immer noch isoliertem Generator nutze einen
  selbstgehosteten 8-Kern+-Runner — die Aufteilung gibt der SUT dann `0-3` und `wrk` `4-7`
  automatisch.)
- **Phase 3 — Decision Engine:** „sag mir die Form meiner App → welcher Server + welche
  Worker-Anzahl."

## Aufbau

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
