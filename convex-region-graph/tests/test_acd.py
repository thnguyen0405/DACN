import json
from pathlib import Path
import unittest

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from build_graph import approximate_convex_decomposition, build_pipeline, is_convex


class ACDTests(unittest.TestCase):
    def test_four_maps_cover_free_space_without_overlap_or_lost_endpoints(self):
        data = Path(__file__).resolve().parents[1] / 'research/data'
        for name in ('hole', 'narrow', 'flappy', 'room'):
            with self.subTest(map=name):
                source = json.loads((data / name / 'map.json').read_text())
                graph, regions, _ = build_pipeline(source)
                m = source['map']
                free = Polygon(m['boundary']).difference(unary_union([Polygon(p) for p in m['obstacles']]))
                polygons = [Polygon(r['polygon']) for r in regions['regions']]
                union = unary_union(polygons)
                self.assertLess(union.symmetric_difference(free).area, 1e-7)
                self.assertLess(sum(p.area for p in polygons)-union.area, 1e-7)
                self.assertTrue(all(p.is_valid for p in polygons))
                self.assertTrue(all(is_convex(r['polygon'], 1e-9) for r in regions['regions']))
                self.assertFalse(graph['decomposition']['triangulation'])
                vertices = {v['id']: Polygon(v['polygon']) for v in graph['vertices']}
                for role in ('start', 'goal'):
                    self.assertTrue(vertices[graph['planning'][role+'_region']].buffer(1e-9).covers(Point(m[role])))
                self.assertTrue(any(graph['planning']['start_region'] in c and graph['planning']['goal_region'] in c
                                    for c in graph['connected_components']))
                if name == 'flappy':
                    self.assertLessEqual(len(polygons), 35)

    def test_convex_input_is_not_split_and_winding_does_not_change_coverage(self):
        boundary = [[0, 0], [5, 0], [5, 4], [0, 4]]
        self.assertEqual(len(approximate_convex_decomposition(boundary)), 1)
        obstacle = [[1, 1], [3, 1], [3, 2], [2, 2], [2, 3], [1, 3]]
        results = [approximate_convex_decomposition(b, [h])
                   for b, h in ((boundary, obstacle), (boundary[::-1], obstacle[::-1]))]
        for pieces in results:
            self.assertTrue(all(is_convex(p, 1e-9) for p in pieces))
        self.assertLess(unary_union([Polygon(p) for p in results[0]]).symmetric_difference(
            unary_union([Polygon(p) for p in results[1]])).area, 1e-9)

    def test_boundary_contact_is_clipped_without_triangles(self):
        pieces = approximate_convex_decomposition(
            [[0, 0], [4, 0], [4, 4], [0, 4]],
            [[[1, 0], [2, 0], [2, 1], [1, 1]]])
        self.assertAlmostEqual(sum(Polygon(p).area for p in pieces), 15)
        self.assertTrue(all(is_convex(p, 1e-9) for p in pieces))

    def test_disconnected_and_outside_geometry_are_rejected(self):
        boundary = [[0, 0], [4, 0], [4, 4], [0, 4]]
        with self.assertRaisesRegex(ValueError, 'connected'):
            approximate_convex_decomposition(boundary, [[[1, 0], [2, 0], [2, 4], [1, 4]]])
        with self.assertRaisesRegex(ValueError, 'inside'):
            approximate_convex_decomposition(boundary, [[[3, 3], [5, 3], [5, 5], [3, 5]]])
