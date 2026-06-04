#!/usr/bin/env bash
#
# Laravel Octane benchmark — reproducible crossover harness.
#
# Runs ONE app server at a time (others stopped), sweeps concurrency, and writes
# one JSON result per cell with an embedded manifest. The whole point is fairness:
#   * the host is split in half: the SUT gets the LOWER half of the cores, the wrk
#     generator the UPPER half, so the generator is always isolated (never steals the
#     SUT's CPU). On the default 4-core GitHub Actions runner that's SUT=2 cpus
#     (cpuset 0-1) + wrk=cpuset 2-3; on an 8-core host it's SUT 0-3 + wrk 4-7. The SUT
#     cpu count is recorded in the manifest caps so reports are labelled honestly.
#   * workers = ~2 per SUT cpu (4 on the 2-cpu runner, 8 on 8 cores), FPM matched
#     via pool.conf; opcache + production parity
#   * latency percentiles (p50/p99) from wrk are the headline metric
#   * peak RSS (cgroup high-water mark, v2 memory.peak or v1 max_usage_in_bytes) per cell
#   * cells with wrk errors are recorded so bad cells can't masquerade as clean
#
# Resumable: a cell whose JSON already exists is skipped, so a crash mid-matrix
# doesn't restart from zero. Delete results/ to start fresh.
#
# Usage:
#   ./benchmark.sh                       # full matrix (~3-4h)
#   SERVERS=swoole WORKLOADS=hello CONCURRENCIES=8 RUNS=1 DURATION=5 WARMUP=2 ./benchmark.sh   # smoke
#
set -uo pipefail
cd "$(dirname "$0")"

# ---- config (env-overridable) -------------------------------------------------
SERVERS="${SERVERS:-swoole openswoole roadrunner frankenphp fpm}"
# Grouped: overhead (hello) -> cpu (hash, mandelbrot, json) -> io (db).
WORKLOADS="${WORKLOADS:-hello hash mandelbrot json db}"
CONCURRENCIES="${CONCURRENCIES:-8 16 32 64 128}"
RUNS="${RUNS:-3}"
DURATION="${DURATION:-30}"     # measured seconds per run
WARMUP="${WARMUP:-10}"         # discarded warmup seconds per concurrency level
THREADS="${THREADS:-4}"
TIMEOUT="${TIMEOUT:-15s}"      # wrk per-request timeout — slow cells get measured, not censored
SETTLE="${SETTLE:-3}"          # teardown settle delay between (server,workload)
RESULTS_DIR="${RESULTS_DIR:-results}"
APP_SERVICES="swoole openswoole roadrunner frankenphp fpm nginx"

# ---- core placement: split the host in half (2+2 on the 4-core CI runner) --------
# The SUT gets the LOWER half of the cores, the wrk generator the UPPER half, so the
# generator is ALWAYS isolated (disjoint core sets) — it never steals the SUT's CPU.
# On the default 4-core runner that's SUT=cpuset 0-1 (2 cpus) + wrk=cpuset 2-3; on an
# 8-core host it's SUT 0-3 + wrk 4-7. The trade-off is the SUT only gets half the box
# (2 cpus on CI) — the manifest caps record that so reports are labelled honestly.
NPROC="$(nproc)"
HALF=$(( NPROC / 2 )); [ "$HALF" -lt 1 ] && HALF=1
SUT_CPUS="${SUT_CPUS:-$HALF}"
SUT_CPUSET="${SUT_CPUSET:-0-$((HALF - 1))}"
WRK_CPUSET="${WRK_CPUSET:-$HALF-$((NPROC - 1))}"
export SUT_CPUS SUT_CPUSET WRK_CPUSET
# Isolated whenever the two core sets differ (always, by construction of the split).
GEN_ISOLATED=true; [ "$SUT_CPUSET" = "$WRK_CPUSET" ] && GEN_ISOLATED=false
# Workers track the SUT's cores (Octane's ~2 workers/CPU): 4 on the 2-cpu CI runner,
# 8 on an 8-core host. compose reads OCTANE_WORKERS; FPM is matched via pool.conf.
OCTANE_WORKERS="${OCTANE_WORKERS:-$(( SUT_CPUS * 2 ))}"
export OCTANE_WORKERS

dc() { docker compose "$@"; }

# ---- cgroup reads inside a container (v2 unified vs v1 legacy paths) -----------
# The default GitHub Actions ubuntu-24.04 runner is cgroup v2 (no /sys/fs/cgroup/
# memory/ or /cpuset/ dirs); WSL2 etc. are still v1. Detect via cgroup.controllers
# and read the right path, so peak RSS and the pinning self-check work on both.
read_cpuset() {   # $1=service -> effective cpuset string (e.g. "0-3")
  dc exec -T "$1" sh <<'INNER' 2>/dev/null | tr -d '\r\n'
if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
  cat /sys/fs/cgroup/cpuset.cpus.effective 2>/dev/null
else
  cat /sys/fs/cgroup/cpuset/cpuset.cpus 2>/dev/null
fi
INNER
}
read_peak_rss() { # $1=service -> peak RSS in bytes (v2 memory.peak; current as fallback)
  dc exec -T "$1" sh <<'INNER' 2>/dev/null | tr -dc '0-9'
if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
  cat /sys/fs/cgroup/memory.peak 2>/dev/null || cat /sys/fs/cgroup/memory.current 2>/dev/null
else
  cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null
fi
INNER
}

