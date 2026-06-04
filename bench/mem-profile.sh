#!/usr/bin/env bash
#
# Idle (booted) memory profile for Laravel Octane.
#
# Answers: "how much RAM does each server use at N workers, and what does one MORE
# worker actually cost?" Boots each server at N workers (default 4/8/16/32), warms
# every worker (Octane boots the framework per worker), settles, then reads the
# container's resident WORKING SET from cgroup v1 memory.stat:
#
#     working_set = total_rss + total_shmem
#
# rss = private anon; shmem = shared memory incl. the OPcache SHM. Reading at the
# CONTAINER level (cgroup) counts shared OPcache pages ONCE — summing per-process
# RSS would double-count them. This is a PURE IDLE measurement: no load during the
# read (the warmup only exists to boot every worker, then stops).
#
# One result file per (server, N) -> results/mem/{server}_w{N}.json
# Build the report (linear fit: fixed overhead + marginal/worker):
#     python3 bench/mem_profile.py
#
# Usage:
#   ./bench/mem-profile.sh
#   MEM_SERVERS="swoole fpm" WORKER_COUNTS="4 8 16 32" ./bench/mem-profile.sh
set -uo pipefail
cd "$(dirname "$0")/.."

SERVERS="${MEM_SERVERS:-swoole openswoole roadrunner frankenphp fpm}"
WORKER_COUNTS="${WORKER_COUNTS:-4 8 16 32}"
WARMUP="${MEM_WARMUP:-4}"      # seconds of warmup load (boots every worker)
SETTLE="${MEM_SETTLE:-4}"      # seconds to settle before the idle read
THREADS="${THREADS:-2}"
OUT="results/mem"
APP_SERVICES="swoole openswoole roadrunner frankenphp fpm nginx"
POOL="docker/fpm/pool.conf"

dc(){ docker compose "$@"; }
server_target()   { case "$1" in fpm) echo nginx;;       *) echo "$1";; esac; }
server_services() { case "$1" in fpm) echo "fpm nginx";; *) echo "$1";; esac; }

mkdir -p "$OUT"

# We sed pm.max_children into pool.conf to size the FPM pool; restore it on exit.
cp "$POOL" "$POOL.orig"
trap 'mv -f "$POOL.orig" "$POOL" 2>/dev/null || true' EXIT

wait_healthy(){
  local want=$# svc ok
  for _ in $(seq 1 60); do
    ok=0
    for svc in "$@"; do [ "$(dc ps "$svc" --format '{{.Health}}' 2>/dev/null)" = healthy ] && ok=$((ok+1)); done
    [ "$ok" -eq "$want" ] && return 0; sleep 2
  done
  return 1
}

# echoes "rss shmem working_set usage" in MiB for the given service's container
read_ws_mib(){
  local svc="$1" stat rss shmem usage
  stat=$(dc exec -T "$svc" cat /sys/fs/cgroup/memory/memory.stat 2>/dev/null | tr -d '\r')
  rss=$(awk '/^total_rss /{print $2}'   <<<"$stat")
  shmem=$(awk '/^total_shmem /{print $2}' <<<"$stat")
  usage=$(dc exec -T "$svc" cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null | tr -d '\r')
  rss=${rss:-0}; shmem=${shmem:-0}; usage=${usage:-0}
  echo "$((rss/1048576)) $((shmem/1048576)) $(((rss+shmem)/1048576)) $((usage/1048576))"
}

echo "Servers: $SERVERS"
echo "Workers: $WORKER_COUNTS   (warmup ${WARMUP}s, settle ${SETTLE}s, idle read)"
echo

for server in $SERVERS; do
  target=$(server_target "$server"); svcs=$(server_services "$server"); measure="$server"
  echo "################ $server ################"
  for N in $WORKER_COUNTS; do
    dc stop $APP_SERVICES >/dev/null 2>&1
    if [ "$server" = fpm ]; then
      # Size the FPM pool by writing pm.max_children into the bind-mounted file
      # FROM the pristine copy via redirect (preserves the inode — `sed -i` swaps
      # it, which breaks the Docker Desktop / WSL2 bind-mount snapshot), then
      # --force-recreate so Docker re-snapshots the changed mount.
      sed "s/^pm.max_children = .*/pm.max_children = $N/" "$POOL.orig" > "$POOL"
      dc up -d --force-recreate $svcs >/dev/null 2>&1
    else
      OCTANE_WORKERS=$N dc up -d $svcs >/dev/null 2>&1
    fi
    if ! wait_healthy $svcs; then echo "  N=$N: UNHEALTHY — skipped" >&2; dc stop $svcs >/dev/null 2>&1; continue; fi
    # warm: round-robin needs > N requests so every worker boots the framework
    dc run --rm wrk -t"$THREADS" -c"$((N*2))" -d"${WARMUP}s" "http://${target}:8000/bench/hello" >/dev/null 2>&1
    sleep "$SETTLE"
    read -r rss shmem ws usage < <(read_ws_mib "$measure")
    procs=$(dc exec -T "$measure" sh -c 'ls /proc 2>/dev/null | grep -cE "^[0-9]+$"' 2>/dev/null | tr -d '\r')
    jq -n --arg s "$server" --argjson n "$N" --argjson rss "$rss" --argjson shmem "$shmem" \
       --argjson ws "$ws" --argjson usage "$usage" --argjson procs "${procs:-0}" \
       '{server:$s, workers:$n, rss_mib:$rss, shmem_mib:$shmem, working_set_mib:$ws, usage_mib:$usage, procs:$procs}' \
       > "$OUT/${server}_w${N}.json"
    printf "  N=%-2s  working_set=%4s MiB   (rss=%s shmem=%s · usage=%s · procs=%s)\n" "$N" "$ws" "$rss" "$shmem" "$usage" "${procs:-?}"
    dc stop $svcs >/dev/null 2>&1
    sleep 1
  done
done

mv -f "$POOL.orig" "$POOL" 2>/dev/null || true
echo
echo "Done. $(ls "$OUT"/*.json 2>/dev/null | wc -l | tr -d ' ') files in $OUT/."
echo "    Report: python3 bench/mem_profile.py  (fixed overhead + marginal MiB/worker)"
