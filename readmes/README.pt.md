[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · [Français](README.fr.md) · **Português**

---

# Laravel Octane Benchmark

Um harness reproduzível que faz benchmark dos servidores de aplicação Laravel Octane
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) contra um grupo de controle
tradicional **PHP-FPM + nginx** — e mostra *onde cada um vence*.

A maioria dos benchmarks do Octane publica um único número "mais rápido" e se contradizem
entre si, porque divergem silenciosamente em carga de trabalho, número de workers, gerador
de carga e quente-versus-frio, e raramente revelam qualquer um desses detalhes. Este aqui
fixa cada variável de confusão, revela todas elas, e publica **curvas de cruzamento de
latência por carga de trabalho**. O veredito é explicitamente "depende — aqui está
exatamente como depende. Vá executá-lo você mesmo."

> A metodologia é o produto. Se você não consegue reproduzir um número a partir do seu
> manifesto, é um bug.

## Resultados

Execute-o e abra `docs/index.html` (gráficos) / `RESULTS.md` (tabelas). Uma execução
publicada vive na branch `gh-pages`.

Estes são resultados de **máquina única**. Leia-os como **relativos** (qual servidor vence
e em qual concorrência o vencedor muda), não como números absolutos para o seu hardware.

## O que é medido

**Destaque: latência p99 / p50 ao longo de uma varredura de concorrência.** A latência de
cauda é onde estes servidores realmente divergem; o throughput médio costuma ficar dentro
do ruído. O throughput (req/s) é reportado em conjunto. **Pico de RSS** (marca máxima de
memória) é uma métrica secundária de "dimensionamento de VPS". O CPU% deliberadamente *não*
é um destaque — a amostragem de CPU do cgroup é ruidosa demais para ser citada.

Cada célula = `{server, workload, concurrency, run}` e é armazenada como um arquivo JSON em
`results/` com um manifesto embutido (versões fixadas, limites, commit SHA, host, flags do
wrk) para que qualquer ponto de dado seja reproduzível. Células que registraram erros do
wrk (não-2xx / timeouts) são sinalizadas, nunca silenciosamente incluídas na média.

## Controles de equidade (mantidos idênticos para cada servidor)

| Controle | Valor | Por quê |
|---|---|---|
| Workers | **8** em todos os lugares (FPM `pm=static, max_children=8`) | mesmo orçamento; ~2 workers/CPU × 4 cores do Octane |
| CPU | **`cpus=4`, `cpuset=0-3`** por contêiner da aplicação | cada servidor recebe os mesmos 4 cores físicos |
| Gerador de carga | **`wrk` fixado via `${WRK_CPUSET}`** — `4-7` em um host com 8+ cores (isolado), `0-3` no runner padrão de 4 cores (co-residente) | isola o gerador quando há cores disponíveis para ele; revelado por célula como `generator_isolated` |
| Memória | `mem_limit=512m` | mesmo teto |
| OPcache | habilitado, `validate_timestamps=0` | código compilado uma vez, como o Octane mantém |
| Ambiente da app | `APP_ENV=production`, `APP_DEBUG=false` | caminhos de código de produção |
| Sessões | `SESSION_DRIVER=array` | endpoints stateless — nada serializa em um lock de escrita |
| Versões | fixadas: PHP 8.4, Laravel 13, Octane 2.17 (veja o manifesto) | sem partes móveis |

O harness executa **um servidor de aplicação por vez** (todos os outros parados) para que
seu CPU/RAM sejam medidos em isolamento, não sob contenção de irmãos ociosos.

**Ambiente padrão: um runner `ubuntu-24.04` do GitHub Actions (4 vCPU / 16 GB RAM).**
O `benchmark.sh` se adapta à contagem de cores: o SUT sempre recebe `cpuset 0-3`, e o
gerador `wrk` é isolado nos cores `4-7` **somente quando o host tem ≥ 8 cores**. No runner
de 4 cores não existem os cores `4-7`, então o gerador compartilha `0-3` com o SUT — cada
célula registra `generator_isolated: false`. Como os runners de CI também são vizinhos
barulhentos, leia essas execuções como **somente relativas**. Para números com gerador
isolado, execute em uma máquina de 8+ cores (o harness escolhe `WRK_CPUSET=4-7`
automaticamente, ou defina você mesmo).

