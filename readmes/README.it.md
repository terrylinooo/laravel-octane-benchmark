[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · **Italiano** · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Un harness riproducibile che mette alla prova gli application server di Laravel Octane (**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) contro un gruppo di controllo tradizionale **PHP-FPM + nginx** — e mostra *dove ciascuno vince*.

La maggior parte dei benchmark di Octane pubblica un singolo numero "più veloce" e si contraddicono a vicenda, perché differiscono silenziosamente su workload, numero di worker, generatore di carico e warm-vs-cold, e raramente lo dichiarano. Questo fissa ogni variabile confondente, le dichiara tutte e pubblica **curve di crossover della latenza per workload**. Il verdetto è esplicitamente "dipende — ed ecco esattamente da cosa dipende. Provalo tu stesso."

Essere il più veloce non significa automaticamente essere il migliore. Swoole/OpenSwoole, RoadRunner e FrankenPHP hanno ciascuno compromessi diversi e scenari applicativi in cui hanno più senso. Una scelta reale dipende anche dal modello operativo, dal supporto dell'ecosistema, dallo stile di deploy, dalla compatibilità delle estensioni e dalla familiarità del team. Questo progetto non prova a decidere al posto tuo; esegue solo i server in un ambiente equo e riproducibile e pubblica i dati.

## Results

Eseguilo e apri `docs/index.html` (grafici) / `RESULTS.md` (tabelle). Un'esecuzione pubblicata viene distribuita su GitHub Pages (Settings → Pages → Source: GitHub Actions). Il sito è una piccola dashboard multi-pagina: una pagina **Compare** (heatmap dei vincitori, curve di p99 + throughput per workload con tabelle dati, picco RSS) più una pagina di **deep-report per server** per ciascun server Octane (Swoole / OpenSwoole / RoadRunner /FrankenPHP), con un **toggle del numero di worker** per cambiare l'intera vista tra i conteggi di worker analizzati.

Questi sono risultati **a macchina singola**. Leggili come **relativi** (quale server vince, e a quale concorrenza il vincitore cambia), non come numeri assoluti per il tuo hardware.

## What's measured

**Titolo: latenza p99 / p50 attraverso uno sweep di concorrenza.** La latenza di coda è dove questi server divergono davvero; il throughput medio è spesso entro il rumore. Il throughput (req/s) è riportato accanto. Il **picco RSS** (massimo di memoria raggiunto) è una metrica secondaria di "dimensionamento del VPS". La CPU% deliberatamente *non* è un titolo — il campionamento CPU del cgroup è troppo rumoroso per essere citato.

Ogni cella = `{server, workload, workers, concurrency, run}` ed è memorizzata come un file JSON in `results/` con un manifest incorporato (versioni fissate, cap, commit SHA, host, flag di wrk) così che qualsiasi punto dati sia riproducibile. Le celle che hanno registrato errori di wrk (non-2xx / timeout) sono segnalate, mai mediate silenziosamente.

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| Workers | **swept** (`WORKER_COUNTS`, default ~2/cpu e il suo ×2 → `4 8` sul runner a 2 cpu); `max_children` di FPM allineato | una dimensione della matrice — guarda come ciascun server scala con i worker. Stesso conteggio per ogni server (incl. il controllo FPM) a ogni passaggio; più worker possono essere più lenti quando la CPU è già sovrascritta |
| CPU | il SUT riceve tutti i core oltre i due riservati (`cpuset 2-3` sul runner a 4 core) | ogni server riceve lo stesso budget CPU |
| Generatore + DB | `wrk` e `mysql` ricevono un core dedicato ciascuno (`0` e `1`), separati dal SUT | generatore e database non sottraggono CPU al SUT; `/bench/db` evita la contesa CPU di MySQL |
| Memory | `mem_limit=4g` (env `MEM_LIMIT`) | tetto **uguale** generoso — non vincola mai sul runner da 16 GB, così nessun server è penalizzato da OOM e il picco RSS legge il vero massimo raggiunto (non limitato). Imposta `MEM_LIMIT=512m` per uno scenario di piccolo VPS |
| OPcache | abilitato, `validate_timestamps=0` | codice compilato una volta, come Octane lo mantiene |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | percorsi di codice di produzione |
| Sessions | `SESSION_DRIVER=array` | endpoint stateless — niente si serializza su un write lock |
| Versions | fissate: PHP 8.4, Laravel 13, Octane 2.17 (vedi manifest) | nessuna parte mobile |

L'harness esegue **un application server alla volta** (tutti gli altri fermati) così che la sua CPU/RAM siano misurate in isolamento, non sotto contesa da fratelli inattivi.

**Ambiente predefinito: GitHub Actions `ubuntu-24.04` (4 vCPU / 16 GB RAM).** `wrk` usa il core `0`, `mysql` il core `1` e il SUT `cpuset 2-3`, con `cpus=2` e `mem_limit=4g`. Su un host a 8 core, `wrk` e `mysql` restano su `0` e `1`, mentre il SUT usa `cpuset 2-7`. Generatore e database sono così isolati dal SUT. I runner condivisi restano rumorosi: conta più la forma dei risultati dei numeri esatti.

## Workloads

I workload sono organizzati in tre **gruppi** così che i grafici e le tabelle si leggano come "overhead → dove va la CPU → I/O". Le tre route del gruppo `cpu` stressano ciascuna un percorso di istruzioni *diverso*, quindi possono non essere d'accordo su quale server vince.

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | routing + overhead di risposta | corpo a lunghezza fissa |
| cpu | `/bench/hash` | intero / bitwise | concatenazione `sha256` ×`BENCH_HASH_ITERATIONS` (calibra così che sia ≫ hello) |
| cpu | `/bench/mandelbrot` | float / FPU | Mandelbrot escape-time, griglia `BENCH_MANDELBROT_DIM`²×4, cap `…_MAX_ITER`, ×`…_REPEAT` (~30ms default) |
| cpu | `/bench/json` | serializzazione (codec) | round-trip `json_encode`+`json_decode` di un array di 1000 interi ×`BENCH_JSON_ITERATIONS` (domina il codec, non il routing; ~20ms default) |
| io | `/bench/db` | una query reale | `SELECT` su PK indicizzata contro **MySQL 8** |

**Avvertenza su `/bench/db`:** i server differiscono nella gestione delle connessioni (pool di coroutine di Swoole vs RoadRunner vs FrankenPHP). Questo workload è inquadrato come **"il comportamento DB Octane di default di ciascun server,"** non come una misurazione isolata della query grezza. È etichettato come tale sul grafico.

## Run it

Per impostazione predefinita, questo progetto genera i report di benchmark su un runner di GitHub Actions. Puoi usare il workflow di questo repository così com'è, fare fork ed eseguirlo nel tuo repo, oppure eseguire lo stesso harness su una macchina locale o remota che controlli direttamente.

**In CI (il default):** attiva il workflow **Benchmark** (`.github/workflows/benchmark.yml`) tramite *Actions → Run workflow*. Gira su `ubuntu-24.04`, costruisce il report e carica `results/` + `docs/` come artifact (imposta l'input `publish`per distribuire `docs/` su GitHub Pages). Gli input ti permettono di scalare la matrice.

**Localmente** — **Prerequisiti:** Docker (Compose v2), e PHP 8.4 + Composer sull'host per `make deps` (solo `composer install` gira sull'host; tutto il resto è in Docker). Un `Makefile` avvolge il workflow — `make help` elenca ogni target.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

Regolabile tramite env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `WORKER_COUNTS`, `RUNS`, `DURATION`, `WARMUP`,`TIMEOUT`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_DIM`, `BENCH_MANDELBROT_MAX_ITER`,`BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`. Ogni (server, workload) viene riscaldato **a ogni concorrenza** prima delle sue esecuzioni, e `wrk --timeout` (default 15s) permette di misurare una cella lenta e satura invece di censurarla come errori.

Per impostazione predefinita, `benchmark.sh` testa circa `2 * SUT_CPUS` worker e poi il doppio. Sul runner predefinito a 4 vCPU il SUT riceve 2 CPU, quindi lo sweep predefinito dei worker è`4 8`. Se 8 worker mostrano throughput più basso o p99 peggiore rispetto a 4, è un risultato valido: di solito significa che i worker PHP extra aggiungono contesa dello scheduler, pressione sulla cache o contesa DB/socket senza aggiungere capacità CPU utile.

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

Il container `wrk` esegue un piccolo reporter Lua (`docker/wrk/report.lua`) che emette una riga JSON con i percentili di latenza completi e i conteggi di errore per classe.

## Idle memory profiler

Uno strumento separato misura **quanta RAM Octane mantiene residente per worker** — il costo di memoria per tenere il framework caldo — senza carico:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

Il fit separa l'overhead **fisso** di framework/master/OPcache dal costo **marginale** di un worker in più. La media ingenua `RSS / N` è fuorviante — cala con la crescita di N solo perché il costo fisso viene ammortizzato, non perché un worker sia diventato più economico.

## Caveats

- **Macchina singola, relativo non assoluto.** I tuoi numeri saranno diversi; la *forma* (chi vince dove) è il risultato portabile.
- **Self-check del pinning.** Se l'host non onora `--cpuset-cpus`, ogni cella viene etichettata `pinning=unverified` e il risultato non viene presentato come isolato dal generatore.
- **SUT a 2 cpu / 4 GB sul runner a 4 core.** Gli altri due core sono riservati separatamente a `wrk` e `mysql`, così non competono con il SUT.
- **Più worker non sono automaticamente meglio.** Un calo da 4 a 8 worker va letto come il punto di saturazione locale trovato dal benchmark, specialmente nei workload CPU-bound o con la divisione SUT predefinita a 2 CPU.
- **Calibrazione del gruppo `cpu`.** I default puntano a **~20-30ms per richiesta**: abbastanza pesanti da dominare `/bench/hello`, abbastanza leggeri che uno sweep fino a concorrenza 128 non saturi in timeout di `wrk` su una macchina a 4 core. Regola sulla tua macchina tramite `BENCH_HASH_ITERATIONS` (2000), `BENCH_MANDELBROT_DIM` (32) / `BENCH_MANDELBROT_MAX_ITER`(256), e `BENCH_JSON_ITERATIONS` (150); `…_REPEAT` scala mandelbrot verso l'alto per host più pesanti.

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

## Riepilogo del benchmark

Report pubblicato: [Dashboard UI](https://terrylinooo.github.io/laravel-octane-benchmark) · [Dati dei risultati](https://terrylinooo.github.io/laravel-octane-benchmark/summary.json)

Il benchmark è stato eseguito su una singola macchina controllata. Il container Docker del SUT era limitato a `2 CPU / 4 GB RAM`, mentre `wrk` e `mysql` usavano core separati. I dati sono un confronto relativo con gli stessi limiti, non una classifica universale per la produzione.

- Latenza p99 più stabile: FrankenPHP
- Throughput di picco più alto in alcuni workload: Swoole / OpenSwoole
- Minore uso di memoria: PHP-FPM + nginx
- Efficienza più debole in questa configurazione: RoadRunner
- Con il limite di `2 CPU`, in genere 4 workers sono migliori di 8

FrankenPHP offre il miglior equilibrio tra stabilità della latenza, throughput competitivo e uso moderato della memoria. Non si dovrebbe scegliere un server Octane basandosi solo sul massimo numero di requests per second.

## License

Questo benchmark Laravel Octane è rilasciato sotto MIT License ed è mantenuto da [Terry L.](https://terryl.in). Terry L. è anche lo sviluppatore di Airygen, un [WordPress SEO Plugin](https://www.airygen.com/en) gratuito e potente per team che hanno bisogno di workflow di contenuto strutturati e strumenti di pubblicazione orientati alla ricerca.

## Discussione aperta

I servizi di container serverless, come Google Cloud Run, possono comportarsi diversamente dal container fisso a 2 CPU usato in questo benchmark. Poiché questi servizi in genere fatturano il compute allocato e possono girare su host con molti CPU cores sottostanti, un numero maggiore di worker può teoricamente consumare il compute disponibile fino a raggiungere il limite configurato del servizio. In questo ambiente, la regola pratica `workers = CPU x 2` potrebbe non essere il default corretto; il worker count va calibrato sulla reale allocazione CPU della piattaforma, sul concurrency model, sul comportamento di fatturazione e sul latency target.
