[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · **Italiano** · [Français](README.fr.md) · [Português](README.pt.md)

---

# Benchmark di Laravel Octane

Un'infrastruttura riproducibile che mette alla prova gli application server di Laravel Octane
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) rispetto a un tradizionale
gruppo di controllo **PHP-FPM + nginx** — e mostra *dove ciascuno vince*.

La maggior parte dei benchmark di Octane pubblica un unico numero "il più veloce" e si
contraddicono a vicenda, perché differiscono silenziosamente su workload, numero di worker,
generatore di carico e warm-vs-cold, e raramente ne rivelano alcunché. Questo qui fissa ogni
variabile confondente, le rivela tutte e pubblica **curve di crossover della latenza per
workload**. Il verdetto è esplicitamente "dipende — ecco esattamente da cosa dipende.
Provalo tu stesso."

> La metodologia è il prodotto. Se non riesci a riprodurre un numero a partire dal suo
> manifest, è un bug.

## Risultati

Eseguilo e apri `docs/index.html` (grafici) / `RESULTS.md` (tabelle). Un'esecuzione
pubblicata risiede sul branch `gh-pages`.

Questi sono risultati su **singola macchina**. Leggili come **relativi** (quale server vince
e a quale concorrenza il vincitore cambia), non come numeri assoluti per il tuo hardware.

## Cosa viene misurato

**In primo piano: latenza p99 / p50 lungo una scansione di concorrenza.** La latenza di coda
è dove questi server divergono davvero; il throughput medio rientra spesso nel rumore. Il
throughput (req/s) è riportato a fianco. Il **picco di RSS** (massimo storico di memoria) è
una metrica secondaria di "dimensionamento VPS". La CPU% deliberatamente *non* è in primo
piano — il campionamento CPU dei cgroup è troppo rumoroso per essere citato.

Ogni cella = `{server, workload, concurrency, run}` ed è memorizzata come un singolo file JSON
in `results/` con un manifest incorporato (versioni fissate, cap, commit SHA, host, flag di
wrk) così che qualsiasi punto dati sia riproducibile. Le celle che hanno registrato errori di
wrk (non-2xx / timeout) sono contrassegnate, mai mediate silenziosamente.

## Controlli di equità (mantenuti identici per ogni server)

| Controllo | Valore | Perché |
|---|---|---|
| Worker | **8** ovunque (FPM `pm=static, max_children=8`) | stesso budget; ~2 worker/CPU × 4 core di Octane |
| CPU | **`cpus=4`, `cpuset=0-3`** per container applicativo | ogni server ottiene gli stessi 4 core fisici |
| Generatore di carico | **`wrk` fissato tramite `${WRK_CPUSET}`** — `4-7` su un host a 8+ core (isolato), `0-3` sul runner predefinito a 4 core (co-residente) | isola il generatore quando ci sono core per esso; rivelato per cella come `generator_isolated` |
| Memoria | `mem_limit=512m` | stesso tetto massimo |
| OPcache | abilitato, `validate_timestamps=0` | codice compilato una volta, come fa Octane |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | percorsi di codice di produzione |
| Sessioni | `SESSION_DRIVER=array` | endpoint stateless — nulla serializza su un lock di scrittura |
| Versioni | fissate: PHP 8.4, Laravel 13, Octane 2.17 (vedi manifest) | nessuna parte mobile |

L'infrastruttura esegue **un application server alla volta** (tutti gli altri fermati) così
che CPU/RAM siano misurati in isolamento, non in contesa con fratelli inattivi.

**Ambiente predefinito: un runner GitHub Actions `ubuntu-24.04` (4 vCPU / 16 GB RAM).**
`benchmark.sh` si adatta al numero di core: il SUT ottiene sempre `cpuset 0-3`, e il
generatore `wrk` è isolato sui core `4-7` **solo quando l'host ha ≥ 8 core**. Sul runner a
4 core non ci sono i core `4-7`, quindi il generatore condivide `0-3` con il SUT — ogni cella
registra `generator_isolated: false`. Poiché i runner CI sono anche vicini rumorosi, leggi
quelle esecuzioni come **solo-relative**. Per numeri con generatore isolato, esegui su una
macchina a 8+ core (l'infrastruttura sceglie automaticamente `WRK_CPUSET=4-7`, o impostalo
tu stesso).

