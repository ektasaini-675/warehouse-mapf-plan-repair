"""Prepare the frames recorded by the simulator for display.

Used by both the GIF writer (viz.py) and the interactive HTML viewer (viz_html.py).
It only READS sim.frames / sim.records / sim.event_log; it never changes the simulation.
"""

TAB20 = ["#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c", "#98df8a", "#d62728", "#ff9896",
         "#9467bd", "#c5b0d5", "#8c564b", "#c49c94", "#e377c2", "#f7b6d2", "#7f7f7f", "#c7c7c7",
         "#bcbd22", "#dbdb8d", "#17becf", "#9edae5"]

NEW_BLOCK_TICKS = 3      # a freshly blocked cell is highlighted for this many steps


def agent_colors(sim):
    return {i: TAB20[i % 20] for i in sim.agents}


def prepare(sim):
    """Return a dict with grid info, per-frame display data and the list of disruption events."""
    frames = sim.frames
    out, prev_blocks, first_seen = [], set(), {}
    start_of = {}                       # agent -> frame index where its 'changed' highlight began
    prev_changed = set()
    for k, f in enumerate(frames):
        blocks = set(f["blocks"])
        for c in blocks - prev_blocks:
            first_seen[c] = k
        new_blocks = sorted(c for c in blocks if k - first_seen.get(c, -99) < NEW_BLOCK_TICKS)
        changed = set(f["changed"])
        for i in changed - prev_changed:
            start_of[i] = k
        old = {}
        for i in changed:
            s = start_of.get(i, k)
            if s >= 1:                  # path the agent had BEFORE the disruption was handled
                before = frames[s - 1]
                p = before["path"][i][max(0, f["t"] - before["t"]):]
                if len(p) > 1 and p != list(f["path"][i]):
                    old[i] = [list(c) for c in p]
        out.append(dict(
            t=f["t"],
            pos={i: list(c) for i, c in f["pos"].items()},
            status=dict(f["status"]),
            target={i: (list(c) if c else None) for i, c in f["target"].items()},
            path={i: [list(c) for c in p] for i, p in f["path"].items()},
            blocks=sorted(list(c) for c in blocks),
            new_blocks=[list(c) for c in new_blocks],
            changed=sorted(changed),
            old=old,
            msg=f["msg"]))
        prev_blocks, prev_changed = blocks, changed

    events = []
    for rec, (t, text) in zip(sim.records, sim.event_log):
        events.append(dict(t=rec["t"], kind=rec["kind"], text=text,
                           cell=list(rec["cell"]) if rec.get("cell") else None,
                           agent=rec.get("agent"), affected=rec["affected"],
                           changed=rec["changed_ids"], level=rec["max_level"]))
    return dict(w=sim.grid.w, h=sim.grid.h,
                static=sorted(list(c) for c in sim.grid.static),
                agents=sorted(sim.agents), colors=agent_colors(sim),
                frames=out, events=events)
