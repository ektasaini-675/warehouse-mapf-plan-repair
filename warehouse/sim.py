"""Simulator: executes plans step by step, injects disruptions, collects metrics."""
import random
import time
from collections import defaultdict, Counter
from dataclasses import dataclass

from .planner import ResTable, plan_waypoints
from .repair import Repairer


@dataclass
class Config:
    neg_radius: int = 8        # how far (Manhattan) an agent can ask neighbours for help
    max_group: int = 3         # max number of neighbours asked to yield at once
    max_cands: int = 8
    patience: int = 30         # steps an agent may stay stuck before it is declared failed
    retry_every: int = 4
    mode: str = "local"        # "local" = our plan repair, "full" = baseline replan-everything
    max_time: int = 400
    record: bool = False       # keep frames for the animation


@dataclass
class Event:
    t: int
    kind: str                  # block | break | emergency
    cell: tuple = None
    agent: int = None
    duration: int = 10
    target: tuple = None
    permanent: bool = False


@dataclass
class EventParams:
    dyn_density: float = 0.0   # avg. fraction of free cells blocked at any moment
    n_breaks: int = 0
    n_emerg: int = 0
    mean_dur: int = 10
    perm_break: bool = False


class Simulator:
    def __init__(self, grid, agents, cfg=None, ev_params=None, seed=0):
        self.grid = grid
        self.agents = {a.id: a for a in agents}
        self.cfg = cfg or Config()
        self.evp = ev_params or EventParams()
        self.rng = random.Random(seed * 7919 + 13)
        self.res = ResTable()
        self.repairer = Repairer(self)
        self.horizon = 3 * (grid.w + grid.h) + 40
        self.comp = sorted(grid.largest_component())
        self.records, self.frames, self.event_log = [], [], []
        self.collisions = 0
        self.recoveries = defaultdict(list)
        self.planned = False
        self.timeout = False
        self.recent = {}
        self.t = 0
        self.cpu_repair = 0.0

    # ---------- planning ----------
    def initial_plan(self):
        """Prioritised planning: agent 0 plans first, agent 1 plans around it, ..."""
        for a in sorted(self.agents.values(), key=lambda x: x.id):
            r = plan_waypoints(self.grid, self.res, a.id, a.start, 0, a.waypoints, self.horizon)
            if r is None:
                a.status, a.fail_reason = "failed", "initial_plan"
                a.plan, a.t0, a.park, a.arrivals = [a.pos], 0, True, {}
                self.res.add(a.id, a.plan, 0, True)
            else:
                self.repairer.install(a, r, 0)
        disp = self.res.take_displaced()
        if disp:
            self.repairer.repair(sorted(disp), 0)
        for a in self.agents.values():
            n = len(a.waypoints)
            a.initial_finish = a.arrivals.get(n - 1, 0) if a.status == "active" else None
        self.planned = True

    # ---------- disruption generation ----------
    def gen_events(self):
        p, rng = self.evp, self.rng
        fin = [a.initial_finish for a in self.agents.values() if a.initial_finish is not None]
        horizon = max(max(fin, default=10), 10)
        ev = []
        n_block = round(p.dyn_density * len(self.comp) * horizon / p.mean_dur)
        for _ in range(n_block):
            d = rng.randint(max(2, p.mean_dur // 2), p.mean_dur * 3 // 2)
            ev.append(Event(rng.randint(1, horizon), "block", cell=rng.choice(self.comp), duration=d))
        ids = sorted(self.agents)
        for _ in range(p.n_breaks):
            ev.append(Event(rng.randint(1, horizon), "break", agent=rng.choice(ids),
                            duration=rng.randint(p.mean_dur // 2 + 1, p.mean_dur * 2),
                            permanent=p.perm_break))
        for _ in range(p.n_emerg):
            ev.append(Event(rng.randint(1, horizon), "emergency", agent=rng.choice(ids),
                            target=rng.choice(self.comp)))
        return ev

    # ---------- helpers ----------
    def sig(self, a, now):
        """Future path of agent from `now` (trailing waits trimmed) -- used to detect changes."""
        seg = a.plan[max(0, now - a.t0):]
        j = len(seg)
        while j > 1 and seg[j - 1] == seg[j - 2]:
            j -= 1
        return tuple(seg[:j])

    def hits(self, a, cell, now, end):
        if a.status == "failed":
            return False
        for i in range(max(0, now - a.t0), len(a.plan)):
            if a.t0 + i >= end:
                break
            if a.plan[i] == cell:
                return True
        return a.park and a.plan[-1] == cell and a.t0 + len(a.plan) - 1 < end

    def occupied_now(self, cell):
        return any(a.pos == cell for a in self.agents.values())

    # ---------- event handling ----------
    def _finish_record(self, rec, before, affected, handled, now, t_start):
        changed = [i for i, a in self.agents.items() if self.sig(a, now) != before[i]]
        for i in changed:
            self.recent[i] = now
        rec.update(affected=len(affected), changed=len(changed), changed_ids=changed,
                   max_level=max(handled.values(), default=0),
                   success=all(v > 0 for v in handled.values()),
                   cpu=time.perf_counter() - t_start)
        self.cpu_repair += rec["cpu"]
        self.records.append(rec)

    def handle_event(self, ev, now):
        t_start = time.perf_counter()
        before = {i: self.sig(a, now) for i, a in self.agents.items()}
        rec = {"t": now, "kind": ev.kind}
        affected = []
        label = ""
        if ev.kind == "block":
            cell = ev.cell
            if cell is None or self.occupied_now(cell):
                return
            end = now + ev.duration
            self.res.blocks[cell] = max(self.res.blocks.get(cell, -1), end)
            affected = [i for i, a in sorted(self.agents.items()) if self.hits(a, cell, now, end)]
            rec["cell"] = cell
            label = f"BLOCKED {cell} for {ev.duration} steps"
        elif ev.kind == "break":
            a = self.agents.get(ev.agent)
            if a is None or a.status != "active":
                return
            if ev.permanent:
                a.status, a.fail_reason = "failed", "permanent_breakdown"
                a.plan, a.t0, a.park = [a.pos], now, True
            else:
                a.status, a.recover_t = "broken", now + ev.duration
                a.plan, a.t0, a.park = [a.pos] * (ev.duration + 1), now, False
                self.recoveries[a.recover_t].append(a.id)
            a.arrivals = {}
            self.res.add(a.id, a.plan, now, a.park)      # forced: robot physically sits here
            # every other agent whose plan used this cell while it is down gets displaced
            affected = [i for i in sorted(self.res.take_displaced()) if i != a.id]
            rec["agent"] = a.id
            label = f"AGENT {a.id} BROKE DOWN" + (" (permanent)" if ev.permanent else f" for {ev.duration} steps")
        elif ev.kind == "emergency":
            a = self.agents.get(ev.agent)
            if a is None or a.status != "active":
                return
            a.waypoints.insert(a.wp_idx, ev.target)
            a.arrivals = {}
            affected = [a.id]
            rec["agent"] = a.id
            label = f"EMERGENCY task for agent {a.id} at {ev.target}"
        handled = self.repairer.repair(affected, now) if affected else {}
        if ev.kind == "emergency":
            a = self.agents[ev.agent]
            rec["emerg_response"] = (a.arrivals[a.wp_idx] - now) if a.wp_idx in a.arrivals else None
        self._finish_record(rec, before, affected, handled, now, t_start)
        self.event_log.append((now, label + f" -> {rec['changed']} agent(s) re-planned"))

    def handle_recovery(self, aid, now):
        t_start = time.perf_counter()
        before = {i: self.sig(a, now) for i, a in self.agents.items()}
        a = self.agents[aid]
        a.status, a.recover_t = "active", None
        handled = self.repairer.repair([aid], now)
        rec = {"t": now, "kind": "recovery", "agent": aid}
        self._finish_record(rec, before, [aid], handled, now, t_start)
        self.event_log.append((now, f"AGENT {aid} RECOVERED"))

    def retry_stuck(self, now):
        for a in sorted(self.agents.values(), key=lambda x: x.id):
            if a.status != "active" or a.stuck_since is None:
                continue
            waited = now - a.stuck_since
            if waited > self.cfg.patience:
                a.status, a.fail_reason = "failed", "stuck"
            elif waited > 0 and waited % self.cfg.retry_every == 0:
                self.repairer.repair([a.id], now)

    # ---------- execution ----------
    def process_arrivals(self, t):
        for a in self.agents.values():
            if a.status != "active":
                continue
            while a.wp_idx < len(a.waypoints) and a.arrivals.get(a.wp_idx) == t:
                a.wp_idx += 1
            if a.wp_idx >= len(a.waypoints):
                a.status, a.done_time = "done", t

    def step(self, t):
        new = {i: a.pos_at(t + 1) for i, a in self.agents.items()}
        seen = {}
        for i, c in new.items():
            if c in seen or c in self.grid.static:
                self.collisions += 1
            seen[c] = i
            if c != self.agents[i].pos and self.res.blocks.get(c, -1) > t + 1:
                self.collisions += 1
        for i, a in self.agents.items():
            for j, b in self.agents.items():
                if i < j and new[i] == b.pos and new[j] == a.pos and new[i] != a.pos:
                    self.collisions += 1
        for i, a in self.agents.items():
            a.pos = new[i]

    def snapshot(self, t):
        msg = ""
        for te, m in self.event_log:
            if 0 <= t - te <= 6:
                msg = m
        self.frames.append(dict(
            t=t,
            pos={i: a.pos for i, a in self.agents.items()},
            status={i: a.status for i, a in self.agents.items()},
            target={i: (a.waypoints[a.wp_idx] if a.status == "active" and a.wp_idx < len(a.waypoints) else None)
                    for i, a in self.agents.items()},
            path={i: list(a.plan[max(0, t - a.t0):][:30]) for i, a in self.agents.items()},
            blocks=[c for c, e in self.res.blocks.items() if e > t],
            changed=[i for i, te in self.recent.items() if 0 <= t - te <= 3],
            msg=msg))

    # ---------- main loop ----------
    def run(self, events=None):
        if not self.planned:
            self.initial_plan()
        ev = events if events is not None else self.gen_events()
        by_t = defaultdict(list)
        for e in ev:
            by_t[e.t].append(e)
        t = 0
        self.process_arrivals(0)
        while True:
            if all(a.status in ("done", "failed") for a in self.agents.values()):
                break
            if t >= self.cfg.max_time:
                self.timeout = True
                break
            self.t = t
            for aid in self.recoveries.pop(t, []):
                self.handle_recovery(aid, t)
            for e in by_t.get(t, []):
                self.handle_event(e, t)
            self.retry_stuck(t)
            if self.cfg.record:
                self.snapshot(t)
            self.step(t)
            t += 1
            self.process_arrivals(t)
        self.t = t
        if self.cfg.record:
            self.snapshot(t)
        return self.result()

    def result(self):
        ag = list(self.agents.values())
        done = [a for a in ag if a.status == "done"]
        reasons = Counter(a.fail_reason for a in ag if a.status == "failed")
        n_unfinished = sum(1 for a in ag if a.status in ("active", "broken"))
        if n_unfinished:
            reasons["timeout"] += n_unfinished
        main = [r for r in self.records if r["kind"] in ("block", "break", "emergency")]
        impact = [r for r in main if r["affected"] > 0]
        initial = sum(a.initial_finish for a in ag if a.initial_finish is not None)
        sum_time = sum(a.done_time for a in done)
        return dict(
            completed=len(done) == len(ag),
            survivors_completed=all(a.status == "done" for a in ag if a.fail_reason != "permanent_breakdown"),
            n_done=len(done), n_agents=len(ag),
            fail_reasons=dict(reasons),
            sum_time=sum_time,
            makespan=max((a.done_time for a in done), default=0),
            initial_sum=initial,
            n_events=len(main),
            n_impactful=len(impact),
            avg_changed=sum(r["changed"] for r in main) / len(main) if main else 0.0,
            avg_changed_impactful=sum(r["changed"] for r in impact) / len(impact) if impact else 0.0,
            max_changed=max((r["changed"] for r in main), default=0),
            repair_failures=sum(1 for r in main if not r["success"]),
            collisions=self.collisions,
            repair_cpu=self.cpu_repair,
            plans_called=self.repairer.n_plans,
        )
