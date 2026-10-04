"""Space-Time A* with a reservation table."""
import heapq
import itertools
from collections import defaultdict

MOVES = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))   # wait + 4 directions


class ResTable:
    """Reservations made by agents' plans.

    occ[cell][t] = agent in `cell` at time t       (vertex conflicts)
    edge[(a,b,t)] = agent moving a->b during t..t+1 (swap conflicts)
    parked[cell]  = (agent, t_from): agent sits there from t_from forever
    blocks[cell]  = time until which a dynamic obstacle blocks the cell
    """

    def __init__(self):
        self.occ = defaultdict(dict)
        self.edge = {}
        self.parked = {}
        self.blocks = {}
        self.own = {}
        self.displaced = set()   # agents whose reservations were overwritten

    def remove(self, aid):
        rec = self.own.pop(aid, None)
        if rec is None:
            return
        occ_keys, edge_keys, pcell = rec
        for c, t in occ_keys:
            if self.occ[c].get(t) == aid:
                del self.occ[c][t]
        for k in edge_keys:
            if self.edge.get(k) == aid:
                del self.edge[k]
        if pcell is not None and self.parked.get(pcell, (None,))[0] == aid:
            del self.parked[pcell]

    def add(self, aid, plan, t0, park=True, track=True, force=True):
        """Reserve `plan` (plan[i] at time t0+i).
        force=True : this plan wins over existing reservations of other agents (used for
                     robots that are physically stuck: breakdown / hold). With track=True the
                     overridden agents are put in `displaced` so repair can fix them.
        force=False: never overwrite another agent's reservation (used when restoring or
                     committing plans, so stale plans cannot erase a forced claim)."""
        self.remove(aid)
        occ_keys, edge_keys = [], []
        for i, c in enumerate(plan):
            t = t0 + i
            cur = self.occ[c]
            old = cur.get(t)
            if old is None or old == aid or force:
                if old is not None and old != aid and track:
                    self.displaced.add(old)
                cur[t] = aid
                occ_keys.append((c, t))
            if i > 0 and plan[i - 1] != c:
                if track and force:
                    o = self.edge.get((c, plan[i - 1], t - 1))
                    if o is not None and o != aid:
                        self.displaced.add(o)
                k = (plan[i - 1], c, t - 1)
                self.edge[k] = aid
                edge_keys.append(k)
        pcell = None
        if park:
            c, tend = plan[-1], t0 + len(plan) - 1
            pk = self.parked.get(c)
            if pk is None or pk[0] == aid or force:
                if track and force:
                    for t, o in self.occ[c].items():
                        if t > tend and o != aid:
                            self.displaced.add(o)
                    if pk and pk[0] != aid:
                        self.displaced.add(pk[0])
                self.parked[c] = (aid, tend)
                pcell = c
        self.own[aid] = (occ_keys, edge_keys, pcell)

    def take_displaced(self):
        s, self.displaced = self.displaced, set()
        return s

    def last_time(self, cell, aid):
        return max((t for t, o in self.occ[cell].items() if o != aid), default=-1)


def plan_leg(grid, res, aid, start, t0, goal, final, horizon, node_cap=25000):
    """Space-Time A* from (start, t0) to `goal`. Returns list of cells
    (index i = time t0+i) or None. If `final`, the agent parks at the goal
    afterwards, so we only accept arrival after every other reservation there."""
    dist = grid.dist_map(goal)
    if start not in dist:
        return None
    t_min = t0
    if final:
        pk = res.parked.get(goal)
        if pk is not None and pk[0] != aid:
            return None
        t_min = max(t0, res.last_time(goal, aid) + 1, res.blocks.get(goal, -1))
    if t_min - t0 > horizon:
        return None

    cnt = itertools.count()
    h0 = max(dist[start], t_min - t0)
    heap = [(h0, h0, next(cnt), start, t0)]
    parent = {(start, t0): None}
    pops = 0
    while heap:
        _, _, _, cell, t = heapq.heappop(heap)
        pops += 1
        if pops > node_cap:
            return None
        if cell == goal and t >= t_min:
            path, node = [], (cell, t)
            while node is not None:
                path.append(node[0])
                node = parent[node]
            return path[::-1]
        if t - t0 >= horizon:
            continue
        nt = t + 1
        x, y = cell
        for dx, dy in MOVES:
            nc = (x + dx, y + dy)
            if (nc, nt) in parent or not grid.passable(nc):
                continue
            if res.blocks.get(nc, -1) > nt:                       # dynamic obstacle
                continue
            d = res.occ.get(nc)
            if d and nt in d:                                     # vertex conflict
                continue
            pk = res.parked.get(nc)
            if pk and pk[0] != aid and pk[1] <= nt:               # parked agent
                continue
            if nc != cell and (nc, cell, t) in res.edge:          # swap conflict
                continue
            hd = dist.get(nc)
            if hd is None:
                continue
            hn = max(hd, t_min - nt)
            parent[(nc, nt)] = (cell, t)
            heapq.heappush(heap, (nt - t0 + hn, hn, next(cnt), nc, nt))
    return None


def plan_waypoints(grid, res, aid, pos, now, wps, horizon):
    """Plan through all waypoints in order. Returns (plan, arrival_times) or None."""
    plan, cur, t, arr = [pos], pos, now, []
    for i, wp in enumerate(wps):
        leg = plan_leg(grid, res, aid, cur, t, wp, i == len(wps) - 1, horizon)
        if leg is None:
            return None
        plan.extend(leg[1:])
        t += len(leg) - 1
        cur = wp
        arr.append(t)
    return plan, arr
