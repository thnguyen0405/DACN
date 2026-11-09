"""Prepare query-specific sequences and class-1 labels without modifying geometry.

Only retained graph edges are used. No decomposition, planner integration,
class-2 state, Bayes model, or model-generated labels are implemented here.
"""
import argparse
from copy import deepcopy
import hashlib
import heapq
import json
import math
from pathlib import Path
from collections import deque

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / 'structural_scoring_config.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_config(path=DEFAULT_CONFIG, k=None):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if k is not None:
        config['k'] = k
    if type(config['k']) is not int or config['k'] < 1:
        raise ValueError('k must be a positive integer')
    rules = config['label_rules']
    if not 0 <= rules['active_at'] <= rules['very_at'] <= 1:
        raise ValueError('Require 0 <= active_at <= very_at <= 1')
    for name in ('open', 'corridor', 'junction', 'narrow', 'critical'):
        r = rules[name]
        if not math.isfinite(r['threshold']) or not math.isfinite(r['softness']) or r['softness'] <= 0:
            raise ValueError(f'Invalid membership settings: {name}')
    for name, key in [('corridor', 'degree'), ('junction', 'minimum_degree'), ('dead_end', 'degree')]:
        if type(rules[name][key]) is not int or rules[name][key] < 0:
            raise ValueError(f'Invalid degree rule: {name}')
    if rules['pocket']['rule'] != 'endpoint_free_side_of_bridge_in_endpoint_component':
        raise ValueError('Unsupported pocket rule')
    if rules['alternative_route']['rule'] != 'simple_path_edge_disjoint_from_best_sequence':
        raise ValueError('Unsupported alternative-route rule')
    if config['feature_definitions']['width_normalizer'] != 'robot_radius':
        raise ValueError('This vocabulary normalizes widths by robot_radius only')
    return config


def sigmoid(value, threshold, softness, decreasing=False):
    x = (value - threshold) / softness
    result = 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))
    return 1 - result if decreasing else result


def membership(value, config, reason=None):
    if value is None:
        return {'value': None, 'active': None, 'label': None,
                'status': 'unavailable', 'reason': reason}
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Membership must be finite and within [0, 1]')
    rules = config['label_rules']
    return {'value': value, 'active': value >= rules['active_at'],
            'label': 'very' if value >= rules['very_at'] else
                     'active' if value >= rules['active_at'] else 'inactive',
            'status': 'computed'}


def finite_point(point):
    return len(point) == 2 and all(math.isfinite(float(x)) for x in point)


def weighted_graph(graph):
    vertices = {v['id']: v for v in graph['vertices']}
    if len(vertices) != len(graph['vertices']):
        raise ValueError('Duplicate region IDs')
    adjacency = {v: {} for v in vertices}
    edge_records = {}
    for vertex in vertices.values():
        if not finite_point(vertex['centroid']):
            raise ValueError('Invalid centroid')
    for index, edge in enumerate(graph['directed_edges']):
        a, b = edge['source'], edge['target']
        if a not in vertices or b not in vertices or a == b:
            raise ValueError('Invalid edge endpoints')
        if (a, b) in edge_records:
            raise ValueError('Parallel directed edges are not supported')
        portal = edge.get('safe_portal')
        if not portal or len(portal) != 2 or not all(finite_point(p) for p in portal):
            raise ValueError(f'Missing or invalid safe_portal: {a}->{b}')
        if math.dist(*portal) <= 0:
            raise ValueError('A retained safe portal must have positive length')
        midpoint = [(portal[0][i] + portal[1][i]) / 2 for i in (0, 1)]
        cost = math.dist(vertices[a]['centroid'], midpoint) + math.dist(midpoint, vertices[b]['centroid'])
        if not math.isfinite(cost) or cost <= 0:
            raise ValueError('Connection weights must be finite and positive')
        adjacency[a][b] = cost
        edge_records[a, b] = {**deepcopy(edge), 'graph_edge_index': index,
                               'safe_portal_midpoint': midpoint, 'weight': cost}
    return vertices, adjacency, edge_records


