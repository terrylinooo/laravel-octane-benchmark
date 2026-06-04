[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · **Français** · [Português](README.pt.md)

---

# Benchmark Laravel Octane

Un banc d'essai reproductible qui mesure les serveurs applicatifs Laravel Octane
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) face à un groupe de contrôle
traditionnel **PHP-FPM + nginx** — et montre *où chacun l'emporte*.

La plupart des benchmarks Octane publient un unique chiffre du « plus rapide » et se
contredisent les uns les autres, parce qu'ils diffèrent discrètement sur la charge de
travail, le nombre de workers, le générateur de charge et le démarrage à chaud ou à froid,
et qu'ils ne divulguent presque jamais rien de tout cela. Celui-ci fige toutes les
variables parasites, les divulgue toutes, et publie des **courbes de croisement de latence
par charge de travail**. Le verdict est explicitement « ça dépend — voici exactement de quoi
ça dépend. Allez le lancer vous-même. »

> La méthodologie est le produit. Si vous ne pouvez pas reproduire un chiffre à partir de
> son manifeste, c'est un bug.

## Résultats

Lancez-le et ouvrez `docs/index.html` (graphiques) / `RESULTS.md` (tableaux). Une exécution
publiée se trouve sur la branche `gh-pages`.

Ce sont des résultats sur **une seule machine**. Lisez-les comme **relatifs** (quel serveur
l'emporte, et à quelle concurrence le vainqueur bascule), et non comme des chiffres absolus
pour votre matériel.

## Ce qui est mesuré

**En vedette : latence p99 / p50 sur un balayage de concurrence.** La latence de queue est
là où ces serveurs divergent réellement ; le débit moyen reste souvent dans le bruit. Le
débit (req/s) est rapporté en parallèle. La **RSS de pointe** (pic d'utilisation mémoire)
est une métrique secondaire de « dimensionnement de VPS ». Le CPU% n'est délibérément *pas*
mis en vedette — l'échantillonnage CPU des cgroups est trop bruité pour être cité.

Chaque cellule = `{server, workload, concurrency, run}` et est stockée comme un fichier JSON
dans `results/` avec un manifeste intégré (versions figées, plafonds, SHA de commit, hôte,
flags wrk) afin que tout point de données soit reproductible. Les cellules ayant enregistré
des erreurs wrk (non-2xx / timeouts) sont signalées, jamais moyennées silencieusement.

## Contrôles d'équité (maintenus identiques pour chaque serveur)

| Contrôle | Valeur | Pourquoi |
|---|---|---|
| Workers | **8** partout (FPM `pm=static, max_children=8`) | même budget ; les ~2 workers/CPU × 4 cœurs d'Octane |
| CPU | **`cpus=4`, `cpuset=0-3`** par conteneur d'application | chaque serveur reçoit les mêmes 4 cœurs physiques |
| Générateur de charge | **`wrk` épinglé via `${WRK_CPUSET}`** — `4-7` sur un hôte à 8 cœurs ou plus (isolé), `0-3` sur le runner par défaut à 4 cœurs (co-résident) | isole le générateur lorsqu'il existe des cœurs pour lui ; divulgué par cellule via `generator_isolated` |
| Mémoire | `mem_limit=512m` | même plafond |
| OPcache | activé, `validate_timestamps=0` | code compilé une seule fois, comme Octane le conserve |
| Environnement de l'application | `APP_ENV=production`, `APP_DEBUG=false` | chemins de code de production |
| Sessions | `SESSION_DRIVER=array` | endpoints sans état — rien ne se sérialise sur un verrou d'écriture |
| Versions | figées : PHP 8.4, Laravel 13, Octane 2.17 (voir le manifeste) | aucune pièce mobile |

Le banc d'essai exécute **un seul serveur applicatif à la fois** (tous les autres arrêtés)
de sorte que son CPU/RAM soit mesuré de manière isolée, et non sous la contention de voisins
inactifs.

**Environnement par défaut : un runner GitHub Actions `ubuntu-24.04` (4 vCPU / 16 Go de
RAM).** `benchmark.sh` s'adapte au nombre de cœurs : le SUT reçoit toujours `cpuset 0-3`, et
le générateur `wrk` est isolé sur les cœurs `4-7` **uniquement lorsque l'hôte dispose de
≥ 8 cœurs**. Sur le runner à 4 cœurs, il n'y a pas de cœurs `4-7`, donc le générateur
partage `0-3` avec le SUT — chaque cellule enregistre `generator_isolated: false`. Comme les
runners CI sont aussi des voisins bruyants, lisez ces exécutions comme **relatives
uniquement**. Pour des chiffres avec générateur isolé, lancez sur une machine à 8 cœurs ou
plus (le banc d'essai choisit `WRK_CPUSET=4-7` automatiquement, ou définissez-le vous-même).

## Charges de travail

Les charges de travail sont organisées en trois **groupes** afin que les graphiques et les
tableaux se lisent comme « surcoût → où part le CPU → E/S ». Les trois routes du groupe
`cpu` sollicitent chacune un chemin d'instructions *différent*, de sorte qu'elles peuvent
ne pas s'accorder sur le serveur qui l'emporte.

| Groupe | Route | Isole | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | routage + surcoût de réponse | corps de longueur fixe |
| cpu | `/bench/hash` | entier / bit à bit | chaînage `sha256` ×`BENCH_HASH_ITERATIONS` (calibrez pour que ce soit ≫ hello) |
| cpu | `/bench/mandelbrot` | flottant / FPU | Mandelbrot par temps d'évasion, grille 78×78 ×`BENCH_MANDELBROT_REPEAT` |
| cpu | `/bench/json` | sérialisation (codec) | aller-retour `json_encode`+`json_decode` d'un tableau de 1000 entiers ×`BENCH_JSON_ITERATIONS` (le codec domine, pas le routage) |
| io | `/bench/db` | une vraie requête | `SELECT` sur clé primaire indexée face à **MySQL 8** |

**Mise en garde sur `/bench/db` :** les serveurs diffèrent dans la gestion des connexions
(pool de coroutines Swoole vs RoadRunner vs FrankenPHP). Cette charge de travail est cadrée
comme **« le comportement DB Octane par défaut de chaque serveur »**, et non comme une
mesure isolée de requête brute. Elle est étiquetée comme telle sur le graphique.

## Lancez-le

**En CI (par défaut) :** déclenchez le workflow **Benchmark**
(`.github/workflows/benchmark.yml`) via *Actions → Run workflow*. Il s'exécute sur
`ubuntu-24.04`, construit le rapport et téléverse `results/` + `docs/` en tant qu'artefact
(en publiant éventuellement `docs/` sur `gh-pages`). Des entrées vous permettent de mettre
la matrice à l'échelle.

**En local** — **Prérequis :** Docker (Compose v2).

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

Réglable via les variables d'environnement : `SERVERS`, `WORKLOADS`, `CONCURRENCIES`,
`RUNS`, `DURATION`, `WARMUP`, `BENCH_HASH_ITERATIONS`, `BENCH_MANDELBROT_REPEAT`,
`BENCH_JSON_ITERATIONS`.

## Comment ça marche

```
benchmark.sh ── per (server, workload):
  stop all app servers → start this one (+ mysql for db) → wait healthy
  → cpuset self-check (tags pinning=verified|unverified)
  → warm (discarded) → sweep concurrency × runs via the pinned wrk container
  → write results/{server}_{workload}_c{conc}_r{run}.json (+ embedded manifest)
  → capture peak RSS (cgroup memory high-water mark) → stop → settle
bench/aggregate.py ── results/*.json → medians+ranges → RESULTS.md + docs/ (Chart.js)
```

Le conteneur `wrk` exécute un petit reporter Lua (`docker/wrk/report.lua`) qui émet une
ligne JSON avec les percentiles de latence complets et les comptages d'erreurs par classe.

## Mises en garde

- **Une seule machine, relatif et non absolu.** Vos chiffres différeront ; la *forme* (qui
  l'emporte et où) est la conclusion transposable.
- **Auto-vérification de l'épinglage.** Si l'hôte ne respecte pas `--cpuset-cpus`, chaque
  cellule est étiquetée `pinning=unverified` et le résultat n'est pas présenté comme isolé
  du générateur.
- **Co-résidence du générateur sur 4 cœurs.** Sur le runner `ubuntu-24.04` par défaut, le
  générateur de charge partage les cœurs du SUT (`generator_isolated: false`). La
  comparaison reste équitable — chaque serveur est mesuré sous le *même* générateur
  co-résident — mais la latence absolue est gonflée par rapport à une exécution isolée sur
  8 cœurs. C'est une mesure relative dans les deux cas.
- **Calibrage du groupe `cpu`.** `BENCH_HASH_ITERATIONS` (par défaut 2000),
  `BENCH_MANDELBROT_REPEAT` (1) et `BENCH_JSON_ITERATIONS` (1000) doivent être ajustés sur
  votre machine afin que la latence de chaque route du groupe `cpu` domine clairement
  `/bench/hello`.

## Feuille de route

- **Phase 2 — benchmark vivant :** le workflow GitHub Actions exécute déjà la matrice sur
  `ubuntu-24.04` et peut publier sur `gh-pages`. Ensuite : un déclencheur `schedule:` pour
  relancer automatiquement à chaque sortie de PHP/Octane/serveur. (Mise en garde : les
  runners hébergés sont bruités ; pour des chiffres absolus isolés, utilisez un runner
  auto-hébergé à 8 cœurs ou plus — le banc d'essai épinglera alors `wrk` sur `4-7`
  automatiquement.)
- **Phase 3 — moteur de décision :** « dites-moi la forme de mon application → quel serveur
  + nombre de workers. »

## Organisation

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