## Workload

I workload sono organizzati in tre **gruppi** così che grafici e tabelle si leggano come
"overhead → dove va la CPU → I/O". Le tre route del gruppo `cpu` sollecitano ciascuna un
percorso di istruzioni *diverso*, quindi possono divergere su quale server vince.

| Gruppo | Route | Isola | Note |
|---|---|---|---|
| overhead | `/bench/hello` | routing + overhead di risposta | corpo a lunghezza fissa |
| cpu | `/bench/hash` | intero / bitwise | concatenamento `sha256` ×`BENCH_HASH_ITERATIONS` (calibra affinché sia ≫ hello) |
| cpu | `/bench/mandelbrot` | float / FPU | Mandelbrot a escape-time, griglia 78×78 ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | serializzazione (codec) | round-trip `json_encode`+`json_decode` di un array di 1000 int ×`BENCH_JSON_ITERATIONS` (domina il codec, non il routing) |
| io | `/bench/db` | una query reale | `SELECT` su PK indicizzata vs **MySQL 8** |

**Avvertenza su `/bench/db`:** i server differiscono nella gestione delle connessioni (pool
di coroutine di Swoole vs RoadRunner vs FrankenPHP). Questo workload ha come ambito **"il
comportamento DB di Octane predefinito di ciascun server"**, non una misurazione isolata della
query grezza. È etichettato come tale nel grafico.

## Eseguirlo

**In CI (l'impostazione predefinita):** avvia il workflow **Benchmark**
(`.github/workflows/benchmark.yml`) tramite *Actions → Run workflow*. Esegue su
`ubuntu-24.04`, costruisce il report e carica `results/` + `docs/` come artefatto
(pubblicando facoltativamente `docs/` su `gh-pages`). Gli input ti permettono di scalare la
matrice.

**In locale** — **Prerequisito:** Docker (Compose v2).

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

Regolabile tramite env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `RUNS`, `DURATION`, `WARMUP`,
`BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`.

## Come funziona

```
benchmark.sh ── per (server, workload):
  stop all app servers → start this one (+ mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → warm (discarded) → sweep concurrency × runs via the pinned wrk container
  → write results/{server}_{workload}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup memory high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Chart.js)
```

Il container `wrk` esegue un piccolo reporter Lua (`docker/wrk/report.lua`) che emette una
riga JSON con i percentili completi di latenza e i conteggi di errore per classe.

## Avvertenze

- **Singola macchina, relativi non assoluti.** I tuoi numeri saranno diversi; la *forma* (chi
  vince dove) è il risultato portabile.
- **Auto-verifica del pinning.** Se l'host non rispetta `--cpuset-cpus`, ogni cella viene
  contrassegnata `pinning=unverified` e il risultato non è presentato come isolato dal
  generatore.
- **Co-residenza del generatore su 4 core.** Sul runner predefinito `ubuntu-24.04` il
  generatore di carico condivide i core del SUT (`generator_isolated: false`). Il confronto
  rimane equo — ogni server è misurato sotto lo *stesso* generatore co-residente — ma la
  latenza assoluta è gonfiata rispetto a un'esecuzione isolata a 8 core. È comunque una
  misurazione relativa.
- **Calibrazione del gruppo `cpu`.** `BENCH_HASH_ITERATIONS` (default 2000),
  `BENCH_MANDELBROT_REPEAT` (1) e `BENCH_JSON_ITERATIONS` (1000) dovrebbero essere regolati
  sulla tua macchina così che la latenza di ciascuna route del gruppo `cpu` domini chiaramente
  `/bench/hello`.

## Roadmap

- **Fase 2 — benchmark vivente:** il workflow GitHub Actions esegue già la matrice su
  `ubuntu-24.04` e può pubblicare su `gh-pages`. Prossimo passo: un trigger `schedule:` per
  rieseguire automaticamente a ogni release di PHP/Octane/server. (Avvertenza: i runner
  ospitati sono rumorosi; per numeri assoluti isolati usa un runner self-hosted a 8+ core —
  l'infrastruttura fisserà allora `wrk` su `4-7` automaticamente.)
- **Fase 3 — motore decisionale:** "dimmi la forma della mia app → quale server + numero di
  worker."

## Struttura

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