def endpoint_regions(graph, role, vertices):
    from build_graph import point_in_polygon
    planning = graph.get('planning', {})
    point = planning.get(role)
    if point is not None:
        if not finite_point(point):
            raise ValueError(f'Invalid {role} coordinates')
        return sorted(v for v, data in vertices.items()
                      if point_in_polygon(tuple(point), [tuple(p) for p in data['polygon']], 1e-9))
    values = planning.get(role + '_regions')
    if values is None:
        value = planning.get(role + '_region')
        values = [value] if value is not None else []
    if any(v not in vertices for v in values):
        raise ValueError(f'Unknown {role} region')
    return sorted(set(values))


def shortest_path(adjacency, source, target, banned_nodes=frozenset(), banned_edges=frozenset()):
    if source in banned_nodes or target in banned_nodes:
        return None
    heap = [(0., (source,))]
    best = {source: (0., (source,))}
    while heap:
        distance, path = heapq.heappop(heap)
        node = path[-1]
        if best.get(node) != (distance, path):
            continue
        if node == target:
            return path
        for neighbor, cost in sorted(adjacency[node].items()):
            if neighbor in banned_nodes or (node, neighbor) in banned_edges:
                continue
            candidate = (distance + cost, path + (neighbor,))
            if neighbor not in best or candidate < best[neighbor]:
                best[neighbor] = candidate
                heapq.heappush(heap, candidate)
    return None


def path_cost(path, adjacency):
    return sum(adjacency[a][b] for a, b in zip(path, path[1:]))


def yen_paths(adjacency, source, target, k):
    """Yen's k shortest loopless paths; Dijkstra provides each spur path."""
    first = shortest_path(adjacency, source, target)
    if first is None:
        return []
    accepted = [first]
    candidates, queued = [], set()
    for _ in range(1, k):
        previous = accepted[-1]
        for i in range(len(previous) - 1):
            root = previous[:i + 1]
            blocked = {(p[i], p[i + 1]) for p in accepted
                       if len(p) > i + 1 and p[:i + 1] == root}
            spur = shortest_path(adjacency, root[-1], target, frozenset(root[:-1]), blocked)
            if spur is not None:
                path = root[:-1] + spur
                if path not in queued and path not in accepted:
                    heapq.heappush(candidates, (path_cost(path, adjacency), path))
                    queued.add(path)
        if not candidates:
            break
        accepted.append(heapq.heappop(candidates)[1])
    return accepted


def query_paths(adjacency, starts, goals, k):
    # Each endpoint pair needs at most k candidates to contain the global top k.
    candidates = {p for s in starts for t in goals for p in yen_paths(adjacency, s, t, k)}
    return sorted(candidates, key=lambda p: (path_cost(p, adjacency), p))[:k]


def reachable(adjacency, starts, blocked=frozenset()):
    seen = set(starts)
    queue = deque(starts)
    while queue:
        a = queue.popleft()
        for b in adjacency[a]:
            if (a, b) not in blocked and b not in seen:
                seen.add(b)
                queue.append(b)
    return seen


def edge_key(a, b):
    return tuple(sorted((a, b)))


def undirected_graph(adjacency):
    result = {a: set() for a in adjacency}
    for a in adjacency:
        for b in adjacency[a]:
            result[a].add(b)
            result[b].add(a)
    return result


def biconnected_blocks(adjacency):
    """Tarjan edge blocks, including single-edge bridges."""
    discovery, low, stack, blocks = {}, {}, [], []

    def visit(a, parent):
        discovery[a] = low[a] = len(discovery)
        for b in sorted(adjacency[a]):
            if b == parent:
                continue
            if b not in discovery:
                stack.append(edge_key(a, b))
                visit(b, a)
                low[a] = min(low[a], low[b])
                if low[b] >= discovery[a]:
                    block = set()
                    while stack:
                        edge = stack.pop()
                        block.add(edge)
                        if edge == edge_key(a, b):
                            break
                    blocks.append(block)
            elif discovery[b] < discovery[a]:
                stack.append(edge_key(a, b))
                low[a] = min(low[a], discovery[b])
    for a in sorted(adjacency):
        if a not in discovery:
            visit(a, None)
    return blocks


