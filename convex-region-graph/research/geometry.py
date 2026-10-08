"""Exact polygon-distance collision checks and explicitly discrete references."""
import heapq
import math
import numpy as np
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import unary_union
from shapely import points, contains_xy, distance


class World:
    def __init__(self, data):
        self.data = data['map'] if 'map' in data else data
        self.boundary = Polygon(self.data['boundary'])
        self.obstacles = unary_union([Polygon(p) for p in self.data.get('obstacles', [])])
        self.free = self.boundary.difference(self.obstacles)
        if not self.free.is_valid:
            raise ValueError('Invalid map geometry')
        self.radius = self.data.get('robot_radius', 0) + self.data.get('safety_margin', 0)
        self.walls = self.free.boundary
        self.bounds = self.boundary.bounds

    def valid(self, p):
        q = Point(p)
        return self.free.contains(q) and q.distance(self.walls) + 1e-9 >= self.radius

    def segment_valid(self, a, b):
        if math.dist(a, b) < 1e-12:
            return self.valid(a)
        line = LineString([a, b])
        return self.free.contains(line) and line.distance(self.walls) + 1e-9 >= self.radius

    def path_valid(self, path):
        return bool(path) and all(self.segment_valid(a, b) for a, b in zip(path, path[1:])) and all(self.valid(p) for p in path)


class GridReference:
    """Shortest path on a fixed 8-neighbour lattice with exact segment checks.

    This is NOT the globally optimal continuous path. Start/goal are connected
    to nearby visible lattice vertices. Restricting nodes AND segments to a
    corridor compares both problems on exactly the same graph.
    """
    def __init__(self, world, step):
        if step <= 0:
            raise ValueError('Grid step must be positive')
        self.world, self.step = world, step
        x0, y0, x1, y1 = world.bounds
        xs = np.arange(x0 + step / 2, x1, step)
        ys = np.arange(y0 + step / 2, y1, step)
        self.nx, self.ny = len(xs), len(ys)
        self.coordinates = np.array([(x, y) for y in ys for x in xs])
        self.mask = contains_xy(world.free, self.coordinates[:, 0], self.coordinates[:, 1])
        self.mask &= distance(points(self.coordinates), world.walls) + 1e-9 >= world.radius
        self.edge_cache = {}

    def neighbours(self, i):
        y, x = divmod(i, self.nx)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if not (dx or dy): continue
                xx, yy = x + dx, y + dy
                if 0 <= xx < self.nx and 0 <= yy < self.ny:
                    j = yy * self.nx + xx
                    if self.mask[j]: yield j

    def edge_valid(self, i, j):
        key = tuple(sorted((i, j)))
        if key not in self.edge_cache:
            self.edge_cache[key] = self.world.segment_valid(self.coordinates[i], self.coordinates[j])
        return self.edge_cache[key]

    def endpoints(self):
        """Deterministic far-apart pair in largest valid lattice component."""
        seen = set(); groups = []
        for raw in np.flatnonzero(self.mask):
            i = int(raw)
            if i in seen: continue
            seen.add(i); group = [i]; queue = [i]
            while queue:
                u = queue.pop()
                for v in self.neighbours(u):
                    if v not in seen and self.edge_valid(u, v):
                        seen.add(v); group.append(v); queue.append(v)
            groups.append(group)
        if not groups: raise ValueError('No safe lattice vertices')
        group = max(groups, key=len)
        def farthest(u):
            return max(group, key=lambda v: np.sum((self.coordinates[u] - self.coordinates[v])**2))
        a = farthest(group[0]); b = farthest(a)
        return self.coordinates[a].tolist(), self.coordinates[b].tolist(), len(groups)

    def shortest(self, start, goal, corridor=None):
        if not self.world.valid(start) or not self.world.valid(goal): return None
        allow = self.mask.copy()
        if corridor is not None:
            from shapely import covers
            allow &= covers(corridor, points(self.coordinates))
            if not corridor.covers(Point(start)) or not corridor.covers(Point(goal)): return None
        def links(p):
            candidates = np.flatnonzero(allow & (np.sum((self.coordinates - p)**2, axis=1) <= (2*self.step)**2))
            return {int(i): math.dist(p, self.coordinates[i]) for i in candidates
                    if self.world.segment_valid(p, self.coordinates[i])
                    and (corridor is None or corridor.covers(LineString([p, self.coordinates[i]])))}
        begins, ends = links(start), links(goal)
        distances = dict(begins); parents = {i: None for i in begins}
        heap = [(d, i) for i, d in begins.items()]; heapq.heapify(heap)
        best = math.inf; finish = None
        while heap:
            d, u = heapq.heappop(heap)
            if d != distances[u] or d >= best: continue
            if u in ends and d + ends[u] < best: best, finish = d + ends[u], u
            for v in self.neighbours(u):
                if not allow[v] or not self.edge_valid(u, v): continue
                if corridor is not None and not corridor.covers(LineString([self.coordinates[u], self.coordinates[v]])): continue
                nd = d + math.dist(self.coordinates[u], self.coordinates[v])
                if nd < distances.get(v, math.inf):
                    distances[v] = nd; parents[v] = u; heapq.heappush(heap, (nd, v))
        if finish is None: return None
        chain = []
        while finish is not None:
            chain.append(self.coordinates[finish].tolist()); finish = parents[finish]
        path = [list(start)] + list(reversed(chain)) + [list(goal)]
        path = [p for i,p in enumerate(path) if i == 0 or math.dist(p,path[i-1]) > 1e-10]
        assert self.world.path_valid(path)
        return {'path': path, 'length': path_length(path), 'step': self.step,
                'reference_type': 'shortest_on_8_neighbour_grid_not_continuous_optimum'}


