[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · **Русский** · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Воспроизводимый стенд, который сравнивает серверы приложений Laravel Octane
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) с традиционной
контрольной группой **PHP-FPM + nginx** — и показывает, *где побеждает каждый из них*.

Большинство бенчмарков Octane публикуют единственную «самую быструю» цифру и противоречат
друг другу, потому что незаметно расходятся в нагрузке, числе воркеров, генераторе нагрузки
и режиме «прогретый против холодного» и редко хоть что-то из этого раскрывают. Этот стенд
фиксирует каждую сбивающую переменную, раскрывает их все и публикует **кривые пересечения
задержек по каждой нагрузке**. Вердикт прямо звучит как «зависит от условий — и вот ровно
от чего. Запустите сами».

Самый быстрый вариант не обязательно является лучшим. У Swoole/OpenSwoole, RoadRunner и
FrankenPHP разные сильные стороны, ограничения и подходящие сценарии применения. Реальный
выбор зависит также от операционной модели, поддержки экосистемы, способа деплоя,
совместимости расширений и опыта команды. Этот проект не пытается принять такое решение;
он только запускает серверы в честной, воспроизводимой среде и публикует данные.

## Результаты

Запустите стенд и откройте `docs/index.html` (графики) / `RESULTS.md` (таблицы).
Опубликованный прогон разворачивается на GitHub Pages (Settings → Pages → Source: GitHub
Actions). Сайт — это небольшая многостраничная панель: страница **Compare** (тепловая карта
победителей, кривые p99 + пропускной способности по каждой нагрузке с таблицами данных,
пиковый RSS) плюс страница **детального отчёта по серверу** для каждого сервера Octane
(Swoole / OpenSwoole / RoadRunner / FrankenPHP) с **переключателем числа воркеров**, который
меняет весь вид между перебранными значениями числа воркеров.

Это результаты на **одной машине**. Читайте их как **относительные** (какой сервер
побеждает и при какой конкурентности победитель меняется), а не как абсолютные числа
для вашего железа.

## Что измеряется

**Главное: задержка p99 / p50 на свипе по конкурентности.** Именно на хвостовой задержке
эти серверы реально расходятся; средняя пропускная способность часто укладывается в шум.
Пропускная способность (req/s) приводится рядом. **Пиковый RSS** (максимальный уровень
потребления памяти) — это вторичная метрика «подбора размера VPS». CPU% намеренно *не*
выносится в заголовок — выборка CPU из cgroup слишком шумная, чтобы на неё ссылаться.

Каждая ячейка = `{server, workload, workers, concurrency, run}` и хранится как один
JSON-файл в `results/` со встроенным манифестом (зафиксированные версии, лимиты, commit
SHA, хост, флаги wrk), так что любая точка данных воспроизводима. Ячейки, в которых wrk
зафиксировал ошибки (не-2xx / таймауты), помечаются, а не молча усредняются.

## Контроль честности (одинаков для каждого сервера)

| Контроль | Значение | Почему |
|---|---|---|
| Workers | **перебираются** (`WORKER_COUNTS`, по умолчанию ~2/cpu и его ×2 → `4 8` на 2-cpu раннере); FPM `max_children` сопоставлен | измерение матрицы — смотрите, как каждый сервер масштабируется по воркерам. Одинаковое число для каждого сервера (включая контрольный FPM) на каждом проходе |
| CPU | **нижняя половина хоста** — `cpus=2`, `cpuset=0-1` на 4-ядерном раннере (`cpus=4`, `cpuset=0-3` на 8-ядерном хосте) | каждый сервер получает одни и те же ядра; число cpu у SUT записано в лимитах манифеста |
| Load generator | **`wrk` на верхней половине хоста** (`cpuset=2-3` на раннере, `4-7` на 8 ядрах) — отдельно от SUT | генератор **всегда изолирован**: он никогда не отбирает CPU у SUT. Записывается по каждой ячейке как `generator_isolated` |
| Memory | `mem_limit=4g` (env `MEM_LIMIT`) | щедрый **равный** потолок — никогда не упирается на 16 ГБ раннере, поэтому ни один сервер не штрафуется за OOM, а пиковый RSS показывает истинный максимум (не зажатый). Задайте `MEM_LIMIT=512m` для сценария маленького VPS |
| OPcache | включён, `validate_timestamps=0` | код компилируется один раз, как его держит Octane |
| App env | `APP_ENV=production`, `APP_DEBUG=false` | продакшен-пути кода |
| Sessions | `SESSION_DRIVER=array` | эндпоинты без состояния — ничего не сериализуется под блокировкой записи |
| Versions | зафиксированы: PHP 8.4, Laravel 13, Octane 2.17 (см. манифест) | никаких подвижных частей |