## Cargas de trabalho

As cargas de trabalho são organizadas em três **grupos** para que os gráficos e tabelas
sejam lidos como "overhead → para onde a CPU vai → I/O". As três rotas do grupo `cpu`
estressam cada uma um caminho de instruções *diferente*, de modo que podem discordar sobre
qual servidor vence.

| Grupo | Rota | Isola | Notas |
|---|---|---|---|
| overhead | `/bench/hello` | roteamento + overhead de resposta | corpo de tamanho fixo |
| cpu | `/bench/hash` | inteiro / bitwise | encadeamento de `sha256` ×`BENCH_HASH_ITERATIONS` (calibre para que seja ≫ hello) |
| cpu | `/bench/mandelbrot` | float / FPU | Mandelbrot por tempo de escape, grade 78×78 ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | serialização (codec) | round-trip de `json_encode`+`json_decode` de um array de 1000 inteiros ×`BENCH_JSON_ITERATIONS` (o codec domina, não o roteamento) |
| io | `/bench/db` | uma query real | `SELECT` por PK indexada vs **MySQL 8** |

**Ressalva do `/bench/db`:** os servidores diferem no tratamento de conexões (pool de
corrotinas do Swoole vs RoadRunner vs FrankenPHP). Esta carga de trabalho é delimitada como
**"o comportamento de DB padrão do Octane de cada servidor",** não uma medição isolada de
query bruta. Está rotulada como tal no gráfico.

## Execute-o

**No CI (o padrão):** dispare o workflow **Benchmark**
(`.github/workflows/benchmark.yml`) via *Actions → Run workflow*. Ele executa em
`ubuntu-24.04`, constrói o relatório, e faz upload de `results/` + `docs/` como um artefato
(opcionalmente publicando `docs/` em `gh-pages`). As entradas permitem dimensionar a matriz.

**Localmente** — **Pré-requisito:** Docker (Compose v2).

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

Ajustável via env: `SERVERS`, `WORKLOADS`, `CONCURRENCIES`, `RUNS`, `DURATION`, `WARMUP`,
`BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_REPEAT`, `BENCH_JSON_ITERATIONS`.

## Como funciona

```
benchmark.sh ── per (server, workload):
  stop all app servers → start this one (+ mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → warm (discarded) → sweep concurrency × runs via the pinned wrk container
  → write results/{server}_{workload}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup memory high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Chart.js)
```

O contêiner `wrk` executa um pequeno reporter em Lua (`docker/wrk/report.lua`) que emite
uma linha JSON com percentis de latência completos e contagens de erro por classe.

## Ressalvas

- **Máquina única, relativo não absoluto.** Seus números serão diferentes; o *formato*
  (quem vence onde) é o achado portável.
- **Auto-verificação de fixação.** Se o host não honrar `--cpuset-cpus`, cada célula é
  marcada como `pinning=unverified` e o resultado não é apresentado como gerador isolado.
- **Co-residência do gerador em 4 cores.** No runner padrão `ubuntu-24.04` o gerador de
  carga compartilha os cores do SUT (`generator_isolated: false`). A comparação permanece
  justa — cada servidor é medido sob o *mesmo* gerador co-residente — mas a latência
  absoluta é inflada em relação a uma execução isolada de 8 cores. De qualquer forma, é uma
  medição relativa.
- **Calibração do grupo `cpu`.** `BENCH_HASH_ITERATIONS` (padrão 2000),
  `BENCH_MANDELBROT_REPEAT` (1), e `BENCH_JSON_ITERATIONS` (1000) devem ser ajustados na sua
  máquina para que a latência de cada rota do grupo `cpu` domine claramente `/bench/hello`.

## Roadmap

- **Fase 2 — benchmark vivo:** o workflow do GitHub Actions já executa a matriz em
  `ubuntu-24.04` e pode publicar em `gh-pages`. A seguir: um gatilho `schedule:` para
  re-executar automaticamente a cada lançamento de PHP/Octane/servidor. (Ressalva: runners
  hospedados são barulhentos; para números absolutos isolados use um runner self-hosted de
  8+ cores — o harness então fixará `wrk` em `4-7` automaticamente.)
- **Fase 3 — motor de decisão:** "diga-me o formato da minha app → qual servidor + número
  de workers."

## Estrutura

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