# ---- server -> target host : services to start : container to measure RSS -----
server_target()  { case "$1" in fpm) echo nginx;; *) echo "$1";; esac; }
server_services(){ case "$1" in fpm) echo "fpm nginx";; *) echo "$1";; esac; }
server_measure() { echo "$1"; }   # measure the PHP container (fpm, not nginx)

route_for() { echo "/bench/$1"; }

mkdir -p "$RESULTS_DIR"

# ---- wait until given services are healthy ------------------------------------
wait_healthy() {
  local want=$# svc ok
  for _ in $(seq 1 60); do
    ok=0
    for svc in "$@"; do
      [ "$(dc ps "$svc" --format '{{.Health}}' 2>/dev/null)" = "healthy" ] && ok=$((ok+1))
    done
    [ "$ok" -eq "$want" ] && return 0
    sleep 2
  done
  echo "  ! timed out waiting for healthy: $*" >&2
  return 1
}

# ---- are all cells for this (server,workload) already on disk? -----------------
cells_complete() {
  local server="$1" workload="$2" conc run f
  [ -f "$RESULTS_DIR/${server}_${workload}_rss.json" ] || return 1
  for conc in $CONCURRENCIES; do
    for run in $(seq 1 "$RUNS"); do
      f="$RESULTS_DIR/${server}_${workload}_c${conc}_r${run}.json"
      [ -f "$f" ] || return 1
    done
  done
  return 0
}

# ---- static manifest (built once) ---------------------------------------------
build_manifest() {
  local php_ver octane_ver laravel_ver commit host
  php_ver=$(grep -oE 'PHP_VERSION[":= ]+[0-9.]+' <<<"$(docker inspect ghcr.io/airygen/php:8.4-swoole-1.0.0 --format '{{json .Config.Env}}')" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  octane_ver=$(jq -r '.packages[] | select(.name=="laravel/octane") | .version' composer.lock 2>/dev/null)
  laravel_ver=$(jq -r '.packages[] | select(.name=="laravel/framework") | .version' composer.lock 2>/dev/null)
  commit=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
  host=$(uname -srm)
  jq -n \
    --arg php "${php_ver:-8.4.x}" --arg octane "${octane_ver:-?}" --arg laravel "${laravel_ver:-?}" \
    --arg commit "$commit" --arg host "$host" --arg nproc "$NPROC" \
    --arg date "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson workers "$OCTANE_WORKERS" \
    --arg caps "cpus=${SUT_CPUS},cpuset=${SUT_CPUSET},mem=${MEM_LIMIT:-8g}" \
    --arg wrk "wrk -t${THREADS} -d${DURATION}s --timeout ${TIMEOUT} --latency" \
    --arg wrk_cpuset "$WRK_CPUSET" --argjson gen_isolated "$GEN_ISOLATED" \
    '{php:$php, laravel:$laravel, octane:$octane, workers:$workers, caps:$caps,
      commit:$commit, host:$host, nproc:($nproc|tonumber), wrk_cmd:$wrk,
      wrk_cpuset:$wrk_cpuset, generator_isolated:$gen_isolated, generated_at:$date}'
}

# ---- one wrk run -> writes a cell file ----------------------------------------
run_cell() {
  local server="$1" workload="$2" conc="$3" run="$4" target="$5" pinning="$6"
  local route out wrkjson f
  f="$RESULTS_DIR/${server}_${workload}_c${conc}_r${run}.json"
  [ -f "$f" ] && { echo "      c${conc} r${run}: cached"; return 0; }
  route=$(route_for "$workload")
  out=$(dc run --rm wrk -t"$THREADS" -c"$conc" -d"${DURATION}s" --timeout "$TIMEOUT" --latency -s /report.lua \
        "http://${target}:8000${route}" 2>/dev/null)
  wrkjson=$(grep '^__WRKJSON__' <<<"$out" | sed 's/^__WRKJSON__//' | head -1)
  if [ -z "$wrkjson" ]; then
    echo "      c${conc} r${run}: NO RESULT (wrk produced no JSON)" >&2
    return 1
  fi
  jq -n --argjson wrk "$wrkjson" --argjson man "$MANIFEST" \
    --arg server "$server" --arg workload "$workload" --arg route "$route" \
    --argjson conc "$conc" --argjson run "$run" --arg pinning "$pinning" \
    '{server:$server, workload:$workload, route:$route, concurrency:$conc, run:$run,
      pinning:$pinning, wrk:$wrk, manifest:$man}' > "$f"
  local rps p99 errs
  rps=$(jq -r '.wrk.rps' "$f"); p99=$(jq -r '.wrk.latency_ms.p99' "$f")
  errs=$(jq -r '[.wrk.errors[]] | add' "$f")
  printf "      c%-3s r%s: %8.0f rps  p99=%7.1fms  errors=%s\n" "$conc" "$run" "$rps" "$p99" "$errs"
}

