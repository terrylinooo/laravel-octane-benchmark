[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · **Italiano** · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Un harness riproducibile che mette alla prova gli application server di Laravel Octane
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) contro un gruppo di controllo
tradizionale **PHP-FPM + nginx** — e mostra *dove ciascuno vince*.

La maggior parte dei benchmark di Octane pubblica un singolo numero "più veloce" e si
contraddicono a vicenda, perché differiscono silenziosamente su workload, numero di worker,
generatore di carico e warm-vs-cold, e raramente lo dichiarano. Questo fissa ogni variabile
confondente, le dichiara tutte e pubblica **curve di crossover della latenza per workload**.
Il verdetto è esplicitamente "dipende — ed ecco esattamente da cosa dipende. Provalo tu stesso."

## Results

Eseguilo e apri `docs/index.html` (grafici) / `RESULTS.md` (tabelle). Un'esecuzione
pubblicata viene distribuita su GitHub Pages (Settings → Pages → Source: GitHub Actions).
Il sito è una piccola dashboard multi-pagina: una pagina **Compare** (heatmap dei vincitori,
curve di p99 + throughput per workload con tabelle dati, picco RSS) più una pagina di
**deep-report per server** per ciascun server Octane (Swoole / OpenSwoole / RoadRunner /
FrankenPHP), con un **toggle del numero di worker** per cambiare l'intera vista tra i conteggi
di worker analizzati.

Questi sono risultati **a macchina singola**. Leggili come **relativi** (quale server vince,
e a quale concorrenza il vincitore cambia), non come numeri assoluti per il tuo hardware.

## What's measured

**Titolo: latenza p99 / p50 attraverso uno sweep di concorrenza.** La latenza di coda è
dove questi server divergono davvero; il throughput medio è spesso entro il rumore. Il
throughput (req/s) è riportato accanto. Il **picco RSS** (massimo di memoria raggiunto) è
una metrica secondaria di "dimensionamento del VPS". La CPU% deliberatamente *non* è un
titolo — il campionamento CPU del cgroup è troppo rumoroso per essere citato.

Ogni cella = `{server, workload, workers, concurrency, run}` ed è memorizzata come un file
JSON in `results/` con un manifest incorporato (versioni fissate, cap, commit SHA, host, flag
di wrk) così che qualsiasi punto dati sia riproducibile. Le celle che hanno registrato errori
di wrk (non-2xx / timeout) sono segnalate, mai mediate silenziosamente.

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| Workers | **swept** (`WORKER_COUNTS`, default ~2/cpu e il suo ×2 → `4 8` sul runner a 2 cpu); `max_children` di FPM allineato | una dimensione della matrice — guarda come ciascun server scala con i worker. Stesso conteggio per ogni server (incl. il controllo FPM) a ogni passaggio |
| CPU | **la metà inferiore dell'host** — `cpus=2`, `cpuset=0-1` sul runner a 4 core (`cpus=4`, `cpuset=0-3` su un host a 8 core) | ogni server riceve gli stessi core; il numero di cpu del SUT è registrato nei cap del manifest |
| Load generator | **`wrk` sulla metà superiore dell'host** (`cpuset=2-3` sul runner, `4-7` su 8 core) — disgiunto dal SUT | il generatore è **sempre isolato**: non ruba mai la CPU del SUT. Registrato per cella come `generator_isolated` |
| Memory | `mem_limit=4g` (env `MEM_LIMIT`) | tetto **uguale** generoso — non vincola mai sul runner da 16 GB, così nessun server è penalizzato da OOM e il picco RSS legge il vero massimo raggiunto (non limitato). Imposta `MEM_LIMIT=512m` per uno scenario di piccolo VPS |
| OPcache | abilitato, `validate_timestamps=0` | codice compilato una volta, come Octane lo mantiene |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | percorsi di codice di produzione |
| Sessions | `SESSION_DRIVER=array` | endpoint stateless — niente si serializza su un write lock |
| Versions | fissate: PHP 8.4, Laravel 13, Octane 2.17 (vedi manifest) | nessuna parte mobile |

L'harness esegue **un application server alla volta** (tutti gli altri fermati) così che la
sua CPU/RAM siano misurate in isolamento, non sotto contesa da fratelli inattivi.

**Ambiente di default: un runner `ubuntu-24.04` di GitHub Actions (4 vCPU / 16 GB RAM).**
`benchmark.sh` **divide l'host a metà**: il SUT riceve i core inferiori, il generatore `wrk`
i core superiori, così che il generatore sia **sempre isolato** (non ruba mai la CPU del SUT).
Sul runner a 4 core questo significa che il **SUT è a 2 cpu** (`cpuset 0-1`) e `wrk` gira su
`2-3`; su un host a 8 core il SUT riceve 4 cpu (`0-3`) e `wrk` `4-7`. Il compromesso è che il
SUT riceve solo **metà della macchina** — quindi sul runner di default i report sono per un
**server a 2 cpu**, registrato nei cap del manifest (`cpus=2`). Poiché i runner CI condivisi
sono comunque vicini rumorosi, leggi i numeri come **solo relativi**.

## Workloads

