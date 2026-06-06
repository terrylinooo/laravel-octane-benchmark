[English](../README.md) · [繁體中文](README.zh-Hant.md) · [简体中文](README.zh-Hans.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Italiano](README.it.md) · **Français** · [Português](README.pt.md)

---

# Laravel Octane Benchmark

Un banc d'essai reproductible qui mesure les serveurs applicatifs Laravel Octane (**Swoole**, **OpenSwoole**, **RoadRunner**, **FrankenPHP**) face à un groupe de contrôle traditionnel **PHP-FPM + nginx** — et montre *où chacun l'emporte*.

La plupart des benchmarks Octane publient un unique chiffre du « plus rapide » et se contredisent les uns les autres, parce qu'ils diffèrent discrètement sur la charge de travail, le nombre de workers, le générateur de charge et le démarrage à chaud ou à froid, et qu'ils ne divulguent presque jamais rien de tout cela. Celui-ci fige toutes les variables parasites, les divulgue toutes, et publie des **courbes de croisement de latence par charge de travail**. Le verdict est explicitement « ça dépend — voici exactement de quoi ça dépend. Allez le lancer vous-même. »

Le plus rapide n'est pas automatiquement le meilleur. Swoole/OpenSwoole, RoadRunner et FrankenPHP ont chacun leurs compromis et leurs scénarios d'application naturels. Un vrai choix dépend aussi du modèle d'exploitation, du support de l'écosystème, du mode de déploiement, de la compatibilité des extensions et de la familiarité de l'équipe. Ce projet ne cherche pas à trancher cette décision ; il se contente d'exécuter les serveurs dans un environnement équitable et reproductible, puis de publier les données.

## Résultats

Lancez-le et ouvrez `docs/index.html` (graphiques) / `RESULTS.md` (tableaux). Une exécution publiée est déployée sur GitHub Pages (Settings → Pages → Source: GitHub Actions). Le site est un petit tableau de bord multi-pages : une page **Compare** (heatmap des vainqueurs, courbes de p99 + débit par charge de travail avec tableaux de données, RSS de pointe) plus une page de **rapport détaillé par serveur** pour chaque serveur Octane (Swoole / OpenSwoole / RoadRunner / FrankenPHP), avec une **bascule de nombre de workers** pour faire passer toute la vue d'un nombre de workers balayé à l'autre.

