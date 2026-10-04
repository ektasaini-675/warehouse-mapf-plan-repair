"""Scripted demo: a blocked cell, a robot breakdown and an emergency task.
Usage: python run_demo.py            -> demo.gif (animation) and demo.html (interactive viewer:
                                       pause, +-10 s, step, jump to disruptions)
"""
from warehouse.scenario import build
from warehouse.sim import Simulator, Config, Event
from warehouse.viz import animate
from warehouse.viz_html import export_html

grid, agents = build(dict(n_agents=8, n_tasks=2), seed=4)
sim = Simulator(grid, agents, Config(record=True), seed=4)
sim.initial_plan()

# pick disruption cells that really lie on agents' planned paths
a0, a3 = sim.agents[0], sim.agents[3]
cell = next(c for c in (a0.pos_at(t) for t in range(10, 40)) if c != a0.pos_at(6))
events = [
    Event(6, "block", cell=cell, duration=14),
    Event(14, "break", agent=3, duration=12),
    Event(22, "emergency", agent=5, target=(10, 19)),
]
res = sim.run(events)
print("result:", {k: v for k, v in res.items() if k not in ("repair_cpu",)})
for r in sim.records:
    print(r["t"], r["kind"], "affected", r["affected"], "changed", r["changed_ids"], "level", r["max_level"])
animate(sim, "demo.gif", fps=5)
print("saved demo.gif with", len(sim.frames), "frames")
export_html(sim, "demo.html", fps=5)
print("saved demo.html (open it in any web browser)")
