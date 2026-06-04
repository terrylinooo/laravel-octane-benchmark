[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **Español** · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Un arnés reproducible que compara los servidores de aplicaciones de Laravel Octane
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) frente a un grupo de control
tradicional de **PHP-FPM + nginx**, y muestra *dónde gana cada uno*.

La mayoría de los benchmarks de Octane publican un único número del "más rápido" y se
contradicen entre sí, porque difieren silenciosamente en la carga de trabajo, el número de
workers, el generador de carga y caliente-vs-frío, y rara vez revelan algo de ello. Este
fija cada variable de confusión, las revela todas y publica **curvas de cruce de latencia
por carga de trabajo**. El veredicto es explícitamente "depende: aquí está exactamente de
qué depende. Ejecútalo tú mismo."

## Resultados

Ejecútalo y abre `docs/index.html` (gráficos) / `RESULTS.md` (tablas). Una ejecución
publicada se despliega en GitHub Pages (Settings → Pages → Source: GitHub Actions). El sitio
es un pequeño panel multipágina: una página **Compare** (mapa de calor de ganadores, curvas
de p99 + throughput por carga de trabajo con tablas de datos, RSS pico) más una página de
**informe detallado por servidor** para cada servidor Octane (Swoole / OpenSwoole /
RoadRunner / FrankenPHP), con un **interruptor de número de workers** para cambiar toda la
vista entre los conteos de workers barridos.

Estos son resultados de **una sola máquina**. Léelos como **relativos** (qué servidor gana, y
a qué concurrencia se invierte el ganador), no como números absolutos para tu hardware.

## Qué se mide

**Titular: latencia p99 / p50 a lo largo de un barrido de concurrencia.** La latencia de cola
es donde estos servidores realmente divergen; el throughput medio suele estar dentro del
ruido. El throughput (req/s) se reporta junto a ella. El **RSS pico** (marca máxima de
memoria) es una métrica secundaria de "dimensionamiento de VPS". El CPU% deliberadamente *no*
es un titular: el muestreo de CPU por cgroup es demasiado ruidoso para citarlo.

Cada celda = `{server, workload, workers, concurrency, run}` y se almacena como un archivo JSON
en `results/` con un manifest embebido (versiones fijadas, caps, commit SHA, host, flags de
wrk) para que cualquier punto de datos sea reproducible. Las celdas que registraron errores de
wrk (non-2xx / timeouts) se marcan, nunca se promedian silenciosamente.

## Controles de equidad (idénticos para cada servidor)

| Control | Valor | Por qué |
|---|---|---|
| Workers | **barrido** (`WORKER_COUNTS`, por defecto ~2/cpu y su ×2 → `4 8` en el runner de 2 cpu); `max_children` de FPM igualado | una dimensión de matriz: observa cómo escala cada servidor con los workers. Mismo conteo para cada servidor (incl. el control FPM) por pasada |
| CPU | **la mitad inferior del host** — `cpus=2`, `cpuset=0-1` en el runner de 4 núcleos (`cpus=4`, `cpuset=0-3` en un host de 8 núcleos) | cada servidor recibe los mismos núcleos; el conteo de cpu del SUT se registra en los caps del manifest |
| Generador de carga | **`wrk` en la mitad superior del host** (`cpuset=2-3` en el runner, `4-7` en 8 núcleos), disjunto del SUT | el generador está **siempre aislado**: nunca roba la CPU del SUT. Registrado por celda como `generator_isolated` |
| Memoria | `mem_limit=4g` (env `MEM_LIMIT`) | techo **igual** y generoso: nunca limita en el runner de 16 GB, por lo que ningún servidor es penalizado por OOM y el RSS pico lee la verdadera marca máxima (no recortada). Configura `MEM_LIMIT=512m` para un escenario de VPS pequeño |
| OPcache | habilitado, `validate_timestamps=0` | código compilado una sola vez, como lo mantiene Octane |
| Entorno de la app | `APP_ENV=production`, `APP_DEBUG=false` | rutas de código de producción |
| Sesiones | `SESSION_DRIVER=array` | endpoints sin estado: nada se serializa en un write lock |
| Versiones | fijadas: PHP 8.4, Laravel 13, Octane 2.17 (ver manifest) | sin piezas móviles |

El arnés ejecuta **un servidor de aplicaciones a la vez** (todos los demás detenidos) para que
su CPU/RAM se midan de forma aislada, sin contención de hermanos inactivos.

**Entorno por defecto: un runner `ubuntu-24.04` de GitHub Actions (4 vCPU / 16 GB RAM).**
`benchmark.sh` **divide el host por la mitad**: el SUT recibe los núcleos inferiores, el
generador `wrk` los núcleos superiores, de modo que el generador está **siempre aislado** (nunca
roba la CPU del SUT). En el runner de 4 núcleos eso significa que el **SUT tiene 2 cpus**
(`cpuset 0-1`) y `wrk` corre en `2-3`; en un host de 8 núcleos el SUT recibe 4 cpus (`0-3`) y
`wrk` `4-7`. La contrapartida es que el SUT solo recibe **la mitad de la máquina**, así que en
el runner por defecto los informes son para un **servidor de 2 cpu**, registrado en los caps del
manifest (`cpus=2`). Como los runners de CI compartidos siguen siendo vecinos ruidosos, lee los
números como **solo relativos**.

## Cargas de trabajo

