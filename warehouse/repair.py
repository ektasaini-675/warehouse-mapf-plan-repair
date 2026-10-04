"""Plan repair (no global replanning).

Escalation ladder for a disrupted agent `a`:
  Level 1  self-repair      : re-plan only `a` against everybody else's existing plans
  Level 2  1 neighbour      : ask one nearby agent to yield (re-plan after `a`)
  Level 3  2 neighbours     : ask a pair of neighbours
  Level 4+ wider group      : the k nearest neighbours
  Fail     hold position    : `a` waits (parked) and retries every few steps

At every level, candidates that succeed are compared by the extra delay they
cause and the cheapest one is committed. A neighbour that "yields" simply
re-plans its remaining route around `a`'s new path (priority goes to `a`).
Neighbours are limited by Manhattan distance `cfg.neg_radius`.
"""
from itertools import combinations
from collections import defaultdict
from .planner import plan_waypoints


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def trim_len(plan):
    j = len(plan)
    while j > 1 and plan[j - 1] == plan[j - 2]:
        j -= 1
    return j


class Repairer:
    def __init__(self, sim):
        self.sim = sim
        self.n_plans = 0        # number of A* plan calls made for repair

    # ---------- helpers ----------
    def wps_of(self, a):
        # a finished agent that is asked to step aside only has to come back to its cell
        return a.waypoints[a.wp_idx:] if a.status == "active" else [a.pos]

    def plan_for(self, a, now):
        self.n_plans += 1
        s = self.sim
        return plan_waypoints(s.grid, s.res, a.id, a.pos, now, self.wps_of(a), s.horizon)

    def snapshot(self, a):
        return (a.plan, a.t0, a.park, dict(a.arrivals))

    def restore(self, a, s):
        a.plan, a.t0, a.park, arr = s
        a.arrivals = dict(arr)
        self.sim.res.add(a.id, a.plan, a.t0, a.park, track=False, force=False)

    def install(self, a, r, now, track=True, force=True):
        plan, arr = r
        a.plan, a.t0, a.park = plan, now, True
        self.sim.res.add(a.id, plan, now, True, track=track, force=force)
        if a.status == "active":
            a.arrivals = {a.wp_idx + i: t for i, t in enumerate(arr)}
            a.stuck_since = None

    def hold(self, a, now):
        """Could not repair: stay put (and block the cell for others)."""
        a.plan, a.t0, a.park, a.arrivals = [a.pos], now, True, {}
        if a.stuck_since is None:
            a.stuck_since = now
        self.sim.res.add(a.id, a.plan, now, True)

    # ---------- the ladder ----------
    def repair(self, aids, now):
        """Repair a list of disrupted agents. Returns {agent: level} (0 = failed)."""
        s = self.sim
        if s.cfg.mode == "full":
            return self.full_replan(now)
        queue, handled, seen = list(aids), {}, defaultdict(int)
        while queue:
            aid = queue.pop(0)
            a = s.agents[aid]
            if a.status in ("failed", "broken"):
                continue
            if seen[aid] >= 3:          # ping-pong guard: stop and just hold position
                self.hold(a, now)
                continue
            seen[aid] += 1
            handled[aid] = self.repair_one(a, now)
            for d in sorted(s.res.take_displaced()):     # cascade
                if d != aid and d not in queue:
                    queue.append(d)
        return handled

    def repair_one(self, a, now):
        if self.try_self(a, now):
            return 1
        g = self.negotiate(a, now)
        if g is not None:
            return 1 + len(g)
        self.hold(a, now)
        return 0

    def try_self(self, a, now):
        old = self.snapshot(a)
        self.sim.res.remove(a.id)
        r = self.plan_for(a, now)
        if r is not None:
            self.install(a, r, now)
            return True
        self.restore(a, old)
        return False

    def trial(self, a, group, now):
        """Try: `a` re-plans first, then each agent of `group` re-plans around it.
        Nothing is changed permanently. Returns (cost, new_plans) or None."""
        s = self.sim
        involved = [a] + group
        saved = {x.id: self.snapshot(x) for x in involved}
        for x in involved:
            s.res.remove(x.id)
        plans, ok = {}, True
        for x in involved:
            r = self.plan_for(x, now)
            if r is None:
                ok = False
                break
            plans[x.id] = r
            s.res.add(x.id, r[0], now, True, track=False, force=False)
        for x in involved:
            s.res.remove(x.id)
        for x in involved:
            self.restore(x, saved[x.id])
        if not ok:
            return None
        cost = 0.001 * (now + trim_len(plans[a.id][0]))
        for x in group:
            old_end = max(now, x.t0 + trim_len(saved[x.id][0]) - 1)
            new_end = now + trim_len(plans[x.id][0]) - 1
            cost += max(0, new_end - old_end)
        return cost, plans

    def negotiate(self, a, now):
        s, cfg = self.sim, self.sim.cfg
        cands = [o for o in s.agents.values()
                 if o.id != a.id and o.status in ("active", "done")
                 and manhattan(o.pos, a.pos) <= cfg.neg_radius]
        cands.sort(key=lambda o: (manhattan(o.pos, a.pos), o.id))
        cands = cands[:cfg.max_cands]
        for k in range(1, cfg.max_group + 1):
            if k == 1:
                groups = [[o] for o in cands]
            elif k == 2:
                groups = [list(g) for g in combinations(cands[:5], 2)]
            else:
                groups = [cands[:k]] if len(cands) >= k else []
            best = None
            for g in groups:
                out = self.trial(a, g, now)
                if out is not None and (best is None or out[0] < best[0]):
                    best = (out[0], g, out[1])
            if best is not None:
                _, g, plans = best
                involved = [a] + g
                for x in involved:
                    s.res.remove(x.id)
                for x in involved:
                    self.install(x, plans[x.id], now, track=False, force=False)
                return g
        return None

    # ---------- baseline for comparison ----------
    def full_replan(self, now):
        """Baseline: throw away every plan and re-plan all agents in id order."""
        s = self.sim
        for a in s.agents.values():
            s.res.remove(a.id)
        movable = []
        for a in s.agents.values():
            if a.status in ("broken", "failed"):
                s.res.add(a.id, a.plan, a.t0, a.park, track=False)
            else:
                movable.append(a)
        handled = {}
        for a in sorted(movable, key=lambda x: x.id):
            r = self.plan_for(a, now)
            if r is not None:
                self.install(a, r, now, track=False, force=False)
                handled[a.id] = 1
            else:
                self.hold(a, now)
                handled[a.id] = 0
        # a failed agent that had to hold position may sit on a path planned earlier:
        # fix those agents (self re-plan, else hold) so no stale plan survives
        for _ in range(5):
            disp = sorted(s.res.take_displaced())
            if not disp:
                break
            for d in disp:
                a = s.agents[d]
                if a.status in ("broken", "failed"):
                    continue
                if not self.try_self(a, now):
                    self.hold(a, now)
                handled[d] = handled.get(d, 1)
        return handled