Ce sont des résultats sur **une seule machine**. Lisez-les comme **relatifs** (quel serveur l'emporte, et à quelle concurrence le vainqueur bascule), et non comme des chiffres absolus pour votre matériel.

## Ce qui est mesuré

**En vedette : latence p99 / p50 sur un balayage de concurrence.** La latence de queue est là où ces serveurs divergent réellement ; le débit moyen reste souvent dans le bruit. Le débit (req/s) est rapporté en parallèle. La **RSS de pointe** (pic d'utilisation mémoire) est une métrique secondaire de « dimensionnement de VPS ». Le CPU% n'est délibérément *pas* mis en vedette — l'échantillonnage CPU des cgroups est trop bruité pour être cité.

Chaque cellule = `{server, workload, workers, concurrency, run}` et est stockée comme un fichier JSON dans `results/` avec un manifeste intégré (versions figées, plafonds, SHA de commit, hôte, flags wrk) afin que tout point de données soit reproductible. Les cellules ayant enregistré des erreurs wrk (non-2xx / timeouts) sont signalées, jamais moyennées silencieusement.

## Contrôles d'équité (maintenus identiques pour chaque serveur)

| Contrôle | Valeur | Pourquoi |
|---|---|---|
| Workers | **balayés** (`WORKER_COUNTS`, par défaut ~2/cpu et son ×2 → `4 8` sur le runner à 2 cpu) ; le `max_children` de FPM est aligné | une dimension de la matrice — voyez comment chaque serveur passe à l'échelle avec les workers. Même nombre pour chaque serveur (y compris le contrôle FPM) à chaque passe ; plus de workers peuvent ralentir une fois le CPU surabonné |
| CPU | le SUT reçoit tous les cœurs au-dessus des deux cœurs réservés (`cpuset 2-3` sur le runner à 4 cœurs) | chaque serveur reçoit le même budget CPU |
| Générateur + DB | `wrk` et `mysql` ont chacun un cœur dédié (`0` et `1`), séparé du SUT | ni le générateur ni la base de données ne prennent du CPU au SUT ; `/bench/db` évite la contention CPU de MySQL |
| Mémoire | `mem_limit=4g` (env `MEM_LIMIT`) | plafond **égal** généreux — il ne contraint jamais sur le runner à 16 Go, donc aucun serveur n'est pénalisé par l'OOM et la RSS de pointe relève le vrai pic d'utilisation (non bridé). Définissez `MEM_LIMIT=512m` pour un scénario de petit VPS |
| OPcache | activé, `validate_timestamps=0` | code compilé une seule fois, comme Octane le conserve |
| Environnement de l'application | `APP_ENV=production`, `APP_DEBUG=false` | chemins de code de production |
| Sessions | `SESSION_DRIVER=array` | endpoints sans état — rien ne se sérialise sur un verrou d'écriture |
| Versions | figées : PHP 8.4, Laravel 13, Octane 2.17 (voir le manifeste) | aucune pièce mobile |

Le banc d'essai exécute **un seul serveur applicatif à la fois** (tous les autres arrêtés) de sorte que son CPU/RAM soit mesuré de manière isolée, et non sous la contention de voisins inactifs.

**Environnement par défaut : GitHub Actions `ubuntu-24.04` (4 vCPU / 16 Go).** `wrk` utilise le cœur `0`, `mysql` le cœur `1`, et le SUT `cpuset 2-3` avec `cpus=2` et `mem_limit=4g`. Sur un hôte à 8 cœurs, `wrk` et `mysql` restent sur `0` et `1`, tandis que le SUT utilise `cpuset 2-7`. Le générateur et la base sont ainsi isolés du SUT. Les runners partagés restent bruités : privilégiez la forme des résultats aux chiffres exacts.

## Charges de travail

Les charges de travail sont organisées en trois **groupes** afin que les graphiques et les tableaux se lisent comme « surcoût → où part le CPU → E/S ». Les trois routes du groupe `cpu` sollicitent chacune un chemin d'instructions *différent*, de sorte qu'elles peuvent ne pas s'accorder sur le serveur qui l'emporte.

| Groupe | Route | Isole | Notes |
|---|---|---|---|
| overhead | `/bench/hello` | routage + surcoût de réponse | corps de longueur fixe |
| cpu | `/bench/hash` | entier / bit à bit | chaînage `sha256` ×`BENCH_HASH_ITERATIONS` (calibrez pour que ce soit ≫ hello) |
| cpu | `/bench/mandelbrot` | flottant / FPU | Mandelbrot par temps d'évasion, grille `BENCH_MANDELBROT_DIM`²×4, plafond `…_MAX_ITER`, ×`…_REPEAT` (~30ms par défaut) |
| cpu | `/bench/json` | sérialisation (codec) | aller-retour `json_encode`+`json_decode` d'un tableau de 1000 entiers ×`BENCH_JSON_ITERATIONS` (le codec domine, pas le routage ; ~20ms par défaut) |
| io | `/bench/db` | une vraie requête | `SELECT` sur clé primaire indexée face à **MySQL 8** |

**Mise en garde sur `/bench/db` :** les serveurs diffèrent dans la gestion des connexions (pool de coroutines Swoole vs RoadRunner vs FrankenPHP). Cette charge de travail est cadrée comme **« le comportement DB Octane par défaut de chaque serveur »**, et non comme une mesure isolée de requête brute. Elle est étiquetée comme telle sur le graphique.

## Lancez-le

Par défaut, ce projet génère les rapports de benchmark sur un runner GitHub Actions. Vous pouvez utiliser le workflow de ce dépôt tel quel, le forker et l'exécuter dans votre propre repo, ou lancer le même harness sur une machine locale ou distante que vous contrôlez.

**En CI (par défaut) :** déclenchez le workflow **Benchmark** (`.github/workflows/benchmark.yml`) via *Actions → Run workflow*. Il s'exécute sur `ubuntu-24.04`, construit le rapport et téléverse `results/` + `docs/` en tant qu'artefact (définissez l'entrée `publish` pour déployer `docs/` sur GitHub Pages). Des entrées vous permettent de mettre la matrice à l'échelle.

**En local** — **Prérequis :** Docker (Compose v2), et PHP 8.4 + Composer sur l'hôte pour `make deps` (seul `composer install` s'exécute sur l'hôte ; tout le reste est dans Docker). Un `Makefile` enveloppe le workflow — `make help` liste chaque cible.

```bash
make setup     # one-time: .env + APP_KEY + composer install into vendor/
make bench     # the full matrix  (= ./benchmark.sh; resumable — existing cells are skipped)
make report    # build RESULTS.md + docs/ (Compare + per-server pages)  (= python3 bench/aggregate.py)

make smoke     # quick end-to-end smoke run (a few minutes)
```

Réglable via les variables d'environnement : `SERVERS`, `WORKLOADS`, `CONCURRENCIES`,`WORKER_COUNTS`, `RUNS`, `DURATION`, `WARMUP`, `TIMEOUT`, `BENCH_HASH_ITERATIONS`,`BENCH_MANDELBROT_DIM`, `BENCH_MANDELBROT_MAX_ITER`, `BENCH_MANDELBROT_REPEAT`,`BENCH_JSON_ITERATIONS`. Chaque (server, workload) est chauffé **à chaque concurrence** avant ses exécutions, et `wrk --timeout` (15s par défaut) permet de mesurer une cellule lente et saturée plutôt que de la censurer sous forme d'erreurs.

Par défaut, `benchmark.sh` teste environ `2 * SUT_CPUS` workers puis le double. Sur le runner par défaut à 4 vCPU, le SUT reçoit 2 CPUs, donc le balayage de workers par défaut est `4 8`. Si 8 workers affichent un débit plus faible ou un p99 pire que 4, c'est un résultat valide : cela signifie généralement que les workers PHP supplémentaires ajoutent de la contention du scheduler, de la pression cache ou de la contention DB/socket sans ajouter de capacité CPU utile.

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

Le conteneur `wrk` exécute un petit reporter Lua (`docker/wrk/report.lua`) qui émet une ligne JSON avec les percentiles de latence complets et les comptages d'erreurs par classe.

## Profileur de mémoire au repos

Un outil distinct mesure **combien de RAM Octane garde résidente par worker** — le coût mémoire de maintenir le framework chaud — sans aucune charge :

```bash
./bench/mem-profile.sh        # boot each server at N workers (4/8/16/32), warm every
                              # worker, read the container working set (cgroup rss+shmem,
                              # so shared OPcache is counted once)
python3 bench/mem_profile.py  # linear fit working_set(N) = fixed + marginal·N
```

L'ajustement sépare le surcoût **fixe** framework/master/OPcache du coût **marginal** d'un worker supplémentaire. La moyenne naïve `RSS / N` est trompeuse — elle baisse à mesure que N grandit uniquement parce que le coût fixe est amorti, pas parce qu'un worker est devenu moins cher.

## Mises en garde

- **Une seule machine, relatif et non absolu.** Vos chiffres différeront ; la *forme* (qui l'emporte et où) est la conclusion transposable.
- **Auto-vérification de l'épinglage.** Si l'hôte ne respecte pas `--cpuset-cpus`, chaque cellule est étiquetée `pinning=unverified` et le résultat n'est pas présenté comme isolé du générateur.
- **SUT à 2 cpu / 4 Go sur le runner à 4 cœurs.** Les deux autres cœurs sont réservés séparément à `wrk` et `mysql`, afin qu'ils ne concurrencent pas le SUT.
- **Plus de workers n'est pas automatiquement mieux.** Une baisse de 4 à 8 workers doit être lue comme le point de saturation local trouvé par le benchmark, surtout pour les workloads CPU-bound ou avec la coupe SUT par défaut à 2 CPU.
- **Calibrage du groupe `cpu`.** Les valeurs par défaut visent **~20-30ms par requête** : assez lourdes pour dominer `/bench/hello`, assez légères pour qu'un balayage jusqu'à la concurrence 128 ne sature pas en timeouts `wrk` sur une machine à 4 cœurs. Ajustez sur votre machine via `BENCH_HASH_ITERATIONS` (2000), `BENCH_MANDELBROT_DIM` (32) /`BENCH_MANDELBROT_MAX_ITER` (256), et `BENCH_JSON_ITERATIONS` (150) ; `…_REPEAT` augmente la charge de mandelbrot pour des hôtes plus puissants.

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

## Résumé du benchmark

Rapport publié : [Dashboard UI](https://terrylinooo.github.io/laravel-octane-benchmark) · [Données des résultats](https://terrylinooo.github.io/laravel-octane-benchmark/summary.json)

Le benchmark a été exécuté sur une seule machine contrôlée. Le conteneur Docker du SUT était limité à `2 CPU / 4 GB RAM`, tandis que `wrk` et `mysql` utilisaient des cœurs distincts. Les données constituent une comparaison relative sous les mêmes limites, pas un classement universel pour la production.

- Latence p99 la plus stable : FrankenPHP
- Débit de pointe le plus élevé sur certains workloads : Swoole / OpenSwoole
- Consommation mémoire la plus faible : PHP-FPM + nginx
- Efficacité la plus faible dans cette configuration : RoadRunner
- Sous la limite de `2 CPU`, 4 workers sont généralement préférables à 8

FrankenPHP offre le meilleur équilibre entre stabilité de la latence, débit compétitif et consommation mémoire modérée. Le choix d'un serveur Octane ne doit pas reposer uniquement sur le maximum de requests per second.

## License

Ce benchmark Laravel Octane est publié sous MIT License et maintenu par [Terry L.](https://terryl.in). Terry L. est également le développeur d'Airygen, un [WordPress SEO Plugin](https://www.airygen.com/en) gratuit et puissant pour les équipes qui ont besoin de workflows de contenu structurés et d'outils de publication orientés recherche.

## Discussion ouverte

Les services de conteneurs serverless, comme Google Cloud Run, peuvent se comporter différemment du conteneur fixe à 2 CPU utilisé dans ce benchmark. Comme ces services facturent généralement le compute alloué et peuvent s'exécuter sur des hôtes disposant de nombreux CPU cores sous-jacents, un nombre plus élevé de workers peut théoriquement consommer le compute disponible jusqu'à atteindre la limite configurée du service. Dans cet environnement, la règle empirique `workers = CPU x 2` n'est pas forcément le bon choix par défaut ; le worker count doit être ajusté selon l'allocation CPU réelle de la plateforme, le concurrency model, le mode de facturation et le latency target.
