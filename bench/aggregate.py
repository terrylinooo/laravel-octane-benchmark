#!/usr/bin/env python3
"""
Aggregate raw benchmark cells into:
  - docs/summary.json   structured medians + ranges (machine-readable)
  - RESULTS.md          markdown tables (per-workload rps + latency percentiles, plus peak RSS)
  - docs/index.html     self-contained Chart.js page (works from file:// and gh-pages)

Pure stdlib. Reads results/*.json written by benchmark.sh.

Median across runs is the headline; min/max show the spread so noise is visible.
Cells include total wrk error counts so failed requests stay visible beside latency.
"""
import base64
import glob
import html
import json
import os
import shutil
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
        w = d.get("workers", 0)  # worker-count dimension (0 = pre-sweep data)
        if path.endswith("_rss.json"):
            rss[(d["server"], d["workload"], w)] = d
        elif "wrk" in d:
            cells.append(d)
            if manifest is None:
                manifest = d.get("manifest")
    return cells, rss, manifest


def aggregate(cells):
    # group runs by (server, workload, workers, concurrency)
    groups = defaultdict(list)
    for c in cells:
        groups[(c["server"], c["workload"], c.get("workers", 0), c["concurrency"])].append(c)

    out = {}
    for (server, workload, workers, conc), runs in groups.items():
        rps = [r["wrk"]["rps"] for r in runs]
        lat = {k: [r["wrk"]["latency_ms"][k] for r in runs if k in r["wrk"]["latency_ms"]]
               for k in ("p50", "p90", "p95", "p99")}
        errors = sum(sum(r["wrk"]["errors"].values()) for r in runs)
        row = {
            "server": server, "workload": workload, "workers": workers, "concurrency": conc,
            "runs": len(runs),
            "rps_median": round(statistics.median(rps), 1),
            "rps_min": round(min(rps), 1), "rps_max": round(max(rps), 1),
            "errors": errors,
        }
        for p, values in lat.items():
            if not values:
                row[f"{p}_median"] = None
                row[f"{p}_min"] = None
                row[f"{p}_max"] = None
                continue
            row[f"{p}_median"] = round(statistics.median(values), 2)
            row[f"{p}_min"] = round(min(values), 2)
            row[f"{p}_max"] = round(max(values), 2)
        out[(server, workload, workers, conc)] = row
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
FEATURED_SERVERS = ["swoole", "openswoole", "roadrunner", "frankenphp"]
SERVER_LABELS = {
    "swoole": "Swoole",
    "openswoole": "OpenSwoole",
    "roadrunner": "RoadRunner",
    "frankenphp": "FrankenPHP",
    "fpm": "PHP-FPM",
}


