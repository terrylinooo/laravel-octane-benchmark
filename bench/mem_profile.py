#!/usr/bin/env python3
"""
Build the idle-memory report from results/mem/*.json (written by mem-profile.sh).

Per server: the booted (idle) resident working set at each worker count, the naive
average (working_set / N), and a linear fit

    working_set(N) = fixed + marginal * N

that separates the FIXED cost (master + framework + shared OPcache, independent of
worker count) from the MARGINAL cost of one more worker. The naive average is
misleading on its own: it falls as N grows only because the fixed cost is amortized
over more workers, not because a worker got cheaper. Pure stdlib.

Outputs MEM_RESULTS.md and results/mem/summary.json.
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEM = os.path.join(ROOT, "results", "mem")


def lin_fit(xs, ys):
    """Least-squares fit y = intercept + slope*x; returns (intercept, slope, r2)."""
    n = len(xs)
    if n < 2:
        return (ys[0] if ys else 0.0), 0.0, 1.0
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx else 0.0
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot else 1.0
    return intercept, slope, r2


def main():
    rows = {}
    for p in sorted(glob.glob(os.path.join(MEM, "*.json"))):
        if p.endswith("summary.json"):
            continue
        d = json.load(open(p))
        rows.setdefault(d["server"], []).append(d)
    if not rows:
        print("No results in results/mem/. Run ./bench/mem-profile.sh first.")
        return

    SERVER_ORDER = ["swoole", "openswoole", "roadrunner", "frankenphp", "fpm"]
    servers = [s for s in SERVER_ORDER if s in rows] + [s for s in rows if s not in SERVER_ORDER]

    out = [
        "# Octane idle memory — RAM by worker count",
        "",
        "Booted (idle) resident **working set** per container = cgroup `total_rss + "
        "total_shmem` (shared OPcache counted once). Measured with **no load**, after "
        "warming every worker so the framework is booted in each.",
        "",
        "- **naive avg** = working_set / N. Falls as N grows because the fixed cost is "
        "spread over more workers — not because a worker got cheaper.",
        "- **marginal/worker** = slope of `working_set(N) = fixed + marginal·N`. The real "
        "cost of one more worker. **fixed** = master + framework + shared OPcache.",
        "",
    ]
    summary = []
    for s in servers:
        rs = sorted(rows[s], key=lambda r: r["workers"])
        out += [f"## `{s}`", "",
                "| workers | working set (MiB) | rss | shmem | naive avg /N (MiB) |",
                "|---|---|---|---|---|"]
        for r in rs:
            out.append(f"| {r['workers']} | **{r['working_set_mib']}** | {r['rss_mib']} | "
                       f"{r['shmem_mib']} | {r['working_set_mib'] / r['workers']:.1f} |")
        xs = [r["workers"] for r in rs]
        ys = [r["working_set_mib"] for r in rs]
        fixed, marg, r2 = lin_fit(xs, ys)
        out += ["", f"Linear fit: **fixed ≈ {fixed:.0f} MiB**, "
                    f"**marginal ≈ {marg:.1f} MiB/worker** (R² = {r2:.3f}).", ""]
        summary.append((s, fixed, marg, r2))

    out += ["## Summary — marginal cost per worker", "",
            "| server | fixed overhead (MiB) | marginal MiB/worker | R² |",
            "|---|---|---|---|"]
    for s, fixed, marg, r2 in summary:
        out.append(f"| `{s}` | {fixed:.0f} | {marg:.1f} | {r2:.3f} |")
    out.append("")

    report = "\n".join(out)
    with open(os.path.join(ROOT, "MEM_RESULTS.md"), "w") as fh:
        fh.write(report)
    with open(os.path.join(MEM, "summary.json"), "w") as fh:
        json.dump([{"server": s, "fixed_mib": round(f, 1),
                    "marginal_mib_per_worker": round(m, 1), "r2": round(r, 4)}
                   for s, f, m, r in summary], fh, indent=2)
    print(report)
    print(f"\nWrote MEM_RESULTS.md and {os.path.relpath(MEM, ROOT)}/summary.json")


if __name__ == "__main__":
    main()
