#!/usr/bin/env python3
"""
Aggregate raw benchmark cells into:
  - docs/summary.json   structured medians + ranges (machine-readable)
  - RESULTS.md          markdown tables (per-workload rps + p99, plus peak RSS)
  - docs/index.html     self-contained Chart.js page (works from file:// and gh-pages)

Pure stdlib. Reads results/*.json written by benchmark.sh.

Median across runs is the headline; min/max show the spread so noise is visible.
Cells that recorded any wrk errors are flagged, not hidden.
"""
import glob
import json
import os
import statistics
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)


def load_cells():
    cells, rss, manifest = [], {}, None
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        with open(path) as fh:
            d = json.load(fh)
        if path.endswith("_rss.json"):
            rss[(d["server"], d["workload"])] = d
        elif "wrk" in d:
            cells.append(d)
            if manifest is None:
                manifest = d.get("manifest")
    return cells, rss, manifest


def aggregate(cells):
    # group runs by (server, workload, concurrency)
    groups = defaultdict(list)
    for c in cells:
        groups[(c["server"], c["workload"], c["concurrency"])].append(c)

    out = {}
    for (server, workload, conc), runs in groups.items():
        rps = [r["wrk"]["rps"] for r in runs]
        p50 = [r["wrk"]["latency_ms"]["p50"] for r in runs]
        p99 = [r["wrk"]["latency_ms"]["p99"] for r in runs]
        errors = sum(sum(r["wrk"]["errors"].values()) for r in runs)
        out[(server, workload, conc)] = {
            "server": server, "workload": workload, "concurrency": conc,
            "runs": len(runs),
            "rps_median": round(statistics.median(rps), 1),
            "rps_min": round(min(rps), 1), "rps_max": round(max(rps), 1),
            "p50_median": round(statistics.median(p50), 2),
            "p99_median": round(statistics.median(p99), 2),
            "p99_min": round(min(p99), 2), "p99_max": round(max(p99), 2),
            "errors": errors,
        }
    return out


# Workload taxonomy. Every workload belongs to exactly one group; the group both
# orders the display (overhead -> the CPU-bound trio -> I/O) and is rendered as a
# section header in RESULTS.md and the charts page.
WORKLOAD_ORDER = ["hello", "hash", "mandelbrot", "json", "db"]
WORKLOAD_GROUP = {
    "hello": "overhead",
    "hash": "cpu", "mandelbrot": "cpu", "json": "cpu",
    "db": "io",
}
GROUP_ORDER = ["overhead", "cpu", "io"]
GROUP_LABEL = {"overhead": "Overhead", "cpu": "CPU-bound", "io": "I/O"}


def grouped(workloads):
    """Ordered [{group, label, workloads}] for the present workloads. Within a
    group, the incoming workload order (WORKLOAD_ORDER) is preserved."""
    by_group = defaultdict(list)
    for w in workloads:
        by_group[WORKLOAD_GROUP.get(w, "other")].append(w)
    out = []
    for g in GROUP_ORDER + sorted(set(by_group) - set(GROUP_ORDER)):
        if g in by_group:
            out.append({"group": g, "label": GROUP_LABEL.get(g, g.title()),
                        "workloads": by_group[g]})
    return out


