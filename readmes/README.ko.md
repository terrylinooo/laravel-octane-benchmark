[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · **한국어** · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Laravel Octane 애플리케이션 서버(**Swoole**, **OpenSwoole**, **RoadRunner**,
**FrankenPHP**)를 전통적인 **PHP-FPM + nginx** 대조군과 비교 벤치마킹하고, *각각이 어디에서
이기는지* 보여주는 재현 가능한 하니스입니다.

대부분의 Octane 벤치마크는 단일 "가장 빠른" 수치를 발표하면서 서로 모순됩니다.
워크로드, 워커 수, 부하 생성기, 워밍업 여부에서 슬그머니 차이가 나는데도 그 어느 것도 거의
공개하지 않기 때문입니다. 이 프로젝트는 모든 교란 변수를 고정하고, 그 전부를 공개하며,
**워크로드별 레이턴시 교차 곡선**을 발표합니다. 결론은 명시적으로 "상황에 따라 다르다 —
정확히 어떻게 다른지 여기 있다. 직접 실행해 보라"입니다.

> 방법론이 곧 제품입니다. 매니페스트로 어떤 수치를 재현할 수 없다면,
> 그것은 버그입니다.

## Results

실행한 뒤 `docs/index.html`(차트) / `RESULTS.md`(표)를 열어 보세요. 발표된 실행 결과는
`gh-pages` 브랜치에 있습니다.

이 결과는 **단일 머신** 결과입니다. 여러분 하드웨어에 대한 절대 수치가 아니라 **상대적인**
것(어느 서버가 이기는지, 그리고 어느 동시성에서 승자가 뒤바뀌는지)으로 읽으세요.

## What's measured

**핵심 지표: 동시성 스윕 전반의 p99 / p50 레이턴시.** 이 서버들이 실제로 갈리는 지점은
꼬리 레이턴시이며, 평균 처리량은 종종 노이즈 범위 안에 있습니다. 처리량(req/s)도 함께
보고됩니다. **Peak RSS**(메모리 최고 수위)는 보조적인 "VPS 사이징" 지표입니다. CPU%는
의도적으로 핵심 지표로 *삼지 않습니다* — cgroup CPU 샘플링은 인용하기에는 너무 노이즈가
심합니다.

각 셀 = `{server, workload, concurrency, run}`이며 `results/`에 하나의 JSON 파일로
저장되고, 매니페스트(고정된 버전, 상한, 커밋 SHA, 호스트, wrk 플래그)가 내장되어 있어
어떤 데이터 포인트도 재현할 수 있습니다. wrk 에러(non-2xx / 타임아웃)를 기록한 셀은
플래그가 붙으며, 절대 조용히 평균에 포함되지 않습니다.

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| 워커 | 모든 곳에서 **8** (FPM `pm=static, max_children=8`) | 동일한 예산; Octane의 ~2 워커/CPU × 4 코어 |
| CPU | 앱 컨테이너당 **`cpus=4`, `cpuset=0-3`** | 각 서버가 동일한 물리 코어 4개를 받음 |
| 부하 생성기 | **`${WRK_CPUSET}`로 고정된 `wrk`** — 8코어 이상 호스트에서는 `4-7`(격리), 4코어 기본 러너에서는 `0-3`(공존) | 코어가 남을 때 생성기를 격리; 셀별로 `generator_isolated`로 공개 |
| 메모리 | `mem_limit=512m` | 동일한 상한 |
| OPcache | 활성화, `validate_timestamps=0` | 코드는 한 번만 컴파일됨 (Octane이 유지하는 방식과 동일) |
| 앱 환경 | `APP_ENV=production`, `APP_DEBUG=false` | 프로덕션 코드 경로 |
| 세션 | `SESSION_DRIVER=array` | 무상태 엔드포인트 — 쓰기 잠금에서 직렬화되는 것이 없음 |
| 버전 | 고정: PHP 8.4, Laravel 13, Octane 2.17 (매니페스트 참조) | 움직이는 부분 없음 |

이 하니스는 **한 번에 하나의 앱 서버만** 실행하므로(나머지는 모두 정지), 해당 서버의
CPU/RAM은 유휴 상태인 형제 서버와의 경합이 아니라 격리된 상태에서 측정됩니다.

**기본 환경: GitHub Actions `ubuntu-24.04` 러너(4 vCPU / 16 GB RAM).**
`benchmark.sh`는 코어 수에 맞춰 적응합니다. SUT는 항상 `cpuset 0-3`을 받고, `wrk`
생성기는 **호스트에 코어가 ≥ 8개일 때만** 코어 `4-7`에 격리됩니다. 4코어 러너에는 코어
`4-7`이 없으므로 생성기는 `0-3`을 SUT와 공유합니다 — 각 셀은 `generator_isolated:
false`를 기록합니다. CI 러너 역시 시끄러운 이웃이므로, 그 실행 결과는 **상대값 전용**으로
읽으세요. 생성기 격리 수치를 원하면 8코어 이상 머신에서 실행하세요(하니스가
`WRK_CPUSET=4-7`을 자동으로 선택하거나, 직접 설정하면 됩니다).

## Workloads

워크로드는 차트와 표가 "오버헤드 → CPU가 어디로 가는지 → I/O"로 읽히도록 세 개의
**그룹**으로 구성됩니다. `cpu` 그룹의 세 라우트는 각각 *서로 다른* 명령 경로에 부하를
주므로, 어느 서버가 이기는지에 대해 서로 다른 답을 낼 수 있습니다.

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | 라우팅 + 응답 오버헤드 | 고정 길이 본문 |
| cpu | `/bench/hash` | 정수 / 비트 연산 | `sha256` 체이닝 ×`BENCH_HASH_ITERATIONS` (hello보다 ≫ 가 되도록 보정) |
| cpu | `/bench/mandelbrot` | 부동소수점 / FPU | escape-time Mandelbrot, 78×78 그리드 ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | 직렬화 (코덱) | 1000개 정수 배열의 `json_encode`+`json_decode` 왕복 ×`BENCH_JSON_ITERATIONS` (라우팅이 아니라 코덱이 지배) |
| io | `/bench/db` | 실제 쿼리 | 인덱싱된 PK `SELECT` vs **MySQL 8** |

**`/bench/db` 주의사항:** 서버마다 커넥션 처리 방식이 다릅니다(Swoole 코루틴 풀 vs
RoadRunner vs FrankenPHP). 이 워크로드는 격리된 순수 쿼리 측정이 아니라 **"각 서버의
기본 Octane DB 동작"**으로 범위가 한정됩니다. 차트에도 그렇게 표시됩니다.

## Run it

**CI에서(기본값):** *Actions → Run workflow*를 통해 **Benchmark** 워크플로
(`.github/workflows/benchmark.yml`)를 트리거하세요. `ubuntu-24.04`에서 실행되어 리포트를
빌드하고, `results/` + `docs/`를 아티팩트로 업로드합니다(선택적으로 `docs/`를 `gh-pages`에
발표). 입력값으로 매트릭스 규모를 조정할 수 있습니다.

**로컬에서** — **사전 요구사항:** Docker (Compose v2).

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

환경 변수로 조정 가능: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `RUNS`, `DURATION`,
`WARMUP`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`.

## How it works

```
benchmark.sh ── per (server, workload):
  stop all app servers → start this one (+ mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → warm (discarded) → sweep concurrency × runs via the pinned wrk container
  → write results/{server}_{workload}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup memory high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Chart.js)
```

`wrk` 컨테이너는 작은 Lua 리포터(`docker/wrk/report.lua`)를 실행하여, 전체 레이턴시
백분위수와 클래스별 에러 카운트를 담은 JSON 한 줄을 내보냅니다.

## Caveats

- **단일 머신, 절대값이 아니라 상대값.** 여러분의 수치는 다를 것입니다. 이식 가능한 발견은
  *형태*(누가 어디에서 이기는지)입니다.
- **고정 자체 점검.** 호스트가 `--cpuset-cpus`를 따르지 않으면, 모든 셀에
  `pinning=unverified` 태그가 붙고 그 결과는 생성기 격리된 것으로 제시되지 않습니다.
- **4코어에서의 생성기 공존.** 기본 `ubuntu-24.04` 러너에서는 부하 생성기가 SUT의 코어를
  공유합니다(`generator_isolated: false`). 비교는 여전히 공정합니다 — 모든 서버가 *동일한*
  공존 생성기 아래에서 측정되기 때문입니다 — 하지만 절대 레이턴시는 8코어 격리 실행에 비해
  부풀려집니다. 어느 쪽이든 상대 측정입니다.
- **`cpu` 그룹 보정.** `BENCH_HASH_ITERATIONS`(기본값 2000),
  `BENCH_MANDELBROT_REPEAT`(1), `BENCH_JSON_ITERATIONS`(1000)는 각 `cpu` 그룹
  라우트의 레이턴시가 `/bench/hello`를 분명하게 지배하도록 여러분의 머신에서 조정해야
  합니다.

## Roadmap

- **Phase 2 — 살아있는 벤치마크:** GitHub Actions 워크플로는 이미 `ubuntu-24.04`에서
  매트릭스를 실행하며 `gh-pages`로 발표할 수 있습니다. 다음 단계: 각 PHP/Octane/서버
  릴리스마다 자동으로 다시 실행하는 `schedule:` 트리거. (주의: 호스팅 러너는 노이즈가
  심합니다. 격리된 절대 수치를 원하면 자체 호스팅 8코어 이상 러너를 사용하세요 — 그러면
  하니스가 `wrk`를 `4-7`에 자동으로 고정합니다.)
- **Phase 3 — 의사결정 엔진:** "내 앱의 형태를 알려줘 → 어떤 서버 + 워커 수가 맞는지."

## Layout

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
