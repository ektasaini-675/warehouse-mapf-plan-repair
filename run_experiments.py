"""Experiments. Usage:
    python run_experiments.py --quick     (small, ~1 min)
    python run_experiments.py             (full sweep)
Outputs CSVs and PNG plots into ./results
"""
import argparse, csv, os, time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from warehouse.scenario import build
from warehouse.sim import Simulator, Config, EventParams

BASE = dict(w=20, h=20, aisle=2, n_agents=10, n_tasks=2, dyn_density=0.0, n_breaks=2,
            n_emerg=2, mean_dur=10, perm_break=False, n_stations=None, neg_radius=8,
            mode="local", max_time=400)


def run_one(p):
    q = {**BASE, **p}
    grid, agents = build(q, q["seed"])
    cfg = Config(neg_radius=q["neg_radius"], mode=q["mode"], max_time=q["max_time"])
    evp = EventParams(q["dyn_density"], q["n_breaks"], q["n_emerg"], q["mean_dur"], q["perm_break"])
    sim = Simulator(grid, agents, cfg, evp, q["seed"])
    t0 = time.time()
    r = sim.run()
    r["wall"] = time.time() - t0
    r["levels"] = dict(Counter(x["max_level"] for x in sim.records if x["affected"] > 0))
    return {**q, **r}


def run_all(params, workers):
    if workers > 1:
        with ProcessPoolExecutor(workers) as ex:
            return list(ex.map(run_one, params, chunksize=2))
    return [run_one(p) for p in params]


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def save_csv(rows, path):
    keys = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)


def plot_sweep(rows, outdir, xs_agents, xs_dens):
    def agg(mode, key, fx, fy, ok_only=False):
        d = defaultdict(list)
        for r in rows:
            if r["mode"] == mode and (r["completed"] or not ok_only):
                d[(r["n_agents"], r["dyn_density"])].append(r[key])
        return d
    metrics = [("sum_time", "Total time steps (sum over agents, successful runs)", True),
               ("avg_changed_impactful", "Agents re-planned per disruption", False),
               ("completed", "Success rate", False)]
    for key, title, ok_only in metrics:
        fig, axs = plt.subplots(1, 2, figsize=(11, 4))
        for mode, ls in (("local", "-"), ("full", "--")):
            d = agg(mode, key, None, None, ok_only)
            for dens in xs_dens:
                axs[0].plot(xs_agents, [mean(d[(n, dens)]) for n in xs_agents], ls, marker="o",
                            label=f"{mode}, dens={dens:.0%}")
            for n in xs_agents:
                axs[1].plot(xs_dens, [mean(d[(n, de)]) for de in xs_dens], ls, marker="o",
                            label=f"{mode}, n={n}")
        axs[0].set_xlabel("number of agents"); axs[1].set_xlabel("dynamic obstacle density")
        for a in axs:
            a.set_ylabel(title); a.grid(alpha=.3)
        axs[0].legend(fontsize=6); axs[1].legend(fontsize=6)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, f"{key}.png"), dpi=130)
        plt.close(fig)


FAIL_SETTINGS = [
    ("baseline (20 agents, 3% obstacles)", dict(n_agents=20, dyn_density=0.03)),
    ("very high agent density (12x12, 20 agents)", dict(w=12, h=12, n_agents=20, dyn_density=0.03)),
    ("very high agent count (35 agents, 20x20)", dict(n_agents=35, dyn_density=0.03)),
    ("narrow 1-wide aisles (20 agents)", dict(aisle=1, n_agents=20, dyn_density=0.03)),
    ("very high obstacle density (12%)", dict(n_agents=15, dyn_density=0.12)),
    ("shared delivery stations (only 3)", dict(n_agents=15, n_stations=3)),
    ("permanent breakdowns (3 robots)", dict(n_agents=15, n_breaks=3, perm_break=True)),
    ("many simultaneous emergencies (10)", dict(n_agents=15, n_emerg=10, n_breaks=0)),
    ("no negotiation radius (r=0), 8% obstacles", dict(n_agents=15, dyn_density=0.08, neg_radius=0)),
    ("small negotiation radius (r=2), 8% obstacles", dict(n_agents=15, dyn_density=0.08, neg_radius=2)),
]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default="results")
    ap.add_argument("--skip-sweep", action="store_true", help="only run the failure analysis")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    seeds = range(4) if args.quick else range(10)
    agents_axis = [5, 10, 20] if args.quick else [5, 10, 15, 20, 25]
    dens_axis = [0.0, 0.03, 0.06] if args.quick else [0.0, 0.02, 0.04, 0.06, 0.08]

    if not args.skip_sweep:
        # ---- Experiment A: agents x density, local repair vs full replanning ----
        params = [dict(n_agents=n, dyn_density=d, seed=s, mode=m)
                  for m in ("local", "full") for n in agents_axis for d in dens_axis for s in seeds]
        t0 = time.time()
        rows = run_all(params, args.workers)
        for r in rows:
            r["levels"] = str(r["levels"]); r["fail_reasons"] = str(r["fail_reasons"])
        save_csv(rows, os.path.join(args.out, "sweep.csv"))
        plot_sweep(rows, args.out, agents_axis, dens_axis)
        print(f"sweep done in {time.time() - t0:.0f}s")
        print("\nmode  agents  dens  success  sum_time  avg_changed(impactful)")
        for m in ("local", "full"):
            for n in agents_axis:
                for d in dens_axis:
                    sub = [r for r in rows if r["mode"] == m and r["n_agents"] == n and r["dyn_density"] == d]
                    ok = [r for r in sub if r["completed"]]
                    print(f"{m:5} {n:6} {d:5.2f} {len(ok):3}/{len(sub):<3} "
                          f"{mean(r['sum_time'] for r in ok):9.1f} "
                          f"{mean(r['avg_changed_impactful'] for r in sub):10.2f} ")

    # ---- Experiment B: failure settings ----
    fseeds = range(5) if args.quick else range(10)
    params = [dict(seed=s, setting=name, **kw) for name, kw in FAIL_SETTINGS for s in fseeds]
    frows = run_all(params, args.workers)
    table = []
    print("\nFAILURE ANALYSIS")
    for name, _ in FAIL_SETTINGS:
        sub = [r for r in frows if r["setting"] == name]
        reasons = Counter()
        for r in sub:
            reasons.update(r["fail_reasons"])
        row = dict(setting=name, runs=len(sub),
                   completed=sum(r["completed"] for r in sub),
                   survivors_completed=sum(r["survivors_completed"] for r in sub),
                   agents_done=round(mean(r["n_done"] / r["n_agents"] for r in sub), 2),
                   avg_changed=round(mean(r["avg_changed_impactful"] for r in sub), 2),
                   collisions=sum(r["collisions"] for r in sub),
                   reasons=dict(reasons))
        table.append(row)
        print(row)
    save_csv(table, os.path.join(args.out, "failures.csv"))
