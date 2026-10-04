"""Grid world and warehouse layout generator."""
from collections import deque


class Grid:
    """2D grid. Cells are (x, y) tuples. `static` holds shelf cells (never passable)."""

    def __init__(self, w, h, static=None):
        self.w, self.h = w, h
        self.static = set(static or ())
        self._dist = {}

    def passable(self, c):
        x, y = c
        return 0 <= x < self.w and 0 <= y < self.h and c not in self.static

    def neighbors(self, c):
        x, y = c
        return [n for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                if self.passable(n)]

    def free_cells(self):
        return [(x, y) for x in range(self.w) for y in range(self.h)
                if (x, y) not in self.static]

    def _bfs(self, src):
        d = {src: 0}
        q = deque([src])
        while q:
            c = q.popleft()
            for n in self.neighbors(c):
                if n not in d:
                    d[n] = d[c] + 1
                    q.append(n)
        return d

    def dist_map(self, goal):
        """True shortest-path distance (ignoring other agents) to `goal`. Cached.
        Used as the A* heuristic."""
        if goal not in self._dist:
            self._dist[goal] = self._bfs(goal)
        return self._dist[goal]

    def largest_component(self):
        seen, best = set(), set()
        for c in self.free_cells():
            if c in seen:
                continue
            comp = set(self._bfs(c))
            seen |= comp
            if len(comp) > len(best):
                best = comp
        return best


def make_warehouse(w=20, h=20, shelf_w=2, shelf_len=4, aisle=2):
    """Rectangular shelf blocks separated by aisles of width `aisle`.
    aisle=1 gives narrow single-width corridors (a good failure setting)."""
    static = set()
    for bx in range(aisle, w - aisle - shelf_w + 1, shelf_w + aisle):
        for by in range(aisle, h - aisle - shelf_len + 1, shelf_len + aisle):
            for dx in range(shelf_w):
                for dy in range(shelf_len):
                    static.add((bx + dx, by + dy))
    return Grid(w, h, static)