def logo_data_uri():
    """Embed readmes/laravel-bm.png as a base64 data URI so every generated page is
    self-contained (gh-pages publishes only docs/, not readmes/). '' if absent."""
    path = os.path.join(ROOT, "readmes", "laravel-bm.png")
    try:
        with open(path, "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""


def copy_social_image():
    """Publish the OG/Twitter image and the favicon into docs/ so the pages can
    reference them by URL instead of inlining them."""
    for name in ("laravel-bm.png", "favicon.ico"):
        try:
            shutil.copyfile(os.path.join(ROOT, "readmes", name), os.path.join(DOCS, name))
        except OSError:
            pass


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
    found_s = {s for (s, _, _, _) in agg}
    found_w = {w for (_, w, _, _) in agg}
    servers = [s for s in SERVER_ORDER if s in found_s] + sorted(found_s - set(SERVER_ORDER))
    workloads = [w for w in WORKLOAD_ORDER if w in found_w] + sorted(found_w - set(WORKLOAD_ORDER))
    groups = grouped(workloads)
    concs = sorted({c for (_, _, _, c) in agg})
    worker_counts = sorted({wk for (_, _, wk, _) in agg})

    # ---- summary.json ----
    summary = {
        "manifest": manifest,
        "servers": servers, "workloads": workloads, "groups": groups,
        "concurrencies": concs, "worker_counts": worker_counts,
        "cells": list(agg.values()),
        "rss": [
            {"server": s, "workload": w, "workers": wk, "peak_rss_mib": d["peak_rss_mib"]}
            for (s, w, wk), d in sorted(rss.items())
        ],
    }

    # CI provenance: link back to the workflow run that produced this report so the
    # dashboard can show "generated on X" + a download link. GitHub Actions sets
    # GITHUB_RUN_ID / GITHUB_REPOSITORY / GITHUB_SERVER_URL automatically; on a local
    # run they're absent and run_url stays null (the dashboard hides the link).
    _run_id = os.environ.get("GITHUB_RUN_ID")
    _repo = os.environ.get("GITHUB_REPOSITORY")
    _srv = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    summary["report"] = {
        "generated_at": (manifest or {}).get("generated_at"),
        "run_id": _run_id,
        "run_url": f"{_srv}/{_repo}/actions/runs/{_run_id}" if _run_id and _repo else None,
    }

    with open(os.path.join(DOCS, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    # ---- RESULTS.md ----
    lines = ["# Benchmark Results", ""]
    if manifest:
        lines += [
            f"PHP {manifest.get('php')} · Laravel {manifest.get('laravel')} · "
            f"Octane {manifest.get('octane')} · workers {manifest.get('worker_counts')} · "
            f"caps `{manifest.get('caps')}` · host `{manifest.get('host')}` "
            f"({manifest.get('nproc')} cores) · commit `{manifest.get('commit')}` · "
            f"{manifest.get('generated_at')}",
            "",
            "> Single-machine results. Treat them as **relative** (which server wins, and where "
            "it flips), not as absolute numbers for your hardware. Median of "
            f"{summary['cells'][0]['runs']} runs/cell; ranges show run-to-run spread.",
            "",
        ]

    def cell(s, w, wk, c):
        return agg.get((s, w, wk, c))

    multi = len(worker_counts) > 1
    for wk in worker_counts:
        if multi:
            lines += [f"# {wk} workers", ""]
        for grp in groups:
            lines += [f"## {grp['label']}", ""]
            for w in grp["workloads"]:
                lines.append(f"### `/bench/{w}`")
                lines.append("")
                header = "| Server | " + " | ".join(
                    f"c{c} rps | c{c} p50 | c{c} p90 | c{c} p95 | c{c} p99 | c{c} errors" for c in concs) + " |"
                sep = "|" + "---|" * (1 + 6 * len(concs))
                lines += [header, sep]
                for s in servers:
                    row = [f"`{s}`"]
                    for c in concs:
                        d = cell(s, w, wk, c)
                        if not d:
                            row += ["–", "–", "–", "–", "–", "–"]
                        else:
                            row += [
                                f"{d['rps_median']:.0f}",
                                f"{d['p50_median']:.1f}" if d.get("p50_median") is not None else "–",
                                f"{d['p90_median']:.1f}" if d.get("p90_median") is not None else "–",
                                f"{d['p95_median']:.1f}" if d.get("p95_median") is not None else "–",
                                f"{d['p99_median']:.1f}" if d.get("p99_median") is not None else "–",
                                str(d["errors"]),
                            ]
                    lines.append("| " + " | ".join(row) + " |")
                lines.append("")

        rss_wk = {(s, w): d for (s, w, w2), d in rss.items() if w2 == wk}
        if rss_wk:
            label = f" — {wk} workers" if multi else " — secondary metric"
            lines += [f"## Peak RSS (MiB){label}", "",
                      "Per-server memory high-water mark under load (shared OPcache counted once). "
                      "Octane keeps the framework resident per worker; FPM holds far less.", ""]
            header = "| Server | " + " | ".join(f"`{w}`" for w in workloads) + " |"
            sep = "|" + "---|" * (1 + len(workloads))
            lines += [header, sep]
            for s in servers:
                row = [f"`{s}`"]
                for w in workloads:
                    d = rss_wk.get((s, w))
                    row.append(str(d["peak_rss_mib"]) if d else "–")
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")

    lines += ["`errors` = total wrk connect/read/write/status/timeout errors recorded for that cell.", ""]
    with open(os.path.join(ROOT, "RESULTS.md"), "w") as fh:
        fh.write("\n".join(lines))

    # ---- HTML pages (self-contained: data + logo injected into the templates) ----
    here = os.path.dirname(__file__)
    data_js = json.dumps(summary)
    logo = logo_data_uri()
    copy_social_image()

    # Serve docs/ as pre-built static files: .nojekyll stops GitHub Pages from
    # running Jekyll over it (the pages are generated, not a Jekyll site).
    open(os.path.join(DOCS, ".nojekyll"), "w").close()

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
        server_label = SERVER_LABELS.get(s, s)
        page = (server_tpl.replace("/*__DATA__*/", data_js)
                          .replace("/*__LOGO__*/", logo)
                          .replace("/*__SERVER__*/", json.dumps(s))
                          .replace("/*__SERVER_LABEL__*/", html.escape(server_label))
                          .replace("/*__SERVER_PATH__*/", "/" + html.escape(s)))
        with open(os.path.join(DOCS, f"{s}.html"), "w") as fh:
            fh.write(page)

    pages = "index.html, " + ", ".join(f"{s}.html" for s in featured)
    print("Wrote docs/summary.json, RESULTS.md, docs/{" + pages + "}")
    print(f"  servers={servers}")
    print(f"  workloads={workloads}  concurrencies={concs}")


if __name__ == "__main__":
    main()
