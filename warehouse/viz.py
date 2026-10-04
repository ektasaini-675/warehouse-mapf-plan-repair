"""Animation of a recorded simulation (matplotlib -> GIF).

The grid is drawn cell by cell with coordinate labels, every agent shows its ID inside its
cell, and a side panel lists "agent -> (x, y)" for every time step. Freshly blocked cells
get a gold outline and a coordinate label; agents that were just re-planned get an orange
ring and their previous path is drawn dashed so the repair is visible.
For pause / +-10 s controls use the interactive viewer (viz_html.py).
"""
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle, Circle

from .vizdata import prepare


def animate(sim, out="demo.gif", fps=5, stride=1, dpi=80):
    grid = sim.grid
    prep = prepare(sim)
    frames = prep["frames"][::stride]
    color = prep["colors"]
    ids = prep["agents"]
    static = {tuple(c) for c in prep["static"]}

    fig = plt.figure(figsize=(10.6, 7.2))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.2, 1.35], left=0.04, right=0.99, top=0.88, bottom=0.04, wspace=0.06)
    ax = fig.add_subplot(gs[0])
    side = fig.add_subplot(gs[1])

    def draw(k):
        f = frames[k]
        ax.clear()
        side.clear()
        ax.set_xlim(-0.5, grid.w - 0.5)
        ax.set_ylim(grid.h - 0.5, -0.5)                         # y grows downwards
        ax.set_aspect("equal")
        ax.set_xticks(range(grid.w)); ax.set_yticks(range(grid.h))
        ax.set_xticks([i - .5 for i in range(grid.w + 1)], minor=True)
        ax.set_yticks([i - .5 for i in range(grid.h + 1)], minor=True)
        ax.tick_params(which="major", length=0, labelsize=6, labeltop=True, labelbottom=False, pad=1)
        ax.tick_params(which="minor", length=0)
        ax.grid(which="minor", color="#c8c8c8", lw=0.6)
        ax.set_facecolor("#fbfbfb")
        for s in ax.spines.values():
            s.set_color("#888888")
        for (x, y) in static:                                   # shelves (static obstacles)
            ax.add_patch(Rectangle((x - .5, y - .5), 1, 1, fc="#5b5b5b", ec="#444444", lw=0.6))
        newb = {tuple(c) for c in f["new_blocks"]}
        for (x, y) in f["blocks"]:                              # dynamic blocked cells
            fresh = (x, y) in newb
            ax.add_patch(Rectangle((x - .5, y - .5), 1, 1, fc="#e63946", ec="#ffd60a" if fresh else "#9d0208",
                                   lw=3.2 if fresh else 1, alpha=.92, zorder=3))
            ax.plot([x - .38, x + .38], [y - .38, y + .38], c="white", lw=1, zorder=4)
            ax.plot([x - .38, x + .38], [y + .38, y - .38], c="white", lw=1, zorder=4)
            ax.text(x, y + .42, f"{x},{y}", ha="center", va="bottom", fontsize=4.6, color="white",
                    weight="bold", zorder=5)
        for i, p in f["old"].items():                           # plan before the repair (dashed)
            ax.plot([c[0] for c in p], [c[1] for c in p], ls="--", c="#777777", lw=1.2, zorder=4)
        for i, p in f["path"].items():                          # current planned paths
            if f["status"][i] == "active" and len(p) > 1:
                ax.plot([c[0] for c in p], [c[1] for c in p], c=color[i], lw=1.6, alpha=.7, zorder=5)
        for i, c in f["target"].items():                        # next goal of each agent
            if c is not None:
                ax.add_patch(Rectangle((c[0] - .2, c[1] - .2), .4, .4, fc=color[i], ec="black", lw=.5, zorder=6))
        for i, (x, y) in f["pos"].items():
            st = f["status"][i]
            if st == "done":
                ax.add_patch(Circle((x, y), .38, fc=color[i], alpha=.35, zorder=7))
                ax.text(x, y, str(i), ha="center", va="center", fontsize=7, color="#444444", zorder=8)
            elif st in ("broken", "failed"):
                ax.add_patch(Circle((x, y), .42, fc="#222222", ec="#ff4d4d", lw=1.5, zorder=7))
                ax.plot([x - .3, x + .3], [y - .3, y + .3], c="#ff4d4d", lw=1.5, zorder=8)
                ax.plot([x - .3, x + .3], [y + .3, y - .3], c="#ff4d4d", lw=1.5, zorder=8)
                ax.text(x, y, str(i), ha="center", va="center", fontsize=7, color="white", weight="bold", zorder=9)
            else:
                ch = i in f["changed"]
                ax.add_patch(Circle((x, y), .4, fc=color[i], ec="#ff9f1c" if ch else "black",
                                    lw=3 if ch else .8, zorder=7))
                ax.text(x, y, str(i), ha="center", va="center", fontsize=8, weight="bold", zorder=8)
        n_done = sum(1 for s in f["status"].values() if s == "done")
        ax.set_title(f"t = {f['t']}    done {n_done}/{len(f['status'])}", fontsize=10, loc="left", pad=14)
        if f["msg"]:
            fig.text(0.04, 0.945, f["msg"], fontsize=9.5, weight="bold", color="white",
                     bbox=dict(boxstyle="round,pad=0.3", fc="#c1121f", ec="none"), va="center")

        # ---- side panel: which agent is in which cell ----
        side.set_xlim(0, 1); side.set_ylim(0, 1); side.axis("off")
        side.text(0, 0.995, "Agent  ->  cell (x,y)   goal", fontsize=8, weight="bold", va="top")
        per_col = 18
        ncol = max(1, math.ceil(len(ids) / per_col))
        fs = 7
        for n, i in enumerate(ids):
            col, row = divmod(n, per_col)
            x0 = col * (1.0 / ncol)
            y = 0.95 - row * 0.035
            x0_unused = None
            st, tg = f["status"][i], f["target"][i]
            goal = f"({tg[0]},{tg[1]})" if tg else ("done" if st == "done" else "-")
            tag = {"done": " ok", "broken": " BROKEN", "failed": " FAILED"}.get(st, "")
            col_txt = "#e76f00" if i in f["changed"] else ("#c1121f" if st in ("broken", "failed") else
                                                          ("#888888" if st == "done" else "black"))
            side.add_patch(Circle((x0 + .03, y), .012, fc=color[i], ec="black", lw=.4, transform=side.transAxes))
            side.text(x0 + .07, y, f"{i:>2} -> ({f['pos'][i][0]:>2},{f['pos'][i][1]:>2}) {goal}{tag}", fontsize=fs,
                      family="monospace", va="center", color=col_txt)
        legend = ["grey square  = shelf (static)", "red X cell    = dynamic block (x,y)",
                  "gold outline  = newly blocked", "orange ring   = just re-planned",
                  "solid line    = current plan", "dashed line   = plan before repair",
                  "small square  = next goal", "dark + red X   = broken robot"]
        for j, s in enumerate(legend):
            side.text(0, 0.30 - j * 0.035, s, fontsize=6.5, family="monospace", va="center", color="#333333")

    anim = FuncAnimation(fig, draw, frames=len(frames), interval=1000 // fps)
    anim.save(out, writer=PillowWriter(fps=fps), dpi=dpi)
    plt.close(fig)