Стенд запускает **по одному серверу приложения за раз** (все остальные остановлены), так
что его CPU/RAM измеряются изолированно, а не под конкуренцией со стороны простаивающих
соседей.

**Стандартное окружение: раннер GitHub Actions `ubuntu-24.04` (4 vCPU / 16 ГБ RAM).**
`benchmark.sh` **делит хост пополам**: SUT получает нижние ядра, генератор `wrk` — верхние
ядра, так что генератор **всегда изолирован** (он никогда не отбирает CPU у SUT). На
4-ядерном раннере это означает, что **SUT — это 2 cpu** (`cpuset 0-1`), а `wrk` работает на
`2-3`; на 8-ядерном хосте SUT получает 4 cpu (`0-3`), а `wrk` — `4-7`. Компромисс в том, что
SUT получает лишь **половину машины** — поэтому на стандартном раннере отчёты для **2-cpu
сервера**, записанного в лимитах манифеста (`cpus=2`). Поскольку общие раннеры CI к тому же
являются шумными соседями, читайте числа как **только относительные**.

## Нагрузки

Нагрузки организованы в три **группы**, чтобы графики и таблицы читались как «накладные
расходы → куда уходит CPU → I/O». Три маршрута группы `cpu` нагружают каждый *свой* путь
инструкций, поэтому они могут расходиться в том, какой сервер побеждает.

| Группа | Маршрут | Изолирует | Примечания |
|---|---|---|---|
| overhead | `/bench/hello` | маршрутизация + накладные расходы на ответ | тело фиксированной длины |
| cpu | `/bench/hash` | целочисленные / побитовые | цепочка `sha256` ×`BENCH_HASH_ITERATIONS` (откалибруйте так, чтобы ≫ hello) |
| cpu | `/bench/mandelbrot` | float / FPU | множество Мандельброта по времени убегания, сетка `BENCH_MANDELBROT_DIM`²×4, ограничение `…_MAX_ITER`, ×`…_REPEAT` (~30ms по умолчанию) |
| cpu | `/bench/json` | сериализация (кодек) | круговой проход `json_encode`+`json_decode` массива из 1000 int ×`BENCH_JSON_ITERATIONS` (доминирует кодек, не маршрутизация; ~20ms по умолчанию) |
| io | `/bench/db` | реальный запрос | `SELECT` по индексированному PK против **MySQL 8** |

**Оговорка по `/bench/db`:** серверы по-разному обрабатывают соединения (пул корутин Swoole
против RoadRunner против FrankenPHP). Эта нагрузка ограничена рамками **«поведение БД по
умолчанию для Octane у каждого сервера»**, а не изолированным измерением «сырого» запроса.
На графике она так и подписана.

## Запуск

По умолчанию этот проект генерирует отчёты бенчмарка на runner GitHub Actions. Вы можете
использовать workflow этого репозитория как есть, сделать fork и запустить его в своём repo,
или выполнить тот же harness на локальной либо удалённой машине, которую контролируете сами.