def main():
    cells, rss, manifest = load_cells()
    if not cells:
        print("No result cells found in results/. Run ./benchmark.sh first.")
        return
    agg = aggregate(cells)

    # Canonical display order (Octane servers first, fpm control last; workloads
    # by group, cheap -> expensive). Unknown keys fall to the end, first-seen.
    SERVER_ORDER = ["swoole", "openswoole", "roadrunner", "frankenphp", "fpm"]
    found_s = {s for (s, _, _) in agg}
    found_w = {w for (_, w, _) in agg}
    servers = [s for s in SERVER_ORDER if s in found_s] + sorted(found_s - set(SERVER_ORDER))
    workloads = [w for w in WORKLOAD_ORDER if w in found_w] + sorted(found_w - set(WORKLOAD_ORDER))
    groups = grouped(workloads)
    concs = sorted({c for (_, _, c) in agg})

    # ---- summary.json ----
    summary = {
        "manifest": manifest,
        "servers": servers, "workloads": workloads, "groups": groups,
        "concurrencies": concs,
        "cells": list(agg.values()),
        "rss": [
            {"server": s, "workload": w, "peak_rss_mib": d["peak_rss_mib"]}
            for (s, w), d in sorted(rss.items())
        ],
    }
    with open(os.path.join(DOCS, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    # ---- RESULTS.md ----
    lines = ["# Benchmark Results", ""]
    if manifest:
        lines += [
            f"PHP {manifest.get('php')} · Laravel {manifest.get('laravel')} · "
            f"Octane {manifest.get('octane')} · {manifest.get('workers')} workers · "
            f"caps `{manifest.get('caps')}` · host `{manifest.get('host')}` "
            f"({manifest.get('nproc')} cores) · commit `{manifest.get('commit')}` · "
            f"{manifest.get('generated_at')}",
            "",
            "> Single-machine results. Treat them as **relative** (which server wins, and where "
            "it flips), not as absolute numbers for your hardware. Median of "
            f"{summary['cells'][0]['runs']} runs/cell; ranges show run-to-run spread.",
            "",
        ]

    def cell(s, w, c):
        return agg.get((s, w, c))

    for grp in groups:
        lines += [f"## {grp['label']}", ""]
        for w in grp["workloads"]:
            lines.append(f"### `/bench/{w}`")
            lines.append("")
            header = "| Server | " + " | ".join(
                f"c{c} rps | c{c} p99 (ms)" for c in concs) + " |"
            sep = "|" + "---|" * (1 + 2 * len(concs))
            lines += [header, sep]
            for s in servers:
                row = [f"`{s}`"]
                for c in concs:
                    d = cell(s, w, c)
                    if not d:
                        row += ["–", "–"]
                    else:
                        flag = " ⚠️" if d["errors"] else ""
                        row += [f"{d['rps_median']:.0f}{flag}", f"{d['p99_median']:.1f}"]
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")

    if rss:
        lines += ["## Peak RSS (MiB) — secondary metric", "",
                  "Per-server memory high-water mark under load. Octane keeps the framework "
                  "resident across 8 workers; FPM holds far less. Useful for VPS sizing.", ""]
        header = "| Server | " + " | ".join(f"`{w}`" for w in workloads) + " |"
        sep = "|" + "---|" * (1 + len(workloads))
        lines += [header, sep]
        for s in servers:
            row = [f"`{s}`"]
            for w in workloads:
                d = rss.get((s, w))
                row.append(str(d["peak_rss_mib"]) if d else "–")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    lines += ["⚠️ = cell recorded wrk errors (non-2xx/timeout); its latency is not clean.", ""]
    with open(os.path.join(ROOT, "RESULTS.md"), "w") as fh:
        fh.write("\n".join(lines))

    # ---- index.html (self-contained: data embedded) ----
    html = INDEX_HTML.replace("/*__DATA__*/", json.dumps(summary))
    with open(os.path.join(DOCS, "index.html"), "w") as fh:
        fh.write(html)

    print(f"Wrote docs/summary.json, RESULTS.md, docs/index.html")
    print(f"  servers={servers}")
    print(f"  workloads={workloads}  concurrencies={concs}")


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Laravel Octane Benchmark</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body{font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
  .wrap{max-width:1000px;margin:0 auto;padding:32px 20px 80px}
  h1{font-size:26px;margin:0 0 4px} .sub{color:#9aa0a6;font-size:13px;margin-bottom:24px}
  .note{background:#1a1d24;border-left:3px solid #5b8def;padding:10px 14px;border-radius:4px;color:#c7ccd1;font-size:13px;margin:18px 0}
  h2{font-size:18px;margin:34px 0 6px;border-bottom:1px solid #2a2e37;padding-bottom:6px}
  h2.group{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#5b8def;border-color:#5b8def33;margin-top:44px}
  h3{font-size:16px;margin:22px 0 6px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  @media(max-width:720px){.grid{grid-template-columns:1fr}}
  .card{background:#161922;border:1px solid #2a2e37;border-radius:8px;padding:14px}
  .ct{font-size:13px;color:#9aa0a6;margin-bottom:8px}
  table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}
  th,td{border:1px solid #2a2e37;padding:5px 8px;text-align:right} th:first-child,td:first-child{text-align:left}
  code{background:#222631;padding:1px 5px;border-radius:3px}
</style>
</head>
<body><div class="wrap">
<h1>Laravel Octane Benchmark</h1>
<div class="sub" id="meta"></div>
<div class="note">Single-machine results — read them as <b>relative</b> (which server wins, and where it flips), not as absolute numbers for your hardware. Headline metric is <b>p99 latency</b> across a concurrency sweep; throughput and peak RSS shown alongside. Median of N runs/cell.</div>
<div id="charts"></div>
<h2>Peak RSS (MiB)</h2><div class="card"><div id="rss"></div></div>
</div>
<script>
const DATA = /*__DATA__*/;
const COLORS = {swoole:'#4ade80',openswoole:'#22d3ee',roadrunner:'#f59e0b',frankenphp:'#a78bfa',fpm:'#f87171'};
const m = DATA.manifest||{};
document.getElementById('meta').textContent =
  `PHP ${m.php} · Laravel ${m.laravel} · Octane ${m.octane} · ${m.workers} workers · caps ${m.caps} · ${m.host} · commit ${m.commit} · ${m.generated_at}`;
const cell=(s,w,c)=>DATA.cells.find(x=>x.server===s&&x.workload===w&&x.concurrency===c);
function lineChart(canvas,w,metric,label){
  const ds=DATA.servers.map(s=>({label:s,borderColor:COLORS[s]||'#888',backgroundColor:COLORS[s]||'#888',
    tension:.2,data:DATA.concurrencies.map(c=>{const d=cell(s,w,c);return d?d[metric]:null;})}));
  new Chart(canvas,{type:'line',data:{labels:DATA.concurrencies.map(c=>'c'+c),datasets:ds},
    options:{plugins:{legend:{labels:{color:'#c7ccd1',boxWidth:12}}},
      scales:{x:{ticks:{color:'#9aa0a6'},grid:{color:'#222'}},
        y:{title:{display:true,text:label,color:'#9aa0a6'},ticks:{color:'#9aa0a6'},grid:{color:'#222'},beginAtZero:true}}}});
}
const root=document.getElementById('charts');
const GROUPS=DATA.groups||[{label:'',workloads:DATA.workloads}];
for(const grp of GROUPS){
  if(grp.label){const gh=document.createElement('h2');gh.className='group';gh.textContent=grp.label;root.appendChild(gh);}
  for(const w of grp.workloads){
    const h=document.createElement('h3');h.innerHTML='<code>/bench/'+w+'</code>';root.appendChild(h);
    const g=document.createElement('div');g.className='grid';
    const c1=document.createElement('div');c1.className='card';c1.innerHTML='<div class="ct">p99 latency (ms) — lower is better</div><canvas></canvas>';
    const c2=document.createElement('div');c2.className='card';c2.innerHTML='<div class="ct">throughput (req/s) — higher is better</div><canvas></canvas>';
    g.appendChild(c1);g.appendChild(c2);root.appendChild(g);
    lineChart(c1.querySelector('canvas'),w,'p99_median','p99 ms');
    lineChart(c2.querySelector('canvas'),w,'rps_median','req/s');
  }
}
// RSS table
let t='<table><tr><th>Server</th>'+DATA.workloads.map(w=>'<th>'+w+'</th>').join('')+'</tr>';
for(const s of DATA.servers){t+='<tr><td>'+s+'</td>'+DATA.workloads.map(w=>{
  const r=DATA.rss.find(x=>x.server===s&&x.workload===w);return '<td>'+(r?r.peak_rss_mib:'–')+'</td>';}).join('')+'</tr>';}
document.getElementById('rss').innerHTML=t+'</table>';
</script>
</body></html>"""


if __name__ == "__main__":
    main()
