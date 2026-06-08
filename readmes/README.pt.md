[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · **Português**

---

# Laravel Octane Benchmark

Um harness reproduzível que faz benchmark dos servidores de aplicação Laravel Octane (**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) contra um grupo de controle tradicional **PHP-FPM + nginx** — e mostra *onde cada um vence*.

A maioria dos benchmarks de Octane publica um único número de "mais rápido" e se contradizem entre si, porque divergem silenciosamente em workload, contagem de workers, gerador de carga e warm-vs-cold, e raramente revelam algo disso. Este aqui corrige cada variável de confusão, revela todas elas e publica **curvas de cruzamento de latência por workload**. O veredito é explicitamente "depende — eis exatamente de que depende. Vá executá-lo você mesmo."

## Por que 2 CPU / 4 GB?

Executar benchmarks de frameworks em uma máquina superdimensionada tem pouco valor prático para a maioria dos deployments modernos. Estamos na era dos containers: aplicações normalmente são implantadas como unidades pequenas e repetíveis, e escalam horizontalmente quando o tráfego aumenta. A pergunta útil não é quão rápido um framework pode rodar em um servidor de alto desempenho com recursos abundantes, mas quanto throughput estável e qual latência de cauda um container comum consegue entregar antes de precisar de outra réplica.

Por isso, este benchmark usa `2 CPU / 4 GB RAM` como unidade do container da aplicação. Essa é uma alocação pequena e comum em produção, suficiente para executar Laravel corretamente e, ao mesmo tempo, revelar contenção entre workers, custo de memória e comportamento de saturação. Resultados medidos nesse tamanho são mais úteis para planejamento de capacidade, limites de auto scaling e comparação de custos do que pontuações produzidas por uma máquina que poucas aplicações dedicariam a um único processo de framework.

Ser o mais rápido também não significa ser o melhor. Swoole/OpenSwoole, RoadRunner e FrankenPHP têm compromissos diferentes e cenários de aplicação em que fazem mais sentido. Uma escolha real também depende do modelo operacional, do suporte do ecossistema, do estilo de deploy, da compatibilidade de extensões e da familiaridade da equipe. Este projeto não tenta resolver essa decisão; ele apenas executa os servidores em um ambiente justo e reproduzível e publica os dados.

## Resultados

Execute-o e abra `docs/index.html` (gráficos) / `RESULTS.md` (tabelas). Uma execução publicada é implantada no GitHub Pages (Settings → Pages → Source: GitHub Actions). O site é um pequeno dashboard de várias páginas: uma página **Compare** (heatmap de vencedores, curvas de p99 + throughput por workload com tabelas de dados, pico de RSS) mais uma página de **deep-report por servidor** para cada servidor Octane (Swoole / OpenSwoole / RoadRunner / FrankenPHP), com um **toggle de worker-count** para alternar toda a visão entre as contagens de workers varridas.

Estes são resultados de **máquina única**. Leia-os como **relativos** (qual servidor vence, e em qual concorrência o vencedor inverte), não como números absolutos para o seu hardware.

## O que é medido

**Destaque: latência p99 / p50 ao longo de uma varredura de concorrência.** A latência de cauda é onde esses servidores realmente divergem; o throughput médio frequentemente está dentro do ruído. O throughput (req/s) é reportado ao lado. O **pico de RSS** (marca d'água máxima de memória) é uma métrica secundária de "dimensionamento de VPS". O CPU% deliberadamente *não* é um destaque — a amostragem de CPU via cgroup é ruidosa demais para ser citada.

Cada célula = `{server, workload, workers, concurrency, run}` e é armazenada como um arquivo JSON em `results/` com um manifesto embutido (versões fixadas, caps, commit SHA, host, flags do wrk) de modo que qualquer ponto de dados seja reproduzível. Células que registraram erros do wrk (non-2xx / timeouts) são sinalizadas, nunca incluídas silenciosamente na média.

## Controles de equidade (mantidos idênticos para cada servidor)

| Controle | Valor | Por quê |
|---|---|---|
| Workers | **varridos** (`WORKER_COUNTS`, com uma base de 2 workers, ~2/cpu e seu ×2 → `2 4 8` no runner de 2 cpus); `max_children` do FPM correspondente | uma dimensão da matriz — veja como cada servidor escala com os workers. Mesma contagem para cada servidor (incl. o controle FPM) por passada; mais workers podem ser mais lentos quando a CPU já está sobrescrita |
| CPU | o SUT recebe todos os cores acima dos dois reservados (`cpuset 2-3` no runner de 4 cores) | todo servidor recebe o mesmo orçamento de CPU |
| Gerador + DB | `wrk` e `mysql` recebem um core dedicado cada (`0` e `1`), separados do SUT | gerador e banco não roubam CPU do SUT; `/bench/db` evita contenção de CPU do MySQL |
| Memória | `mem_limit=4g` (env `MEM_LIMIT`) | teto **igual** e generoso — nunca limita no runner de 16 GB, então nenhum servidor é penalizado por OOM e o pico de RSS lê a verdadeira marca d'água máxima (não restringida). Defina `MEM_LIMIT=512m` para um cenário de VPS pequeno |
| OPcache | habilitado, `validate_timestamps=0` | código compilado uma vez, como o Octane o mantém |
| Ambiente da app | `APP_ENV=production`, `APP_DEBUG=false` | caminhos de código de produção |
| Sessões | `SESSION_DRIVER=array` | endpoints sem estado — nada serializa em um lock de escrita |
| Versões | fixadas: PHP 8.4, Laravel 13, Octane 2.17 (ver manifesto) | sem partes móveis |

O harness executa **um servidor de aplicação por vez** (todos os outros parados) de modo que sua CPU/RAM seja medida em isolamento, não sob contenção de irmãos ociosos.

**Ambiente padrão: GitHub Actions `ubuntu-24.04` (4 vCPU / 16 GB RAM).** `wrk` usa o core `0`, `mysql` o core `1` e o SUT `cpuset 2-3`, com `cpus=2` e `mem_limit=4g`. Num host de 8 cores, `wrk` e `mysql` permanecem em `0` e `1`, enquanto o SUT usa `cpuset 2-7`. Gerador e banco ficam isolados do SUT. Runners compartilhados continuam ruidosos; valorize mais a forma dos resultados do que números exatos.

## Workloads

Os workloads são organizados em três **grupos** de modo que os gráficos e tabelas se leiam como "overhead → para onde vai a CPU → I/O". As três rotas do grupo `cpu` estressam cada uma um caminho de instrução *diferente*, então podem discordar sobre qual servidor vence.

| Grupo | Rota | Isola | Notas |
|---|---|---|---|
| overhead | `/bench/hello` | roteamento + overhead de resposta | corpo de comprimento fixo |
| cpu | `/bench/hash` | inteiro / bitwise | encadeamento `sha256` ×`BENCH_HASH_ITERATIONS` (calibre de modo que ≫ hello) |
| cpu | `/bench/mandelbrot` | float / FPU | Mandelbrot por tempo de escape, grade `BENCH_MANDELBROT_DIM`²×4, limite `…_MAX_ITER`, ×`…_REPEAT` (~30ms padrão) |
| cpu | `/bench/json` | serialização (codec) | round-trip de `json_encode`+`json_decode` de um array de 1000 inteiros ×`BENCH_JSON_ITERATIONS` (o codec domina, não o roteamento; ~20ms padrão) |
| io | `/bench/db` | uma query real | `SELECT` de PK indexada vs **MySQL 8** |

**Ressalva do `/bench/db`:** os servidores diferem no tratamento de conexões (pool de corrotinas do Swoole vs RoadRunner vs FrankenPHP). Este workload tem como escopo **"o comportamento de DB padrão do Octane de cada servidor",** não uma medição isolada de query bruta. Está rotulado como tal no gráfico.

## Execute-o

Por padrão, este projeto gera os relatórios de benchmark em um runner do GitHub Actions. Você pode usar o workflow deste repositório como está, fazer fork e executá-lo no seu próprio repo, ou executar o mesmo harness em uma máquina local ou remota sob seu controle.

**Em CI (o padrão):** dispare o workflow **Benchmark** (`.github/workflows/benchmark.yml`) via *Actions → Run workflow*. Ele roda em `ubuntu-24.04`, constrói o relatório e faz upload de `results/` + `docs/` como um artefato (defina a entrada `publish` para implantar `docs/` no GitHub Pages). As entradas permitem dimensionar a matriz.

**Localmente** — **Pré-requisitos:** Docker (Compose v2), e PHP 8.4 + Composer no host para `make deps` (apenas `composer install` roda no host; todo o resto está no Docker). Um `Makefile` envolve o workflow — `make help` lista cada target.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

Ajustável via env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `WORKER_COUNTS`, `RUNS`, `DURATION`, `WARMUP`,`TIMEOUT`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_DIM`, `BENCH_MANDELBROT_MAX_ITER`,`BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`. Cada (server, workload) é aquecido **em cada concorrência** antes de suas execuções, e o `wrk --timeout` (padrão 15s) permite que uma célula lenta e saturada seja medida em vez de censurada como erros.

Por padrão, `benchmark.sh` testa primeiro uma base de 2 workers, depois aproximadamente `2 * SUT_CPUS` workers e o dobro desse valor. No runner padrão de 4 vCPU, o SUT recebe 2 CPUs, então a varredura padrão de workers é `2 4 8`. Se uma contagem maior de workers reduz o throughput ou piora o p99, isso é um resultado válido: normalmente significa que workers PHP extras adicionam contenção do scheduler, pressão de cache ou contenção de DB/socket sem adicionar capacidade real de CPU.

## Como funciona

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

O container `wrk` roda um pequeno reporter em Lua (`docker/wrk/report.lua`) que emite uma linha JSON com percentis completos de latência e contagens de erro por classe.

## Profiler de memória ociosa

Uma ferramenta separada mede **quanta RAM o Octane mantém residente por worker** — o custo de memória de manter o framework aquecido — sem carga:

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

O ajuste separa o overhead **fixo** do framework/master/OPcache do custo **marginal** de mais um worker. A média ingênua `RSS / N` é enganosa — ela cai conforme N cresce apenas porque o custo fixo é amortizado, não porque um worker ficou mais barato.

## Ressalvas

- **Máquina única, relativo e não absoluto.** Seus números vão diferir; o *formato* (quem vence onde) é o achado portável.
- **Self-check de pinning.** Se o host não honrar `--cpuset-cpus`, cada célula é marcada com `pinning=unverified` e o resultado não é apresentado como isolado por gerador.
- **SUT de 2 cpus / 4 GB no runner de 4 cores.** Os outros dois cores são reservados separadamente para `wrk` e `mysql`, evitando competição com o SUT.
- **Mais workers não são automaticamente melhores.** Uma queda de 4 para 8 workers deve ser lida como o ponto local de saturação encontrado pelo benchmark, especialmente em workloads CPU-bound ou na divisão SUT padrão de 2 CPU.
- **Calibração do grupo `cpu`.** Os padrões miram em **~20-30ms por requisição**: pesado o suficiente para dominar `/bench/hello`, leve o suficiente para que uma varredura até a concorrência 128 não sature em timeouts do `wrk` numa máquina de 4 cores. Ajuste na sua máquina via `BENCH_HASH_ITERATIONS` (2000), `BENCH_MANDELBROT_DIM` (32) /`BENCH_MANDELBROT_MAX_ITER` (256), e `BENCH_JSON_ITERATIONS` (150); `…_REPEAT` escala o mandelbrot para cima para hosts mais pesados.

## Estrutura

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

## Resumo do benchmark

Relatório publicado: [Dashboard UI](https://terrylinooo.github.io/laravel-octane-benchmark) · [Dados dos resultados](https://terrylinooo.github.io/laravel-octane-benchmark/summary.json)

O benchmark foi executado em uma única máquina controlada. O container Docker do SUT foi limitado a `2 CPU / 4 GB RAM`, enquanto `wrk` e `mysql` usaram cores separados. Os dados são uma comparação relativa sob os mesmos limites, não um ranking universal para produção.

- Latência p99 mais estável: FrankenPHP
- Maior throughput de pico em alguns workloads: Swoole / OpenSwoole
- Menor uso de memória: PHP-FPM + nginx
- Eficiência mais fraca nesta configuração: RoadRunner
- Sob o limite de `2 CPU`, normalmente 4 workers são melhores que 8

FrankenPHP oferece o melhor equilíbrio entre estabilidade de latência, throughput competitivo e uso moderado de memória. A escolha de um servidor Octane não deve se basear apenas no máximo de requests per second.

## License

Este benchmark Laravel Octane é lançado sob a MIT License e mantido por [Terry L.](https://terryl.in). Terry L. também é o desenvolvedor do Airygen, um [WordPress SEO Plugin](https://www.airygen.com/en) gratuito e poderoso para equipes que precisam de fluxos de conteúdo estruturados e ferramentas de publicação orientadas a busca.

## Discussão aberta

Serviços de containers serverless, como Google Cloud Run, podem se comportar de forma diferente do container fixo de 2 CPU usado neste benchmark. Como esses serviços normalmente cobram pelo compute alocado e podem rodar sobre hosts com muitos CPU cores subjacentes, uma contagem maior de workers pode teoricamente consumir o compute disponível até atingir o limite configurado do serviço. Nesse ambiente, a regra prática `workers = CPU x 2` pode não ser o melhor padrão; o worker count deve ser ajustado de acordo com a CPU real alocada pela plataforma, o concurrency model, o comportamento de cobrança e o latency target.