Las cargas de trabajo se organizan en tres **grupos** para que los gráficos y tablas se lean
como "overhead → a dónde va la CPU → I/O". Las tres rutas del grupo `cpu` estresan cada una una
ruta de instrucciones *diferente*, por lo que pueden discrepar sobre qué servidor gana.

| Grupo | Ruta | Aísla | Notas |
|---|---|---|---|
| overhead | `/bench/hello` | overhead de routing + respuesta | cuerpo de longitud fija |
| cpu | `/bench/hash` | entero / bit a bit | encadenamiento `sha256` ×`BENCH_HASH_ITERATIONS` (calíbralo para que ≫ hello) |
| cpu | `/bench/mandelbrot` | flotante / FPU | Mandelbrot por tiempo de escape, malla `BENCH_MANDELBROT_DIM`²×4, tope `…_MAX_ITER`, ×`…_REPEAT` (~30ms por defecto) |
| cpu | `/bench/json` | serialización (codec) | ida y vuelta `json_encode`+`json_decode` de un array de 1000 ints ×`BENCH_JSON_ITERATIONS` (domina el codec, no el routing; ~20ms por defecto) |
| io | `/bench/db` | una consulta real | `SELECT` por PK indexada vs **MySQL 8** |

**Advertencia sobre `/bench/db`:** los servidores difieren en el manejo de conexiones (pool de
corrutinas de Swoole vs RoadRunner vs FrankenPHP). Esta carga de trabajo se delimita como **"el
comportamiento de BD por defecto de Octane de cada servidor"**, no como una medición aislada de
consulta cruda. Está etiquetada como tal en el gráfico.

## Ejecútalo

**En CI (por defecto):** dispara el workflow **Benchmark**
(`.github/workflows/benchmark.yml`) vía *Actions → Run workflow*. Corre en `ubuntu-24.04`,
construye el informe y sube `results/` + `docs/` como un artefacto (configura la entrada
`publish` para desplegar `docs/` en GitHub Pages). Las entradas te permiten escalar la matriz.

**Localmente** — **Requisitos previos:** Docker (Compose v2), y PHP 8.4 + Composer en el host
para `make deps` (solo `composer install` corre en el host; todo lo demás está en Docker). Un
`Makefile` envuelve el workflow — `make help` lista cada target.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

Ajustable mediante env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `WORKER_COUNTS`, `RUNS`, `DURATION`, `WARMUP`,
`TIMEOUT`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_DIM`, `BENCH_MANDELBROT_MAX_ITER`,
`BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`. Cada (server, workload) se calienta **en cada
concurrencia** antes de sus ejecuciones, y `wrk --timeout` (por defecto 15s) permite que una celda
lenta y saturada sea medida en lugar de censurada como errores.

## Cómo funciona

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

El contenedor `wrk` ejecuta un pequeño reporter en Lua (`docker/wrk/report.lua`) que emite una
línea JSON con los percentiles completos de latencia y el conteo de errores por clase.

## Perfilador de memoria en reposo

Una herramienta separada mide **cuánta RAM mantiene Octane residente por worker** — el costo de
memoria de mantener el framework caliente — sin carga:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

El ajuste separa el overhead **fijo** de framework/master/OPcache del costo **marginal** de un
worker adicional. El promedio ingenuo `RSS / N` es engañoso: cae a medida que N crece solo
porque el costo fijo se amortiza, no porque un worker se haya abaratado.

## Advertencias

- **Una sola máquina, relativo no absoluto.** Tus números diferirán; la *forma* (quién gana
  dónde) es el hallazgo portable.
- **Auto-verificación del pinning.** Si el host no respeta `--cpuset-cpus`, cada celda se etiqueta
  con `pinning=unverified` y el resultado no se presenta como aislado del generador.
- **SUT de 2 cpu en el runner de 4 núcleos.** Para mantener el generador aislado, el host se
  divide por la mitad, así que en el runner por defecto cada servidor es un servidor de **2 cpu**
  (los otros 2 núcleos alimentan `wrk`). Está etiquetado en el manifest (`cpus=2`). Para un SUT de
  4 cpu *con* un generador aislado necesitas un host de 8 núcleos (la división entonces da al SUT 4
  núcleos, y a `wrk` los otros 4).
- **Calibración del grupo `cpu`.** Los valores por defecto apuntan a **~20-30ms por petición**: lo
  suficientemente pesados para dominar `/bench/hello`, lo suficientemente ligeros para que un
  barrido hasta concurrencia 128 no se sature en timeouts de `wrk` en una máquina de 4 núcleos.
  Ajústalos en tu máquina vía `BENCH_HASH_ITERATIONS` (2000), `BENCH_MANDELBROT_DIM` (32) /
  `BENCH_MANDELBROT_MAX_ITER` (256), y `BENCH_JSON_ITERATIONS` (150); `…_REPEAT` escala mandelbrot
  hacia arriba para hosts más potentes.

## Hoja de ruta

- **Fase 2 — benchmark vivo:** el workflow de GitHub Actions ya ejecuta la matriz en
  `ubuntu-24.04` y puede desplegar a GitHub Pages. Siguiente: un disparador `schedule:` para
  re-ejecutar automáticamente en cada lanzamiento de PHP/Octane/servidor. (Advertencia: los runners
  alojados son ruidosos; para un SUT de **4 cpu** con el generador aún aislado, usa un runner
  autoalojado de 8+ núcleos: la división entonces da al SUT `0-3` y a `wrk` `4-7` automáticamente.)
- **Fase 3 — motor de decisión:** "dime la forma de mi app → qué servidor + número de workers."

## Estructura

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
