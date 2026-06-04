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
import base64
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


# The three featured Octane servers that get a dedicated per-server report page
# (linked from the header menu). OpenSwoole shares Swoole's driver and FPM is the
# control, so they appear in the comparison but not as standalone reports.
FEATURED_SERVERS = ["swoole", "roadrunner", "frankenphp"]


def logo_data_uri():
    """Embed readmes/laravel-bm.png as a base64 data URI so every generated page is
    self-contained (gh-pages publishes only docs/, not readmes/). '' if absent."""
    path = os.path.join(ROOT, "readmes", "laravel-bm.png")
    try:
        with open(path, "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""


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

    # ---- HTML pages (self-contained: data + logo injected into the templates) ----
    here = os.path.dirname(__file__)
    data_js = json.dumps(summary)
    logo = logo_data_uri()

    # Comparison dashboard -> docs/index.html
    with open(os.path.join(here, "dashboard_template.html")) as fh:
        index_tpl = fh.read()
    index_html = index_tpl.replace("/*__DATA__*/", data_js).replace("/*__LOGO__*/", logo)
    with open(os.path.join(DOCS, "index.html"), "w") as fh:
        fh.write(index_html)

    # Per-server deep-report pages -> docs/{server}.html (featured servers only)
    featured = [s for s in FEATURED_SERVERS if s in servers]
    with open(os.path.join(here, "server_template.html")) as fh:
        server_tpl = fh.read()
    for s in featured:
        page = (server_tpl.replace("/*__DATA__*/", data_js)
                          .replace("/*__LOGO__*/", logo)
                          .replace("/*__SERVER__*/", json.dumps(s)))
        with open(os.path.join(DOCS, f"{s}.html"), "w") as fh:
            fh.write(page)

    pages = "index.html, " + ", ".join(f"{s}.html" for s in featured)
    print("Wrote docs/summary.json, RESULTS.md, docs/{" + pages + "}")
    print(f"  servers={servers}")
    print(f"  workloads={workloads}  concurrencies={concs}")


if __name__ == "__main__":
    main()
