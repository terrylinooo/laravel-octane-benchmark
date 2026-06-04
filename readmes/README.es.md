[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **Español** · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Benchmark de Laravel Octane

Un entorno reproducible que compara los servidores de aplicaciones de Laravel Octane
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) frente a un grupo de control
tradicional con **PHP-FPM + nginx**, y muestra *dónde gana cada uno*.

La mayoría de los benchmarks de Octane publican un único número del "más rápido" y se
contradicen entre sí, porque difieren silenciosamente en la carga de trabajo, el número de
workers, el generador de carga y el estado caliente vs. frío, y rara vez revelan algo de
ello. Este fija todas las variables de confusión, las revela todas y publica **curvas de
cruce de latencia por carga de trabajo**. El veredicto es explícitamente "depende: y aquí
está exactamente de qué depende. Ejecútalo tú mismo".

> La metodología es el producto. Si no puedes reproducir un número a partir de su
> manifiesto, es un bug.

## Resultados

Ejecútalo y abre `docs/index.html` (gráficas) / `RESULTS.md` (tablas). Una ejecución
publicada vive en la rama `gh-pages`.

Estos son resultados de **una sola máquina**. Léelos como **relativos** (qué servidor gana,
y a qué concurrencia cambia el ganador), no como números absolutos para tu hardware.

## Qué se mide

**Titular: latencia p99 / p50 a lo largo de un barrido de concurrencia.** La latencia de
cola es donde estos servidores realmente divergen; el throughput medio suele estar dentro
del ruido. El throughput (req/s) se reporta en paralelo. El **pico de RSS** (marca máxima de
uso de memoria) es una métrica secundaria de "dimensionamiento de VPS". El % de CPU
deliberadamente *no* es un titular: el muestreo de CPU por cgroup es demasiado ruidoso para
citarlo.

Cada celda = `{server, workload, concurrency, run}` y se almacena como un archivo JSON en
`results/` con un manifiesto embebido (versiones fijadas, límites, commit SHA, host, flags de
wrk) para que cualquier punto de datos sea reproducible. Las celdas que registraron errores
de wrk (no-2xx / timeouts) se marcan, nunca se promedian silenciosamente.

## Controles de equidad (mantenidos idénticos para cada servidor)

| Control | Valor | Por qué |
|---|---|---|
| Workers | **8** en todas partes (FPM `pm=static, max_children=8`) | mismo presupuesto; ~2 workers/CPU × 4 núcleos de Octane |
| CPU | **`cpus=4`, `cpuset=0-3`** por contenedor de app | cada servidor recibe los mismos 4 núcleos físicos |
| Generador de carga | **`wrk` fijado mediante `${WRK_CPUSET}`** — `4-7` en un host de 8+ núcleos (aislado), `0-3` en el runner por defecto de 4 núcleos (co-residente) | aísla el generador cuando existen núcleos para él; revelado por celda como `generator_isolated` |
| Memoria | `mem_limit=512m` | mismo techo |
| OPcache | habilitado, `validate_timestamps=0` | código compilado una vez, como lo mantiene Octane |
| Entorno de la app | `APP_ENV=production`, `APP_DEBUG=false` | rutas de código de producción |
| Sesiones | `SESSION_DRIVER=array` | endpoints sin estado: nada se serializa sobre un bloqueo de escritura |
| Versiones | fijadas: PHP 8.4, Laravel 13, Octane 2.17 (ver manifiesto) | sin piezas móviles |

El entorno ejecuta **un servidor de aplicaciones a la vez** (todos los demás detenidos) para
que su CPU/RAM se midan de forma aislada, no bajo la contención de hermanos inactivos.

**Entorno por defecto: un runner `ubuntu-24.04` de GitHub Actions (4 vCPU / 16 GB de RAM).**
`benchmark.sh` se adapta al número de núcleos: el SUT siempre recibe `cpuset 0-3`, y el
generador `wrk` se aísla en los núcleos `4-7` **solo cuando el host tiene ≥ 8 núcleos**. En el
runner de 4 núcleos no existen los núcleos `4-7`, por lo que el generador comparte `0-3` con
el SUT: cada celda registra `generator_isolated: false`. Como los runners de CI también son
vecinos ruidosos, lee esas ejecuciones como **solo-relativas**. Para números con generador
aislado, ejecútalo en una máquina de 8+ núcleos (el entorno elige `WRK_CPUSET=4-7`
automáticamente, o configúralo tú mismo).

