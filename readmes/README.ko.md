[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · **한국어** · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Laravel Octane 애플리케이션 서버(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) 를전통적인 **PHP-FPM + nginx** 대조군과 비교하여 벤치마크하고, *각각이 어디서 이기는지*를보여주는 재현 가능한 하니스입니다.

대부분의 Octane 벤치마크는 단 하나의 "가장 빠른" 수치만 발표하면서 서로 모순됩니다.워크로드, 워커 수, 부하 생성기, 워밍업 여부에서 슬그머니 차이가 나는데도 그 어느 것도 거의공개하지 않기 때문입니다. 이 프로젝트는 모든 교란 변수를 고정하고, 그 전부를 공개하며, **워크로드별 레이턴시 교차 곡선**을 발표합니다. 결론은 명시적으로 "상황에 따라 다르다 —정확히 어떻게 다른지 여기 있다. 직접 실행해 보라"입니다.

가장 빠르다고 해서 곧 가장 좋은 것은 아닙니다. Swoole/OpenSwoole, RoadRunner, FrankenPHP 는각각 장단점과 적합한 애플리케이션 형태가 다릅니다. 실제 선택에는 운영 모델, 생태계 지원,배포 방식, 확장 호환성, 팀의 익숙함도 함께 고려해야 합니다. 이 프로젝트는 그 선택을 결론내리려는것이 아니라, 공정하고 재현 가능한 환경에서 데이터를 만들어 공개하는 데만 집중합니다.

## Results

실행한 뒤 `docs/index.html `(차트) / ` RESULTS.md `(표) 를 열어 보세요. 발표된 실행 결과는 GitHub Pages 에 배포됩니다(Settings → Pages → Source: GitHub Actions). 사이트는 작은멀티 페이지 대시보드입니다: **Compare** 페이지(승자 히트맵, 워크로드별 p99 + 처리량 곡선과데이터 표, peak RSS) 와 각 Octane 서버(Swoole / OpenSwoole / RoadRunner / FrankenPHP) 별**서버별 심층 리포트** 페이지로 구성되며, **워커 수 토글**로 스윕한 워커 수에 따라 전체뷰를 전환할 수 있습니다.

이 결과는 **단일 머신** 결과입니다. 여러분 하드웨어에 대한 절대 수치가 아니라 **상대적인**것(어느 서버가 이기는지, 그리고 어느 동시성에서 승자가 뒤바뀌는지) 으로 읽으세요.

## What's measured

**핵심 지표: 동시성 스윕 전반의 p99 / p50 레이턴시.** 이 서버들이 실제로 갈리는 지점은꼬리 레이턴시이며, 평균 처리량은 종종 노이즈 범위 안에 있습니다. 처리량(req/s) 도 함께보고됩니다. **Peak RSS**(메모리 최고 수위) 는 보조적인 "VPS 사이징" 지표입니다. CPU%는의도적으로 핵심 지표로 *삼지 않습니다* — cgroup CPU 샘플링은 인용하기에는 너무 노이즈가심합니다.

각 셀 = `{server, workload, workers, concurrency, run}` 이며 ` results/` 에 하나의 JSON 파일로저장되고, 매니페스트(고정된 버전, 상한, 커밋 SHA, 호스트, wrk 플래그) 가 내장되어 있어어떤 데이터 포인트도 재현할 수 있습니다. wrk 에러(non-2xx / 타임아웃) 를 기록한 셀은플래그가 붙으며, 절대 조용히 평균에 포함되지 않습니다.

## Fairness controls (held identical for every server)

| Control | Value | Why |
|---|---|---|
| 워커 | **스윕**(` WORKER_COUNTS `, 기본값 ~2/cpu 와 그 ×2 → 2-cpu 러너에서 ` 4 8 `); FPM ` max_children ` 도 일치 | 매트릭스 차원 — 각 서버가 워커에 따라 어떻게 확장되는지 확인. 패스마다 모든 서버(FPM 대조군 포함) 에 동일한 수. CPU 가 oversubscribe 되면 워커를 더 늘리는 것이 오히려 느릴 수 있음 |
| CPU | **호스트의 아래쪽 절반** — 4 코어 러너에서 ` cpus=2 `, ` cpuset=0-1 `(8 코어 호스트에서는 ` cpus=4 `, ` cpuset=0-3 `) | 모든 서버가 동일한 코어를 받음; SUT cpu 수는 매니페스트 상한에 기록됨 |
| 부하 생성기 | **호스트의 위쪽 절반에서 ` wrk `**(러너에서 ` cpuset=2-3 `, 8 코어에서 ` 4-7 `) — SUT 와 분리 | 생성기는 **항상 격리됨**: SUT 의 CPU 를 절대 빼앗지 않음. 셀별로 ` generator_isolated ` 로 기록 |
| 메모리 | ` mem_limit=4g `(환경 변수 ` MEM_LIMIT `) | 넉넉한 **동일** 상한 — 16 GB 러너에서는 절대 걸리지 않으므로 어느 서버도 OOM 페널티를 받지 않고 peak RSS 가 진짜 최고 수위를 보여줌(클램핑되지 않음). 소형 VPS 시나리오는 ` MEM_LIMIT=512m ` 로 설정 |
| OPcache | 활성화, ` validate_timestamps=0 ` | 코드는 한 번만 컴파일됨 (Octane 이 유지하는 방식과 동일) |
| 앱 환경 | ` APP_ENV=production `, ` APP_DEBUG=false ` | 프로덕션 코드 경로 |
| 세션 | ` SESSION_DRIVER=array ` | 무상태 엔드포인트 — 쓰기 잠금에서 직렬화되는 것이 없음 |
| 버전 | 고정: PHP 8.4, Laravel 13, Octane 2.17 (매니페스트 참조) | 움직이는 부분 없음 |

이 하니스는 **한 번에 하나의 앱 서버만** 실행하므로(나머지는 모두 정지), 해당 서버의 CPU/RAM 은 유휴 상태인 형제 서버와의 경합이 아니라 격리된 상태에서 측정됩니다.

**기본 환경: GitHub Actions ` ubuntu-24.04 ` 러너(4 vCPU / 16 GB RAM).**` benchmark.sh ` 는 **호스트를 절반으로 나눕니다**: SUT 는 아래쪽 코어를, ` wrk ` 생성기는 위쪽코어를 받아 생성기가 **항상 격리되도록** 합니다(SUT 의 CPU 를 절대 빼앗지 않음). 4 코어러너에서는 **SUT 가 2 cpu**(` cpuset 0-1 `) 이고 ` cpus=2 `, ` mem_limit=4g ` 가 설정됩니다. 즉 Docker 로 2 CPU / 4 GB 에 제한된 server 이며, ` wrk ` 는 ` 2-3 ` 에서 실행됩니다. 8 코어 호스트에서는 SUT 가 4 cpu(` 0-3 `) 를 받고 ` wrk ` 는 ` 4-7 ` 을 받습니다. 절충점은 SUT 가 **머신의 절반만** 받는다는것입니다 — 그래서 기본 러너에서의 리포트는 **2-cpu / 4 GB 서버**에 대한 것이며, 매니페스트상한(` cpus=2 `, ` mem=4g `) 에 기록됩니다. 공유 CI 러너는 여전히 시끄러운 이웃이 있으므로, 수치는**상대값 전용**으로 읽으세요.

## Workloads

워크로드는 차트와 표가 "오버헤드 → CPU 가 어디로 가는지 → I/O"로 읽히도록 세 개의**그룹**으로 구성됩니다. ` cpu ` 그룹의 세 라우트는 각각 *서로 다른* 명령 경로에 부하를주므로, 어느 서버가 이기는지에 대해 서로 다른 답을 낼 수 있습니다.

| Group | Route | Isolates | Notes |
|---|---|---|---|
| overhead | `/bench/hello ` | 라우팅 + 응답 오버헤드 | 고정 길이 본문 |
| cpu | `/bench/hash ` | 정수 / 비트 연산 | ` sha256 ` 체이닝 ×` BENCH_HASH_ITERATIONS ` (hello 보다 ≫ 가 되도록 보정) |
| cpu | `/bench/mandelbrot ` | 부동소수점 / FPU | escape-time Mandelbrot, ` BENCH_MANDELBROT_DIM `²×4 그리드, `…_MAX_ITER ` 상한, ×`…_REPEAT ` (기본 ~30ms) |
| cpu | `/bench/json ` | 직렬화 (코덱) | 1000 개 정수 배열의 ` json_encode `+` json_decode ` 왕복 ×` BENCH_JSON_ITERATIONS ` (라우팅이 아니라 코덱이 지배; 기본 ~20ms) |
| io | `/bench/db ` | 실제 쿼리 | 인덱싱된 PK ` SELECT ` vs **MySQL 8** |

**`/bench/db ` 주의사항:** 서버마다 커넥션 처리 방식이 다릅니다(Swoole 코루틴 풀 vs RoadRunner vs FrankenPHP). 이 워크로드는 격리된 순수 쿼리 측정이 아니라 **"각 서버의기본 Octane DB 동작"**으로 범위가 한정됩니다. 차트에도 그렇게 표시됩니다.

## Run it

이 프로젝트는 기본적으로 GitHub Actions runner 에서 benchmark 를 실행하고 리포트를 생성하도록구성되어 있습니다. 이 저장소의 workflow 를 그대로 사용할 수도 있고, fork 한 뒤 자신의 repo 에서실행할 수도 있습니다. 직접 관리하는 로컬 머신이나 원격 머신에서 같은 harness 를 실행할 수도 있습니다.

**CI 에서(기본값):** *Actions → Run workflow*를 통해 **Benchmark** 워크플로(`.github/workflows/benchmark.yml `) 를 트리거하세요. ` ubuntu-24.04 ` 에서 실행되어 리포트를빌드하고, ` results/` + ` docs/` 를 아티팩트로 업로드합니다(` publish ` 입력을 설정하면 ` docs/` 를 GitHub Pages 에 배포). 입력값으로 매트릭스 규모를 조정할 수 있습니다.

**로컬에서** — **사전 요구사항:** Docker (Compose v2), 그리고 ` make deps ` 를 위해 호스트에 PHP 8.4 + Composer(호스트에서는 ` composer install ` 만 실행되고, 나머지는 전부 Docker 안에서실행됨). ` Makefile ` 이 워크플로를 감쌉니다 — ` make help ` 가 모든 타겟을 나열합니다.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

환경 변수로 조정 가능: ` SERVERS `, ` WORKLOADS `, ` CONCURRENCIES `, ` WORKER_COUNTS `, ` RUNS `, ` DURATION `, ` WARMUP `,` TIMEOUT `, ` BENCH_HASH_ITERATIONS `, ` BENCH_MANDELBROT_DIM `, ` BENCH_MANDELBROT_MAX_ITER `,` BENCH_MANDELBROT_REPEAT `, ` BENCH_JSON_ITERATIONS `. 각 (server, workload) 은 실행 전에**모든 동시성에서** 워밍업되며, ` wrk --timeout `(기본 15s) 으로 느리고 포화된 셀을 에러로검열하는 대신 측정할 수 있게 합니다.

` benchmark.sh ` 는 기본적으로 대략 ` 2 * SUT_CPUS ` 워커 수와 그 두 배를 테스트합니다. 기본 4-vCPU 러너에서는 SUT 가 2 CPUs 를 받으므로 기본 worker sweep 은 ` 4 8 ` 입니다. 8 workers 의 처리량이 4 보다낮거나 p99 가 더 나쁘다면, 이는 유효한 결과입니다. 보통 추가 PHP workers 가 scheduler contention, cache pressure, DB/socket contention 을 늘리지만 실제 사용 가능한 CPU 용량은 늘리지 않았다는 뜻입니다.

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

` wrk ` 컨테이너는 작은 Lua 리포터(` docker/wrk/report.lua `) 를 실행하여, 전체 레이턴시백분위수와 클래스별 에러 카운트를 담은 JSON 한 줄을 내보냅니다.

## Idle memory profiler

별도의 도구가 부하 없이 **Octane 이 워커당 얼마나 많은 RAM 을 상주시키는지** — 프레임워크를워밍 상태로 유지하는 메모리 비용 — 를 측정합니다:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

이 피팅은 **고정** 프레임워크/마스터/OPcache 오버헤드를 워커 하나를 더 추가하는 **한계**비용과 분리합니다. 단순한 ` RSS / N ` 평균은 오해를 부릅니다 — 그 값이 N 이 커질수록 떨어지는것은 워커가 더 싸져서가 아니라 고정 비용이 분할 상각되기 때문일 뿐입니다.

## Caveats

- **단일 머신, 절대값이 아니라 상대값.** 여러분의 수치는 다를 것입니다. 이식 가능한 발견은 *형태*(누가 어디에서 이기는지) 입니다.
- **고정 자체 점검.** 호스트가 `--cpuset-cpus ` 를 따르지 않으면, 모든 셀에
` pinning=unverified ` 태그가 붙고 그 결과는 생성기 격리된 것으로 제시되지 않습니다.
- **4 코어 러너의 2-cpu / 4 GB SUT.** 생성기를 격리된 상태로 유지하기 위해 호스트를 절반으로 나눕니다 — 그래서 기본 러너에서는 각 app Docker container 가 **2 CPU / 4 GB** server 입니다(나머지 2 코어는 ` wrk ` 를구동). 이는 매니페스트(` cpus=2 `, ` mem=4g `) 에 표시됩니다. 생성기가 격리된 *동시에* 4-cpu SUT 를원한다면 8 코어 호스트가 필요합니다(그러면 분할 시 SUT 가 4 코어, ` wrk ` 가 나머지 4 코어를 받음).
- **워커 수가 많다고 항상 더 빠른 것은 아닙니다.** 4 workers 에서 8 workers 로 올렸을 때 하락하면, 특히 CPU-bound workload 또는 기본 2-CPU SUT 분할에서는 이 머신의 국소 포화점을 benchmark 가 찾은 것으로 해석하세요.
- **` cpu ` 그룹 보정.** 기본값은 **요청당 ~20-30ms**를 목표로 합니다: `/bench/hello ` 를 분명하게 지배할 만큼 무겁고, 동시성 128 까지의 스윕이 4 코어 박스에서 ` wrk ` 타임아웃으로포화되지 않을 만큼 가볍게. ` BENCH_HASH_ITERATIONS `(2000), ` BENCH_MANDELBROT_DIM `(32) /` BENCH_MANDELBROT_MAX_ITER `(256), ` BENCH_JSON_ITERATIONS `(150) 로 여러분의 박스에 맞게조정하세요; `…_REPEAT ` 은 더 무거운 호스트를 위해 mandelbrot 를 키웁니다.

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

## License

이 Laravel Octane benchmark 는 MIT License 로 배포되며 [Terry L.](https://terryl.in) 이관리합니다. Terry L.은 Airygen 의 개발자이기도 합니다. Airygen 은 구조화된 콘텐츠 워크플로와검색 중심 퍼블리싱 도구가 필요한 팀을 위한 무료이며 강력한 [WordPress SEO Plugin](https://www.airygen.com/ko) 입니다.

## 논의 중

Google Cloud Run 같은 serverless container 서비스는 이 benchmark 에서 사용한 고정 2-CPU container 와다르게 동작할 수 있습니다. 이런 서비스는 보통 할당된 compute 기준으로 과금되며, 하위 host 에는 많은 CPU cores 가 있을 수 있습니다. worker 수가 많으면 이론적으로 설정된 서비스 한도에 도달할 때까지 사용 가능한 compute 를 계속 소비할 수 있습니다. 이런 환경에서는 ` workers = CPU x 2 ` 라는 경험칙이 적절한 기본값이아닐 수 있습니다. worker count 는 플랫폼의 실제 CPU allocation, concurrency model, 과금 방식, latency target 에 맞춰 조정해야 합니다.
