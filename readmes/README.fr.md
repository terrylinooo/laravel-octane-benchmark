[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · **Français** · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Un banc d'essai reproductible qui mesure les serveurs applicatifs Laravel Octane
(**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) face à un groupe de contrôle
traditionnel **PHP-FPM + nginx** — et montre *où chacun l'emporte*.

La plupart des benchmarks Octane publient un unique chiffre du « plus rapide » et se
contredisent les uns les autres, parce qu'ils diffèrent discrètement sur la charge de
travail, le nombre de workers, le générateur de charge et le démarrage à chaud ou à froid,
et qu'ils ne divulguent presque jamais rien de tout cela. Celui-ci fige toutes les variables
parasites, les divulgue toutes, et publie des **courbes de croisement de latence par charge
de travail**. Le verdict est explicitement « ça dépend — voici exactement de quoi ça dépend.
Allez le lancer vous-même. »

Le plus rapide n'est pas automatiquement le meilleur. Swoole/OpenSwoole, RoadRunner et
FrankenPHP ont chacun leurs compromis et leurs scénarios d'application naturels. Un vrai
choix dépend aussi du modèle d'exploitation, du support de l'écosystème, du mode de
déploiement, de la compatibilité des extensions et de la familiarité de l'équipe. Ce projet
ne cherche pas à trancher cette décision ; il se contente d'exécuter les serveurs dans un
environnement équitable et reproductible, puis de publier les données.

## Résultats

Lancez-le et ouvrez `docs/index.html` (graphiques) / `RESULTS.md` (tableaux). Une exécution
publiée est déployée sur GitHub Pages (Settings → Pages → Source: GitHub Actions). Le site
est un petit tableau de bord multi-pages : une page **Compare** (heatmap des vainqueurs,
courbes de p99 + débit par charge de travail avec tableaux de données, RSS de pointe) plus
une page de **rapport détaillé par serveur** pour chaque serveur Octane (Swoole / OpenSwoole
/ RoadRunner / FrankenPHP), avec une **bascule de nombre de workers** pour faire passer toute
la vue d'un nombre de workers balayé à l'autre.

Ce sont des résultats sur **une seule machine**. Lisez-les comme **relatifs** (quel serveur
l'emporte, et à quelle concurrence le vainqueur bascule), et non comme des chiffres absolus
pour votre matériel.

## Ce qui est mesuré

**En vedette : latence p99 / p50 sur un balayage de concurrence.** La latence de queue est
là où ces serveurs divergent réellement ; le débit moyen reste souvent dans le bruit. Le
débit (req/s) est rapporté en parallèle. La **RSS de pointe** (pic d'utilisation mémoire)
est une métrique secondaire de « dimensionnement de VPS ». Le CPU% n'est délibérément *pas*
mis en vedette — l'échantillonnage CPU des cgroups est trop bruité pour être cité.

Chaque cellule = `{server, workload, workers, concurrency, run}` et est stockée comme un
fichier JSON dans `results/` avec un manifeste intégré (versions figées, plafonds, SHA de
commit, hôte, flags wrk) afin que tout point de données soit reproductible. Les cellules
ayant enregistré des erreurs wrk (non-2xx / timeouts) sont signalées, jamais moyennées
silencieusement.

## Contrôles d'équité (maintenus identiques pour chaque serveur)

| Contrôle | Valeur | Pourquoi |
|---|---|---|
| Workers | **balayés** (`WORKER_COUNTS`, par défaut ~2/cpu et son ×2 → `4 8` sur le runner à 2 cpu) ; le `max_children` de FPM est aligné | une dimension de la matrice — voyez comment chaque serveur passe à l'échelle avec les workers. Même nombre pour chaque serveur (y compris le contrôle FPM) à chaque passe |
| CPU | **la moitié basse de l'hôte** — `cpus=2`, `cpuset=0-1` sur le runner à 4 cœurs (`cpus=4`, `cpuset=0-3` sur un hôte à 8 cœurs) | chaque serveur reçoit les mêmes cœurs ; le nombre de cpu du SUT est enregistré dans les plafonds du manifeste |
| Générateur de charge | **`wrk` sur la moitié haute de l'hôte** (`cpuset=2-3` sur le runner, `4-7` sur 8 cœurs) — disjoint du SUT | le générateur est **toujours isolé** : il ne vole jamais le CPU du SUT. Enregistré par cellule via `generator_isolated` |
| Mémoire | `mem_limit=4g` (env `MEM_LIMIT`) | plafond **égal** généreux — il ne contraint jamais sur le runner à 16 Go, donc aucun serveur n'est pénalisé par l'OOM et la RSS de pointe relève le vrai pic d'utilisation (non bridé). Définissez `MEM_LIMIT=512m` pour un scénario de petit VPS |
| OPcache | activé, `validate_timestamps=0` | code compilé une seule fois, comme Octane le conserve |
| Environnement de l'application | `APP_ENV=production`, `APP_DEBUG=false` | chemins de code de production |
| Sessions | `SESSION_DRIVER=array` | endpoints sans état — rien ne se sérialise sur un verrou d'écriture |
| Versions | figées : PHP 8.4, Laravel 13, Octane 2.17 (voir le manifeste) | aucune pièce mobile |

Le banc d'essai exécute **un seul serveur applicatif à la fois** (tous les autres arrêtés)
de sorte que son CPU/RAM soit mesuré de manière isolée, et non sous la contention de voisins
inactifs.

**Environnement par défaut : un runner GitHub Actions `ubuntu-24.04` (4 vCPU / 16 Go de
RAM).** `benchmark.sh` **coupe l'hôte en deux** : le SUT reçoit les cœurs bas, le générateur
`wrk` les cœurs hauts, de sorte que le générateur est **toujours isolé** (il ne vole jamais
le CPU du SUT). Sur le runner à 4 cœurs cela signifie que le **SUT a 2 cpu** (`cpuset 0-1`)
et que `wrk` s'exécute sur `2-3` ; sur un hôte à 8 cœurs le SUT reçoit 4 cpu (`0-3`) et `wrk`
`4-7`. Le compromis est que le SUT ne reçoit que **la moitié de la machine** — donc sur le
runner par défaut les rapports concernent un **serveur à 2 cpu**, enregistré dans les
plafonds du manifeste (`cpus=2`). Comme les runners CI partagés restent des voisins bruyants,
lisez ces chiffres comme **relatifs uniquement**.

## Charges de travail

Les charges de travail sont organisées en trois **groupes** afin que les graphiques et les
tableaux se lisent comme « surcoût → où part le CPU → E/S ». Les trois routes du groupe
`cpu` sollicitent chacune un chemin d'instructions *différent*, de sorte qu'elles peuvent
ne pas s'accorder sur le serveur qui l'emporte.

| Groupe | Route | Isole | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | routage + surcoût de réponse | corps de longueur fixe |
| cpu | `/bench/hash` | entier / bit à bit | chaînage `sha256` ×`BENCH_HASH_ITERATIONS` (calibrez pour que ce soit ≫ hello) |
| cpu | `/bench/mandelbrot` | flottant / FPU | Mandelbrot par temps d'évasion, grille `BENCH_MANDELBROT_DIM`²×4, plafond `…_MAX_ITER`, ×`…_REPEAT` (~30ms par défaut) |
| cpu | `/bench/json` | sérialisation (codec) | aller-retour `json_encode`+`json_decode` d'un tableau de 1000 entiers ×`BENCH_JSON_ITERATIONS` (le codec domine, pas le routage ; ~20ms par défaut) |
| io | `/bench/db` | une vraie requête | `SELECT` sur clé primaire indexée face à **MySQL 8** |

**Mise en garde sur `/bench/db` :** les serveurs diffèrent dans la gestion des connexions
(pool de coroutines Swoole vs RoadRunner vs FrankenPHP). Cette charge de travail est cadrée
comme **« le comportement DB Octane par défaut de chaque serveur »**, et non comme une mesure
isolée de requête brute. Elle est étiquetée comme telle sur le graphique.

## Lancez-le

Par défaut, ce projet génère les rapports de benchmark sur un runner GitHub Actions. Vous
pouvez utiliser le workflow de ce dépôt tel quel, le forker et l'exécuter dans votre propre
repo, ou lancer le même harness sur une machine locale ou distante que vous contrôlez.

**En CI (par défaut) :** déclenchez le workflow **Benchmark**
(`.github/workflows/benchmark.yml`) via *Actions → Run workflow*. Il s'exécute sur
`ubuntu-24.04`, construit le rapport et téléverse `results/` + `docs/` en tant qu'artefact
(définissez l'entrée `publish` pour déployer `docs/` sur GitHub Pages). Des entrées vous
permettent de mettre la matrice à l'échelle.

**En local** — **Prérequis :** Docker (Compose v2), et PHP 8.4 + Composer sur l'hôte pour
`make deps` (seul `composer install` s'exécute sur l'hôte ; tout le reste est dans Docker).
Un `Makefile` enveloppe le workflow — `make help` liste chaque cible.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

Réglable via les variables d'environnement : `SERVERS`, `WORKLOADS`, `CONCURRENCIES`,
`WORKER_COUNTS`, `RUNS`, `DURATION`, `WARMUP`, `TIMEOUT`, `BENCH_HASH_ITERATIONS`,
`BENCH_MANDELBROT_DIM`, `BENCH_MANDELBROT_MAX_ITER`, `BENCH_MANDELBROT_REPEAT`,
`BENCH_JSON_ITERATIONS`. Chaque (server, workload) est chauffé **à chaque concurrence** avant
ses exécutions, et `wrk --timeout` (15s par défaut) permet de mesurer une cellule lente et
saturée plutôt que de la censurer sous forme d'erreurs.

## Comment ça marche

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

Le conteneur `wrk` exécute un petit reporter Lua (`docker/wrk/report.lua`) qui émet une
ligne JSON avec les percentiles de latence complets et les comptages d'erreurs par classe.

## Profileur de mémoire au repos

Un outil distinct mesure **combien de RAM Octane garde résidente par worker** — le coût
mémoire de maintenir le framework chaud — sans aucune charge :

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

L'ajustement sépare le surcoût **fixe** framework/master/OPcache du coût **marginal** d'un
worker supplémentaire. La moyenne naïve `RSS / N` est trompeuse — elle baisse à mesure que N
grandit uniquement parce que le coût fixe est amorti, pas parce qu'un worker est devenu moins
cher.

## Mises en garde

- **Une seule machine, relatif et non absolu.** Vos chiffres différeront ; la *forme* (qui
  l'emporte et où) est la conclusion transposable.
- **Auto-vérification de l'épinglage.** Si l'hôte ne respecte pas `--cpuset-cpus`, chaque
  cellule est étiquetée `pinning=unverified` et le résultat n'est pas présenté comme isolé du
  générateur.
- **SUT à 2 cpu sur le runner à 4 cœurs.** Pour garder le générateur isolé, l'hôte est coupé
  en deux — donc sur le runner par défaut chaque serveur est un serveur à **2 cpu** (les 2
  autres cœurs pilotent `wrk`). C'est étiqueté dans le manifeste (`cpus=2`). Pour un SUT à
  4 cpu *avec* un générateur isolé il vous faut un hôte à 8 cœurs (la coupe donne alors 4
  cœurs au SUT, les 4 autres à `wrk`).
- **Calibrage du groupe `cpu`.** Les valeurs par défaut visent **~20-30ms par requête** :
  assez lourdes pour dominer `/bench/hello`, assez légères pour qu'un balayage jusqu'à la
  concurrence 128 ne sature pas en timeouts `wrk` sur une machine à 4 cœurs. Ajustez sur
  votre machine via `BENCH_HASH_ITERATIONS` (2000), `BENCH_MANDELBROT_DIM` (32) /
  `BENCH_MANDELBROT_MAX_ITER` (256), et `BENCH_JSON_ITERATIONS` (150) ; `…_REPEAT` augmente la
  charge de mandelbrot pour des hôtes plus puissants.

## Feuille de route

- **Phase 2 — benchmark vivant :** le workflow GitHub Actions exécute déjà la matrice sur
  `ubuntu-24.04` et peut déployer sur GitHub Pages. Ensuite : un déclencheur `schedule:` pour
  relancer automatiquement à chaque sortie de PHP/Octane/serveur. (Mise en garde : les runners
  hébergés sont bruités ; pour un SUT à **4 cpu** avec le générateur toujours isolé, utilisez
  un runner auto-hébergé à 8 cœurs ou plus — la coupe donne alors `0-3` au SUT et `4-7` à
  `wrk` automatiquement.)
- **Phase 3 — moteur de décision :** « dites-moi la forme de mon application → quel serveur +
  nombre de workers. »

## Organisation

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