**В CI (по умолчанию):** запустите workflow **Benchmark**
(`.github/workflows/benchmark.yml`) через *Actions → Run workflow*. Он работает на
`ubuntu-24.04`, собирает отчёт и загружает `results/` + `docs/` как артефакт (установите
входной параметр `publish`, чтобы развернуть `docs/` на GitHub Pages). Входные параметры
позволяют масштабировать матрицу.

**Локально** — **Предусловия:** Docker (Compose v2) и PHP 8.4 + Composer на хосте для
`make deps` (на хосте выполняется только `composer install`; всё остальное — в Docker).
`Makefile` оборачивает workflow — `make help` перечисляет все цели.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

Настраивается через env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `WORKER_COUNTS`, `RUNS`, `DURATION`, `WARMUP`,
`TIMEOUT`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_DIM`, `BENCH_MANDELBROT_MAX_ITER`,
`BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`. Каждая пара (server, workload)
прогревается **на каждой конкурентности** перед своими прогонами, а `wrk --timeout`
(по умолчанию 15s) позволяет измерить медленную, насыщенную ячейку, а не отбросить её как
ошибки.

## Как это работает

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

Контейнер `wrk` запускает небольшой Lua-репортёр (`docker/wrk/report.lua`), который выдаёт
одну строку JSON с полными перцентилями задержек и счётчиками ошибок по классам.

## Idle memory profiler

Отдельный инструмент измеряет, **сколько RAM Octane держит резидентно на воркер** —
стоимость памяти за поддержание фреймворка прогретым — без нагрузки:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

Подгонка отделяет **фиксированные** накладные расходы фреймворка/мастера/OPcache от
**предельной** стоимости ещё одного воркера. Наивное среднее `RSS / N` вводит в заблуждение
— оно падает с ростом N только потому, что фиксированная стоимость амортизируется, а не
потому, что воркер стал дешевле.

## Оговорки

- **Одна машина, относительные, а не абсолютные значения.** Ваши числа будут отличаться;
  *форма* (кто где побеждает) — вот переносимый вывод.
- **Самопроверка закрепления.** Если хост не соблюдает `--cpuset-cpus`, каждая ячейка
  помечается `pinning=unverified`, и результат не подаётся как изолированный от генератора.
- **2-cpu SUT на 4-ядерном раннере.** Чтобы держать генератор изолированным, хост делится
  пополам — поэтому на стандартном раннере каждый сервер — это **2-cpu** сервер (остальные 2
  ядра гонят `wrk`). Это помечено в манифесте (`cpus=2`). Для 4-cpu SUT *с* изолированным
  генератором нужен 8-ядерный хост (разделение тогда даёт SUT 4 ядра, а `wrk` — другие 4).
- **Калибровка группы `cpu`.** Значения по умолчанию нацелены на **~20-30ms на запрос**:
  достаточно тяжело, чтобы доминировать над `/bench/hello`, достаточно легко, чтобы свип до
  конкурентности 128 не насыщался в таймауты `wrk` на 4-ядерной машине. Подстройте под свою
  машину через `BENCH_HASH_ITERATIONS` (2000), `BENCH_MANDELBROT_DIM` (32) /
  `BENCH_MANDELBROT_MAX_ITER` (256) и `BENCH_JSON_ITERATIONS` (150); `…_REPEAT` масштабирует
  mandelbrot вверх для более мощных хостов.

## Дорожная карта

- **Phase 2 — живой бенчмарк:** workflow GitHub Actions уже прогоняет матрицу на
  `ubuntu-24.04` и может публиковать на GitHub Pages. Далее: триггер `schedule:` для
  автоматического перезапуска при каждом релизе PHP/Octane/сервера. (Оговорка: размещённые
  раннеры шумные; для **4-cpu** SUT с по-прежнему изолированным генератором используйте
  self-hosted раннер с 8+ ядрами — разделение тогда автоматически даёт SUT `0-3`, а `wrk` —
  `4-7`.)
- **Phase 3 — движок решений:** «опиши форму моего приложения → какой сервер + число
  воркеров».

## Структура

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
