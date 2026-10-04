"""Robot agent state."""


class Agent:
    def __init__(self, aid, start, tasks):
        self.id = aid
        self.start = start
        self.pos = start
        self.tasks = tasks                      # [(pickup, dropoff), ...]
        self.waypoints = [c for p, d in tasks for c in (p, d)]
        self.wp_idx = 0                         # next waypoint to reach
        # current plan: plan[i] is the cell at absolute time t0 + i.
        # After the plan ends the agent stays on plan[-1].
        self.plan = [start]
        self.t0 = 0
        self.park = True                        # reserve last cell forever?
        self.arrivals = {}                      # waypoint index -> planned arrival time
        self.status = "active"                  # active | done | broken | failed
        self.fail_reason = None
        self.done_time = None
        self.recover_t = None
        self.stuck_since = None
        self.initial_finish = None

    def pos_at(self, t):
        i = min(max(t - self.t0, 0), len(self.plan) - 1)
        return self.plan[i]