## Cargas de trabajo

Las cargas de trabajo se organizan en tres **grupos** para que las gráficas y tablas se lean
como "overhead → a dónde va la CPU → I/O". Las tres rutas del grupo `cpu` someten a estrés
cada una un *camino de instrucciones* distinto, por lo que pueden discrepar sobre qué
servidor gana.

| Grupo | Ruta | Aísla | Notas |
|---|---|---|---|
| overhead | `/bench/hello` | enrutamiento + overhead de respuesta | cuerpo de longitud fija |
| cpu | `/bench/hash` | entero / a nivel de bits | encadenamiento de `sha256` ×`BENCH_HASH_ITERATIONS` (calíbralo para que sea ≫ hello) |
| cpu | `/bench/mandelbrot` | flotante / FPU | Mandelbrot por tiempo de escape, malla de 78×78 ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | serialización (códec) | ida y vuelta de `json_encode`+`json_decode` de un arreglo de 1000 enteros ×`BENCH_JSON_ITERATIONS` (domina el códec, no el enrutamiento) |
| io | `/bench/db` | una consulta real | `SELECT` por PK indexada contra **MySQL 8** |

**Advertencia sobre `/bench/db`:** los servidores difieren en el manejo de conexiones (pool
de corrutinas de Swoole vs. RoadRunner vs. FrankenPHP). Esta carga de trabajo se delimita
como **"el comportamiento de BD por defecto de Octane de cada servidor"**, no como una
medición aislada de consulta en bruto. Está etiquetada como tal en la gráfica.

## Ejecútalo

**En CI (lo predeterminado):** dispara el workflow **Benchmark**
(`.github/workflows/benchmark.yml`) vía *Actions → Run workflow*. Se ejecuta en
`ubuntu-24.04`, construye el reporte y sube `results/` + `docs/` como un artefacto
(opcionalmente publicando `docs/` en `gh-pages`). Las entradas te permiten escalar la matriz.

**Localmente** — **Requisito previo:** Docker (Compose v2).

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

Ajustable mediante variables de entorno: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `RUNS`,
`DURATION`, `WARMUP`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_REPEAT`,
`BENCH_JSON_ITERATIONS`.

## Cómo funciona

```
benchmark.sh ── per (server, workload):
  stop all app servers → start this one (+ mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → warm (discarded) → sweep concurrency × runs via the pinned wrk container
  → write results/{server}_{workload}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup memory high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Chart.js)
```

El contenedor de `wrk` ejecuta un pequeño reportador en Lua (`docker/wrk/report.lua`) que
emite una línea JSON con los percentiles completos de latencia y el conteo de errores por
clase.

## Advertencias

- **Una sola máquina, relativo no absoluto.** Tus números diferirán; la *forma* (quién gana
  dónde) es el hallazgo portable.
- **Auto-verificación del fijado (pinning).** Si el host no respeta `--cpuset-cpus`, cada
  celda se etiqueta con `pinning=unverified` y el resultado no se presenta como aislado del
  generador.
- **Co-residencia del generador en 4 núcleos.** En el runner por defecto `ubuntu-24.04` el
  generador de carga comparte los núcleos del SUT (`generator_isolated: false`). La
  comparación sigue siendo justa —cada servidor se mide bajo el *mismo* generador
  co-residente—, pero la latencia absoluta queda inflada frente a una ejecución aislada de 8
  núcleos. De todos modos es una medición relativa.
- **Calibración del grupo `cpu`.** `BENCH_HASH_ITERATIONS` (por defecto 2000),
  `BENCH_MANDELBROT_REPEAT` (1) y `BENCH_JSON_ITERATIONS` (1000) deben ajustarse en tu
  máquina para que la latencia de cada ruta del grupo `cpu` domine claramente sobre
  `/bench/hello`.

## Hoja de ruta

- **Fase 2 — benchmark vivo:** el workflow de GitHub Actions ya ejecuta la matriz en
  `ubuntu-24.04` y puede publicar en `gh-pages`. Siguiente: un disparador `schedule:` para
  re-ejecutar automáticamente en cada lanzamiento de PHP/Octane/servidor. (Advertencia: los
  runners alojados son ruidosos; para números absolutos aislados usa un runner autoalojado de
  8+ núcleos: el entorno fijará entonces `wrk` a `4-7` automáticamente.)
- **Fase 3 — motor de decisión:** "dime la forma de mi app → qué servidor + número de
  workers".

## Estructura

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
