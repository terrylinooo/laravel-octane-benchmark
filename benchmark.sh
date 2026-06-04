#!/usr/bin/env bash
#
# Laravel Octane benchmark — reproducible crossover harness.
#
# Runs ONE app server at a time (others stopped), sweeps concurrency, and writes
# one JSON result per cell with an embedded manifest. The whole point is fairness:
#   * each server gets exactly 4 pinned cores (cpuset 0-3), wrk gets cores 4-7
#   * 8 workers everywhere, opcache + production parity, stateless endpoints
#   * latency percentiles (p50/p99) from wrk are the headline metric
#   * peak RSS (cgroup v1 memory.max_usage_in_bytes) is captured per (server,workload)
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
CONCURRENCIES="${CONCURRENCIES:-8 32 128}"
RUNS="${RUNS:-3}"
DURATION="${DURATION:-30}"     # measured seconds per run
WARMUP="${WARMUP:-10}"         # discarded warmup seconds per (server,workload)
THREADS="${THREADS:-4}"
SETTLE="${SETTLE:-3}"          # teardown settle delay between (server,workload)
RESULTS_DIR="${RESULTS_DIR:-results}"
APP_SERVICES="swoole openswoole roadrunner frankenphp fpm nginx"

dc() { docker compose "$@"; }

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
    --arg commit "$commit" --arg host "$host" --arg nproc "$(nproc)" \
    --arg date "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson workers 8 \
    --arg caps "cpus=4,cpuset=0-3,mem=512m" \
    --arg wrk "wrk -t${THREADS} -d${DURATION}s --latency" \
    '{php:$php, laravel:$laravel, octane:$octane, workers:$workers, caps:$caps,
      commit:$commit, host:$host, nproc:($nproc|tonumber), wrk_cmd:$wrk, generated_at:$date}'
}

# ---- one wrk run -> writes a cell file ----------------------------------------
run_cell() {
  local server="$1" workload="$2" conc="$3" run="$4" target="$5" pinning="$6"
  local route out wrkjson f
  f="$RESULTS_DIR/${server}_${workload}_c${conc}_r${run}.json"
  [ -f "$f" ] && { echo "      c${conc} r${run}: cached"; return 0; }
  route=$(route_for "$workload")
  out=$(dc run --rm wrk -t"$THREADS" -c"$conc" -d"${DURATION}s" --latency -s /report.lua \
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
    dc up -d $svcs >/dev/null 2>&1
    if ! wait_healthy $svcs; then
      echo "     UNHEALTHY — skipping $server/$workload" >&2
      dc stop $svcs >/dev/null 2>&1; continue
    fi
    # pinning self-check on the measured container
    cpuset=$(dc exec -T "$measure" cat /sys/fs/cgroup/cpuset/cpuset.cpus 2>/dev/null | tr -d '\r')
    pinning="unverified"; [ "$cpuset" = "0-3" ] && pinning="verified"
    [ "$pinning" = "unverified" ] && echo "     ! cpuset='$cpuset' (expected 0-3) — results tagged pinning=unverified"
    # warm (discarded)
    dc run --rm wrk -t"$THREADS" -c32 -d"${WARMUP}s" "http://${target}:8000$(route_for "$workload")" >/dev/null 2>&1
    # measured sweep
    for conc in $CONCURRENCIES; do
      for run in $(seq 1 "$RUNS"); do
        run_cell "$server" "$workload" "$conc" "$run" "$target" "$pinning"
      done
    done
    # peak RSS for this (server,workload) — cgroup v1 high-water mark
    rss=$(dc exec -T "$measure" cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null | tr -d '\r')
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