I workload sono organizzati in tre **gruppi** così che i grafici e le tabelle si leggano come
"overhead → dove va la CPU → I/O". Le tre route del gruppo `cpu` stressano ciascuna un percorso
di istruzioni *diverso*, quindi possono non essere d'accordo su quale server vince.

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | routing + overhead di risposta | corpo a lunghezza fissa |
| cpu | `/bench/hash` | intero / bitwise | concatenazione `sha256` ×`BENCH_HASH_ITERATIONS` (calibra così che sia ≫ hello) |
| cpu | `/bench/mandelbrot` | float / FPU | Mandelbrot escape-time, griglia `BENCH_MANDELBROT_DIM`²×4, cap `…_MAX_ITER`, ×`…_REPEAT` (~30ms default) |
| cpu | `/bench/json` | serializzazione (codec) | round-trip `json_encode`+`json_decode` di un array di 1000 interi ×`BENCH_JSON_ITERATIONS` (domina il codec, non il routing; ~20ms default) |
| io | `/bench/db` | una query reale | `SELECT` su PK indicizzata contro **MySQL 8** |

**Avvertenza su `/bench/db`:** i server differiscono nella gestione delle connessioni (pool di
coroutine di Swoole vs RoadRunner vs FrankenPHP). Questo workload è inquadrato come **"il
comportamento DB Octane di default di ciascun server,"** non come una misurazione isolata della
query grezza. È etichettato come tale sul grafico.

## Run it

**In CI (il default):** attiva il workflow **Benchmark**
(`.github/workflows/benchmark.yml`) tramite *Actions → Run workflow*. Gira su `ubuntu-24.04`,
costruisce il report e carica `results/` + `docs/` come artifact (imposta l'input `publish`
per distribuire `docs/` su GitHub Pages). Gli input ti permettono di scalare la matrice.

**Localmente** — **Prerequisiti:** Docker (Compose v2), e PHP 8.4 + Composer sull'host per
`make deps` (solo `composer install` gira sull'host; tutto il resto è in Docker).
Un `Makefile` avvolge il workflow — `make help` elenca ogni target.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

Regolabile tramite env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `WORKER_COUNTS`, `RUNS`, `DURATION`, `WARMUP`,
`TIMEOUT`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_DIM`, `BENCH_MANDELBROT_MAX_ITER`,
`BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`. Ogni (server, workload) viene riscaldato
**a ogni concorrenza** prima delle sue esecuzioni, e `wrk --timeout` (default 15s) permette di
misurare una cella lenta e satura invece di censurarla come errori.

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

Il container `wrk` esegue un piccolo reporter Lua (`docker/wrk/report.lua`) che emette una
riga JSON con i percentili di latenza completi e i conteggi di errore per classe.

## Idle memory profiler

Uno strumento separato misura **quanta RAM Octane mantiene residente per worker** — il costo
di memoria per tenere il framework caldo — senza carico:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

Il fit separa l'overhead **fisso** di framework/master/OPcache dal costo **marginale** di un
worker in più. La media ingenua `RSS / N` è fuorviante — cala con la crescita di N solo
perché il costo fisso viene ammortizzato, non perché un worker sia diventato più economico.

## Caveats

- **Macchina singola, relativo non assoluto.** I tuoi numeri saranno diversi; la *forma* (chi
  vince dove) è il risultato portabile.
- **Self-check del pinning.** Se l'host non onora `--cpuset-cpus`, ogni cella viene etichettata
  `pinning=unverified` e il risultato non viene presentato come isolato dal generatore.
- **SUT a 2 cpu sul runner a 4 core.** Per tenere il generatore isolato, l'host viene diviso a
  metà — quindi sul runner di default ogni server è un server a **2 cpu** (gli altri 2 core
  pilotano `wrk`). È etichettato nel manifest (`cpus=2`). Per un SUT a 4 cpu *con* un generatore
  isolato serve un host a 8 core (la divisione dà allora al SUT 4 core e a `wrk` gli altri 4).
- **Calibrazione del gruppo `cpu`.** I default puntano a **~20-30ms per richiesta**: abbastanza
  pesanti da dominare `/bench/hello`, abbastanza leggeri che uno sweep fino a concorrenza 128
  non saturi in timeout di `wrk` su una macchina a 4 core. Regola sulla tua macchina tramite
  `BENCH_HASH_ITERATIONS` (2000), `BENCH_MANDELBROT_DIM` (32) / `BENCH_MANDELBROT_MAX_ITER`
  (256), e `BENCH_JSON_ITERATIONS` (150); `…_REPEAT` scala mandelbrot verso l'alto per host più
  pesanti.

## Roadmap

- **Fase 2 — benchmark vivente:** il workflow di GitHub Actions esegue già la matrice su
  `ubuntu-24.04` e può distribuire su GitHub Pages. Prossimo: un trigger `schedule:` per
  ri-eseguire automaticamente a ogni release di PHP/Octane/server. (Avvertenza: i runner ospitati
  sono rumorosi; per un SUT a **4 cpu** con il generatore ancora isolato, usa un runner
  self-hosted a 8+ core — la divisione dà allora al SUT `0-3` e a `wrk` `4-7` automaticamente.)
- **Fase 3 — motore decisionale:** "dimmi la forma della mia app → quale server + numero di
  worker."

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
