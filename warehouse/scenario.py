"""Random task/agent generation."""
import random
from .grid import make_warehouse
from .agent import Agent


def _draw(pool, k, rng):
    """k items without replacement if possible, else with replacement."""
    pool = list(pool)
    if len(pool) >= k:
        return rng.sample(pool, k)
    return [rng.choice(pool) for _ in range(k)]


def build(p, seed):
    """p: dict of parameters. Returns (grid, agents)."""
    rng = random.Random(seed)
    grid = make_warehouse(p.get("w", 20), p.get("h", 20), aisle=p.get("aisle", 2))
    comp = sorted(grid.largest_component())
    n, k = p.get("n_agents", 10), p.get("n_tasks", 2)

    shelf_side = [c for c in comp
                  if any((c[0] + dx, c[1] + dy) in grid.static
                         for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))] or comp
    border = [c for c in comp if c[0] in (0, grid.w - 1) or c[1] in (0, grid.h - 1)] or comp

    starts = _draw(comp, n, rng)
    pickups = _draw(shelf_side, n * k, rng)
    ns = p.get("n_stations")
    if ns:   # few shared delivery stations -> contention (failure setting)
        stations = rng.sample(border, min(ns, len(border)))
        drops = [rng.choice(stations) for _ in range(n * k)]
    else:
        drops = _draw(border, n * k, rng)

    agents = []
    for i in range(n):
        tasks = [(pickups[i * k + j], drops[i * k + j]) for j in range(k)]
        agents.append(Agent(i, starts[i], tasks))
    return grid, agents