def path_length(path):
    return sum(math.dist(a,b) for a,b in zip(path,path[1:]))


def path_region_sequence(path, graph):
    """Intersect each full path segment with polygons; no sparse-point guessing."""
    polygons = [(v['id'], Polygon(v['polygon'])) for v in graph['vertices']]
    sequence = []
    for a,b in zip(path,path[1:]):
        if math.dist(a,b) < 1e-12: continue
        line = LineString([a,b]); intervals=[]; cuts={0.0,line.length}
        for rid,poly in polygons:
            overlap=line.intersection(poly)
            chunks=list(overlap.geoms) if hasattr(overlap,'geoms') else [overlap]
            for chunk in chunks:
                if chunk.length<=1e-9 or chunk.geom_type!='LineString':continue
                lo,hi=sorted((line.project(Point(chunk.coords[0])),line.project(Point(chunk.coords[-1]))))
                intervals.append((lo,hi,rid));cuts.update((lo,hi))
        cuts=sorted(cuts)
        for lo,hi in zip(cuts,cuts[1:]):
            if hi-lo<=1e-9:continue
            mid=(lo+hi)/2
            ids=sorted(rid for x,y,rid in intervals if x-1e-10<=mid<=y+1e-10)
            if not ids:continue
            rid=sequence[-1] if sequence and sequence[-1] in ids else ids[0]
            if not sequence or sequence[-1]!=rid:sequence.append(rid)
    return sequence


def overlap_metrics(a,b,graph,tolerance=0.2):
    """Unordered region Jaccard, ordered LCS, and symmetric length coverage."""
    if not a or not b:
        return {'region_jaccard_pct':None,'sequence_lcs_pct':None,'path_coverage_pct':None}
    aa,bb=path_region_sequence(a,graph),path_region_sequence(b,graph)
    union=set(aa)|set(bb)
    row=[0]*(len(bb)+1)
    for x in aa:
        new=[0]
        for j,y in enumerate(bb):new.append(row[j]+1 if x==y else max(new[-1],row[j+1]))
        row=new
    la,lb=LineString(a),LineString(b)
    coverage=(la.intersection(lb.buffer(tolerance)).length+lb.intersection(la.buffer(tolerance)).length)/(la.length+lb.length)
    return {'region_jaccard_pct':100*len(set(aa)&set(bb))/len(union) if union else None,
            'sequence_lcs_pct':200*row[-1]/(len(aa)+len(bb)) if aa or bb else None,
            'path_coverage_pct':100*coverage,'path_tolerance_m':tolerance,
            'sequence_a':aa,'sequence_b':bb}
