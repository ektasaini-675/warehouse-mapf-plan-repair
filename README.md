# Multi-robot warehouse: plan repair under dynamic disruptions

Team: Ekta (B23CS1018), Tavishi Srivastava (B23CS1101), Shreekar (B23CS1069)

Python 3.9+. Install dependencies once:

    pip install -r requirements.txt        # matplotlib, pillow, reportlab

    python run_demo.py                      # scripted demo -> demo.gif + demo.html (interactive viewer)
    python run_experiments.py --quick       # small sweep (about a minute)
    python run_experiments.py               # full sweep + failure analysis -> results/
    python run_experiments.py --quick --out results_quick   # same, without touching results/
    python make_report.py                   # builds report.pdf from results/ (needs reportlab)

## Visualisation

`python run_demo.py` writes two files from the same simulation:

* `demo.gif` - plain animation (a GIF cannot be paused or rewound, so use the HTML viewer for that).
* `demo.html` - interactive viewer. Double-click it (or `open demo.html`); it works offline in any browser.

Both show the warehouse as a labelled 2D grid (x across the top, y down the left). Shelves are dark grey,
blocked cells are red with a white cross and their (x,y) printed in the cell, and a newly blocked cell gets a
gold outline for 3 steps. Each robot shows its ID inside its cell and a side panel lists every robot's cell.
Planned paths stay visible; a robot that was just re-planned has an orange ring and its previous plan is dashed grey.

### Controls of `demo.html`
| Action | Button | Keyboard |
|---|---|---|
| Pause / play | Pause / Play | `Space` or `K` |
| About 10 seconds back | `-10 s` | `J` or `Shift+Left` |
| About 10 seconds forward | `+10 s` | `L` or `Shift+Right` |
| One step back / forward | `1 step` buttons | `Left` / `Right` |
| Previous / next disruption | `prev event` / `next event` | `[` / `]` |
| Start / end | | `Home` / `End` |

"10 seconds" = 10 seconds of playback at the current speed (steps per second x speed). At the default
5 steps/s and 1x speed that is 50 steps; at 2x it is 100 steps (the button label shows the exact number).
You can also drag the slider (coloured ticks mark the disruptions), click an event in the list to jump to 3 steps
before it (paused) and then step forward, change the speed, or hover over a cell to see what is in it.
To inspect a disruption: press `]` (jumps to the step where it is handled), then use `Left`/`Right` to compare
before and after.

## Design
- `grid.py` grid + warehouse generator (`aisle=1` gives narrow corridors)
- `planner.py` Space-Time A*; reservation table with vertex, swap and parking reservations
- `repair.py` plan repair (never re-invokes the global planner) + full-replan baseline
- `sim.py` time-step simulator, disruption injection, failure detection, metrics
- `viz.py` GIF animation; `run_*.py` entry points

Initial plans: prioritised planning (agent 0 first). Each agent plans pickup -> drop-off legs in order
and parks at its last drop-off.

### Repair ladder (per disrupted agent)
1. Self-repair: re-plan only this agent against everyone else's existing plans.
2. Negotiate: ask 1 neighbour (Manhattan distance <= `neg_radius`) to yield, i.e. re-plan around the requester;
   then 2 neighbours, then the k nearest. Cheapest successful option (least extra delay) is committed.
3. Fail: hold position (parked) and retry every few steps; declared failed after `patience` steps.

### Disruptions
- block: a cell is blocked for a random duration
- break: a robot stops for N steps (or permanently); agents whose plans cross it are displaced
- emergency: an agent gets an extra high-priority waypoint inserted

### Metrics
- total time steps = sum over agents of completion time (makespan also reported)
- agents changed per disruption = agents whose future path differs before/after handling that event
  (`avg_changed_impactful` ignores disruptions that hit nobody)
- success = every agent completed all tasks; `survivors_completed` ignores permanently broken robots
- `dyn_density` = expected fraction of free cells blocked at any moment
- `collisions` is a self-check (should be 0)

## Known limitations
Prioritised planning is incomplete (fails for some priority orders / dense maps); no retry with other orders.
Agents that finish stay parked in their cell. Neighbours are chosen by distance only.