def simple_route_members(adjacency, starts, goals, allow_trivial=True):
    """Exact simple-path membership on an undirected graph via its block forest."""
    blocks = biconnected_blocks(adjacency)
    tree = {('v', a): set() for a in adjacency}
    for i, block in enumerate(blocks):
        node = ('b', i)
        tree[node] = {('v', v) for edge in block for v in edge}
        for other in tree[node]:
            tree[other].add(node)
    used_blocks, used_vertices = set(), set()
    for source in starts:
        root = ('v', source)
        parents, queue = {root: None}, deque([root])
        while queue:
            a = queue.popleft()
            for b in tree[a]:
                if b not in parents:
                    parents[b] = a
                    queue.append(b)
        for target in goals:
            if source == target and not allow_trivial:
                continue
            node = ('v', target)
            if node not in parents:
                continue
            used_vertices.update((source, target))
            while node is not None:
                if node[0] == 'b':
                    used_blocks.add(node[1])
                node = parents[node]
    edges = set().union(*(blocks[i] for i in used_blocks)) if used_blocks else set()
    used_vertices.update(v for edge in edges for v in edge)
    return used_vertices, edges


def optional_positive(value):
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError('Optional inscribed geometry must be finite and positive')
    return value


def prepare(graph, config, map_name='custom'):
    vertices, adjacency, edges = weighted_graph(graph)
    starts = endpoint_regions(graph, 'start', vertices)
    goals = endpoint_regions(graph, 'goal', vertices)
    paths = query_paths(adjacency, starts, goals, config['k'])
    count = len(paths)
    endpoints = set(starts + goals)
    undirected = undirected_graph(adjacency)
    reciprocal = all((b, a) in edges for a, b in edges)
    route_regions, route_edges = simple_route_members(undirected, starts, goals) if reciprocal else (set(), set())
    rules = config['label_rules']
    robot_radius = optional_positive(graph.get('planning', {}).get('robot_radius')) if graph.get('planning', {}).get('robot_radius') != 0 else None
    missing = []
    if robot_radius is None:
        missing.append('Positive robot_radius is unavailable; width memberships cannot be normalized.')

    pocket_regions = set()
    alternative_regions, alternative_edges = set(), set()
    if reciprocal:
        for block in biconnected_blocks(undirected):
            if len(block) != 1:
                continue
            a, b = next(iter(block))
            component = reachable(undirected, [a])
            if not component.intersection(endpoints):
                continue
            for node in (a, b):
                side = reachable(undirected, [node], {(a, b), (b, a)})
                if not side.intersection(endpoints):
                    pocket_regions.update(side)
        if paths:
            best_edges = {edge_key(a, b) for a, b in zip(paths[0], paths[0][1:])}
            residual = {a: {b for b in neighbors if edge_key(a, b) not in best_edges}
                        for a, neighbors in undirected.items()}
            alternative_regions, alternative_edges = simple_route_members(residual, starts, goals, allow_trivial=False)
    else:
        missing.append('Pocket and alternative-route labels require reciprocal edges; unavailable for this directed graph.')

    sequences = []
    for i, path in enumerate(paths, 1):
        sequences.append({'id': f'sequence_{i}', 'regions': list(path),
                          'connections': [{'source': a, 'target': b, 'weight': adjacency[a][b],
                                           'graph_edge_index': edges[a, b]['graph_edge_index'],
                                           **({'id': edges[a, b]['id']} if 'id' in edges[a, b] else {})}
                                          for a, b in zip(path, path[1:])],
                          'total_weight': path_cost(path, adjacency)})
    common_reason = 'No start-goal sequence exists, so its sequence fraction is undefined.'
    region_results = []
    for region_id, vertex in vertices.items():
        degree = len(undirected[region_id])
        from_start = [shortest_path(adjacency, s, region_id) for s in starts]
        to_goal = [shortest_path(adjacency, region_id, t) for t in goals]
        from_start_cost = min((path_cost(p, adjacency) for p in from_start if p is not None), default=None)
        to_goal_cost = min((path_cost(p, adjacency) for p in to_goal if p is not None), default=None)
        fraction = sum(region_id in p for p in paths) / count if count else None
        desc = vertex.get('descriptors', {})
        inradius = optional_positive(desc.get('maximum_inscribed_ball_radius'))
        elongation = optional_positive(desc.get('maximum_inscribed_ellipsoid_axis_ratio'))
        if elongation is not None and elongation < 1:
            raise ValueError('Inscribed ellipsoid axis ratio must be at least 1')
        width = inradius / robot_radius if inradius is not None and robot_radius else None
        width_reason = 'Requires maximum_inscribed_ball_radius and positive robot_radius; covariance/clearance are not substitutes.'
        shape_reason = 'Requires maximum_inscribed_ellipsoid_axis_ratio; covariance aspect_ratio is not equivalent.'
        labels = {
            'open': membership(sigmoid(width, **rules['open']) if width is not None else None, config, width_reason),
            'corridor': membership(0. if degree != rules['corridor']['degree'] else
                                  sigmoid(elongation, rules['corridor']['threshold'], rules['corridor']['softness'])
                                  if elongation is not None else None, config, shape_reason),
            'junction': membership(0. if degree < rules['junction']['minimum_degree'] else
                                  sigmoid(fraction, rules['junction']['threshold'], rules['junction']['softness'])
                                  if fraction is not None else None, config, common_reason),
            'dead_end': membership(float(degree == rules['dead_end']['degree'] and
                                        (not rules['dead_end']['exclude_endpoint_regions'] or region_id not in endpoints)), config),
            'pocket': membership(float(region_id in pocket_regions) if reciprocal else None, config,
                                 'Requires an undirected reciprocal graph.'),
            'alternative_route': membership(float(region_id in alternative_regions) if reciprocal and count else None,
                                            config, 'Requires a connected query and reciprocal graph.'),
        }
        region_results.append({**deepcopy(vertex), 'structural_features': {
            'degree': degree, 'sequence_fraction': fraction,
            'best_cost_from_start': from_start_cost, 'best_cost_to_goal': to_goal_cost,
            'on_any_simple_start_goal_path': region_id in route_regions if reciprocal and count else None,
            'on_returned_sequences': [s['id'] for s in sequences if region_id in s['regions']],
            'in_all_returned_sequences': all(region_id in p for p in paths) if count else None,
            'maximum_inscribed_ball_radius': inradius, 'normalized_width': width,
            'maximum_inscribed_ellipsoid_axis_ratio': elongation,
            'is_start_region': region_id in starts, 'is_goal_region': region_id in goals},
            'memberships': labels, 'labels': [name for name, label in labels.items() if label['active']]})
        for name, label in labels.items():
            if label['status'] == 'unavailable':
                missing.append(f'Region {region_id}: {name}: {label["reason"]}')

    connections = []
    for a, b in sorted({edge_key(a, b) for a, b in edges}):
        original = edges.get((a, b), edges.get((b, a)))
        fraction = sum(any(edge_key(u, v) == (a, b) for u, v in zip(p, p[1:])) for p in paths) / count if count else None
        mandatory = not set(goals).intersection(reachable(adjacency, starts, {(a, b), (b, a)})) if count else None
        # Current shared-boundary portals are line segments, not full-dimensional
        # intersections with a positive inscribed-ball radius. Do not use W/2.
        inradius = optional_positive(original.get('intersection_inscribed_ball_radius'))
        width = inradius / robot_radius if inradius is not None and robot_radius else None
        labels = {
            'narrow': membership(sigmoid(width, rules['narrow']['threshold'], rules['narrow']['softness'], True)
                                 if width is not None else None, config,
                                 'Requires full-dimensional intersection_inscribed_ball_radius; a 1D safe portal length is not that radius.'),
            'critical': membership(sigmoid(fraction, **rules['critical']) if fraction is not None else None,
                                   config, common_reason),
            'alternative_route': membership(float((a, b) in alternative_edges) if reciprocal and count else None,
                                            config, 'Requires a connected query and reciprocal graph.'),
        }
        directions = [deepcopy(edges[u, v]) for u, v in ((a, b), (b, a)) if (u, v) in edges]
        connections.append({'source': a, 'target': b, 'directions': directions,
                            'portal_width': original.get('portal_width'),
                            'safe_portal_width': original.get('safe_portal_width'),
                            'safe_portal': original['safe_portal'],
                            'safe_portal_midpoint': original['safe_portal_midpoint'],
                            'weight': original['weight'],
                            'structural_features': {'sequence_fraction': fraction,
                                'on_any_simple_start_goal_path': (a, b) in route_edges if reciprocal and count else None,
                                'in_all_returned_sequences': fraction == 1 if count else None,
                                'mandatory_on_all_start_goal_paths': mandatory,
                                'intersection_inscribed_ball_radius': inradius, 'normalized_width': width,
                                'on_returned_sequences': [s['id'] for s, p in zip(sequences, paths)
                                    if any(edge_key(u, v) == (a, b) for u, v in zip(p, p[1:]))]},
                            'memberships': labels, 'labels': [n for n, label in labels.items() if label['active']]})
        for name, label in labels.items():
            if label['status'] == 'unavailable':
                missing.append(f'Connection {a}-{b}: {name}: {label["reason"]}')
    return {'schema': 'query-structural-data/v1', 'map': map_name,
            'map_metadata': {key: deepcopy(graph[key]) for key in
                             ('map_metrics', 'descriptor_metadata', 'decomposition', 'pipeline') if key in graph},
            'planning': {**deepcopy(graph.get('planning', {})),
                         'start_regions': starts, 'goal_regions': goals,
                         'start_region': starts[0] if starts else None,
                         'goal_region': goals[0] if goals else None},
            'query': {'start_regions': starts, 'goal_regions': goals,
                      'status': 'connected' if count else 'missing_endpoint_regions' if not starts or not goals else 'disconnected',
                      'requested_k': config['k'], 'returned_k': count,
                      'shared_endpoint_regions': sorted(set(starts).intersection(goals))},
            'configuration': deepcopy(config), 'sequences': sequences,
            'regions': region_results, 'connections': connections,
            'missing_features': missing,
            'limitations': ['Sequences are structural graph routes, not certified robot trajectories.',
                'Critical membership uses the returned k sequences; fraction 1 does not prove an all-path mandatory connection.',
                'All-path mandatory flags use graph reachability after deleting both directions of the connection.',
                'No class-2 labels, online feedback, Bayes, Thompson sampling, or planner integration.',
                'Inscribed geometry is used only when explicitly supplied; no covariance or clearance substitution.',
                'Alternative-route labels test all simple routes edge-disjoint from the best sequence on reciprocal graphs.']}


def prepare_file(graph_path, config_path=DEFAULT_CONFIG, k=None, map_name='custom', output=None):
    graph_path = Path(graph_path)
    config = load_config(config_path, k)
    graph = json.loads(graph_path.read_text(encoding='utf-8'))
    result = prepare(graph, config, map_name)
    result['source_graph'] = {'path': str(graph_path.resolve()), 'sha256': digest(graph_path)}
    result['source_config'] = {'path': str(Path(config_path).resolve()), 'sha256': digest(config_path)}
    if output:
        if Path(output).resolve() in (graph_path.resolve(), Path(config_path).resolve()):
            raise ValueError('Output must not overwrite source graph/config')
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', default='flappy')
    parser.add_argument('--graph', type=Path)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--k', type=int)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = prepare_file(args.graph or ROOT / 'research/data' / args.map / 'graph.json',
                          args.config, args.k, args.map,
                          args.output or ROOT / 'outputs' / args.map / 'query_labeled_data.json')
    print(f"Prepared {len(result['regions'])} regions, {len(result['connections'])} connections; "
          f"{result['query']['returned_k']} sequences ({result['query']['status']}).")
    print(f"Unavailable feature/label entries: {len(result['missing_features'])}")


if __name__ == '__main__':
    main()