# ============================== main ===========================================
echo "Servers:       $SERVERS"
echo "Workloads:     $WORKLOADS"
echo "Concurrencies: $CONCURRENCIES   Runs/cell: $RUNS   Duration: ${DURATION}s   Warmup: ${WARMUP}s"
echo "Cores:         nproc=$NPROC   SUT=${SUT_CPUS}cpu (cpuset $SUT_CPUSET)   wrk=cpuset $WRK_CPUSET   workers=$OCTANE_WORKERS   generator_isolated=$GEN_ISOLATED"
[ "$GEN_ISOLATED" = false ] && echo "  ! host too small to split — generator shares the SUT's cores (co-resident), relative-only."
echo

echo "==> Preparing backend (mysql) ..."
dc up -d mysql >/dev/null 2>&1
wait_healthy mysql || { echo "mysql never came up"; exit 1; }
# Idempotent migrate+seed (uses one app image, no deps).
dc run --rm --no-deps swoole php artisan migrate --force >/dev/null 2>&1 \
  && echo "    bench_items ready." || echo "    (migrate skipped/failed — db workload may error)"

MANIFEST=$(build_manifest)
echo "==> Manifest: $(jq -c '{php,laravel,octane,commit,caps}' <<<"$MANIFEST")"
echo

# Match the FPM pool to OCTANE_WORKERS so the control group has the same worker
# budget. Write into the bind-mounted pool.conf from a pristine copy via redirect
# (preserves the inode — `sed -i` swaps it and breaks the Docker Desktop / WSL2
# bind-mount snapshot); restore on exit. fpm is force-recreated in the loop so the
# changed mount is re-snapshotted.
POOL="docker/fpm/pool.conf"
cp "$POOL" "$POOL.orig"
trap 'mv -f "$POOL.orig" "$POOL" 2>/dev/null || true' EXIT
sed "s/^pm.max_children = .*/pm.max_children = ${OCTANE_WORKERS}/" "$POOL.orig" > "$POOL"

for server in $SERVERS; do
  target=$(server_target "$server"); svcs=$(server_services "$server"); measure=$(server_measure "$server")
  echo "################ $server  (target=$target) ################"
  for workload in $WORKLOADS; do
    if cells_complete "$server" "$workload"; then
      echo "  -- $workload: complete, skipping"
      continue
    fi
    echo "  -- $workload"
    dc stop $APP_SERVICES >/dev/null 2>&1
    # fpm: force-recreate so the worker-count pool.conf change is re-snapshotted.
    if [ "$server" = fpm ]; then dc up -d --force-recreate $svcs >/dev/null 2>&1
    else dc up -d $svcs >/dev/null 2>&1; fi
    if ! wait_healthy $svcs; then
      echo "     UNHEALTHY — skipping $server/$workload" >&2
      dc stop $svcs >/dev/null 2>&1; continue
    fi
    # pinning self-check on the measured container
    cpuset=$(read_cpuset "$measure")
    pinning="unverified"; [ "$cpuset" = "$SUT_CPUSET" ] && pinning="verified"
    [ "$pinning" = "unverified" ] && echo "     ! cpuset='$cpuset' (expected $SUT_CPUSET) — results tagged pinning=unverified"
    # measured sweep — warm AT each concurrency (discarded) before its runs, so a
    # level isn't penalized by the previous level's state or residual cold-start
    # (fixes the order artifact where the first-measured concurrency reads high).
    for conc in $CONCURRENCIES; do
      dc run --rm wrk -t"$THREADS" -c"$conc" -d"${WARMUP}s" --timeout "$TIMEOUT" \
        "http://${target}:8000$(route_for "$workload")" >/dev/null 2>&1
      for run in $(seq 1 "$RUNS"); do
        run_cell "$server" "$workload" "$conc" "$run" "$target" "$pinning"
      done
    done
    # peak RSS for this (server,workload) — cgroup high-water mark (v2 or v1)
    rss=$(read_peak_rss "$measure")
    jq -n --arg server "$server" --arg workload "$workload" --argjson bytes "${rss:-0}" --arg pinning "$pinning" \
      '{server:$server, workload:$workload, peak_rss_bytes:$bytes, peak_rss_mib:(($bytes/1048576)|floor), pinning:$pinning}' \
      > "$RESULTS_DIR/${server}_${workload}_rss.json"
    printf "     peak RSS: %s MiB\n" "$(( ${rss:-0} / 1048576 ))"
    dc stop $svcs >/dev/null 2>&1
    sleep "$SETTLE"
  done
done

echo
echo "==> Done. $(ls "$RESULTS_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ') result files in $RESULTS_DIR/"
echo "    Next: python3 bench/aggregate.py  (builds RESULTS.md + docs/summary.json + docs/index.html)"
