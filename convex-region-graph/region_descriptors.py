"""Intrinsic descriptors for a uniform-area distribution over a convex region.

Lengths are metres, areas m². Clearance includes the workspace boundary as
C_obs. Mean clearance uses deterministic area-weighted triangle quadrature,
not distance to the artificial convex-region boundaries.
"""
import math


def polygon_moments(poly):
    # Shift coordinates to avoid cancellation on maps far from the origin.
    ox, oy = poly[0]
    p = [(x - ox, y - oy) for x, y in poly]
    area2 = mx = my = xx = yy = xy = 0.0
    perimeter = 0.0
    for (x, y), (u, v) in zip(p, p[1:] + p[:1]):
        c = x * v - u * y
        area2 += c
        mx += (x + u) * c
        my += (y + v) * c
        xx += (x*x + x*u + u*u) * c
        yy += (y*y + y*v + v*v) * c
        xy += (2*x*y + x*v + u*y + 2*u*v) * c
        perimeter += math.hypot(u-x, v-y)
    if abs(area2) < 1e-14:
        raise ValueError('Region must have positive area')
    cx, cy = mx / (3*area2), my / (3*area2)
    vx, vy = xx/(6*area2)-cx*cx, yy/(6*area2)-cy*cy
    cov = xy/(12*area2)-cx*cy
    gap = math.hypot(vx-vy, 2*cov)
    low, high = (vx+vy-gap)/2, (vx+vy+gap)/2
    if low <= 0:
        raise ValueError('Degenerate region covariance')
    area = abs(area2)/2
    return {
        'area': area, 'perimeter': perimeter,
        'diameter': max(math.dist(a, b) for a in poly for b in poly),
        'aspect_ratio': high/low,
        'compactness': perimeter**2/(4*math.pi*area),
        'covariance_eigenvalues': [low, high],
    }


def triangle_samples(a, b, c, subdivisions=12):
    """Equal-area centroids of n² small triangles in a triangle."""
    def at(i, j):
        return (a[0] + (b[0]-a[0])*i/subdivisions + (c[0]-a[0])*j/subdivisions,
                a[1] + (b[1]-a[1])*i/subdivisions + (c[1]-a[1])*j/subdivisions)
    for i in range(subdivisions):
        for j in range(subdivisions-i):
            yield at(i+1/3, j+1/3)
            if i+j < subdivisions-1:
                yield at(i+2/3, j+2/3)


def enrich_graph(graph, geometry=None):
    # Local import avoids a module-level cycle with build_graph.
    from build_graph import point_clearance, polygon_area, shared_portal
    by_id = {}
    for vertex in graph['vertices']:
        poly = vertex['polygon']
        d = polygon_moments(poly)
        outgoing = [e for e in graph['directed_edges'] if e['source'] == vertex['id']]
        raw_portals = [shared_portal(poly, other['polygon'], 1e-9)
                       for other in graph['vertices'] if other['id'] != vertex['id']]
        raw_portals = [portal for portal in raw_portals if portal is not None]
        d['degree'] = len(raw_portals)
        d['safe_degree'] = len({e['target'] for e in outgoing})
        d['conductance'] = sum(math.dist(*portal) for portal in raw_portals)/d['perimeter']
        d['safe_conductance'] = sum(e['safe_portal_width'] for e in outgoing)/d['perimeter']
        d['mean_clearance'] = None
        d['centroid_clearance'] = None
        if geometry is not None:
            boundary, obstacles = geometry['boundary'], geometry['obstacles']
            d['centroid_clearance'] = point_clearance(vertex['centroid'], boundary, obstacles)
            integral = 0.0
            for i in range(1, len(poly)-1):
                tri = [poly[0], poly[i], poly[i+1]]
                area = polygon_area(tri)
                if area <= 1e-14:
                    continue
                values = [point_clearance(p, boundary, obstacles) for p in triangle_samples(*tri)]
                integral += area * sum(values)/len(values)
            d['mean_clearance'] = integral/d['area']
        vertex['descriptors'] = d
        by_id[vertex['id']] = d
    for edge in graph['directed_edges']:
        a, b = (by_id[edge[key]]['mean_clearance'] for key in ('source', 'target'))
        edge['traversability'] = None if a is None or b is None else edge['portal_width']*min(a, b)
        edge['safe_traversability'] = None if a is None or b is None else edge['safe_portal_width']*min(a, b)
    graph['descriptor_metadata'] = {
        'schema': 'intrinsic-region-descriptors/v1',
        'length_unit': 'm', 'area_unit': 'm^2',
        'covariance': 'uniform area, exact polygon moments; aspect ratio = lambda_max/lambda_min',
        'clearance_obstacles': 'obstacle polygons and workspace exterior; NOT region boundaries',
        'mean_clearance_method': 'area-weighted triangle quadrature, 12^2 samples per fan triangle',
        'missing_clearance': 'null when original map geometry is unavailable',
        'conductance': 'sum of all geometric shared-boundary portal widths / perimeter; safe_degree and safe_conductance use only traversable graph edges',
        'traversability': 'original portal width * min(mean clearances), units m^2; not a safety certificate',
    }
    if geometry is not None:
        boundary_area = polygon_area(geometry['boundary'])
        graph['map_metrics'] = {'boundary_area': boundary_area,
            'obstacle_area': sum(polygon_area(p) for p in geometry['obstacles'])}
        graph['map_metrics']['obstacle_area_ratio'] = graph['map_metrics']['obstacle_area']/boundary_area
    return graph
