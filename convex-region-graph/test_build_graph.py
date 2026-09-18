import unittest

from build_graph import (
    approximate_convex_decomposition,
    build_graph,
    build_pipeline,
    intersection_relation,
    is_convex,
    normalize_polygon,
    point_in_polygon,
    polygon_area,
)


class GeometryTests(unittest.TestCase):
    def relation(self, a, b):
        pa = normalize_polygon(a, 1e-9)
        pb = normalize_polygon(b, 1e-9)
        return intersection_relation(pa, pb, 1e-9)[0]

    def test_shared_edge(self):
        self.assertEqual(
            self.relation([[0, 0], [1, 0], [1, 1], [0, 1]], [[1, 0], [2, 0], [2, 1], [1, 1]]),
            "shared_edge",
        )

    def test_point_contact_is_not_a_navigation_edge(self):
        self.assertIsNone(
            self.relation([[0, 0], [1, 0], [1, 1], [0, 1]], [[1, 1], [2, 1], [1, 2]]),
        )

    def test_overlap_does_not_create_a_relation(self):
        self.assertIsNone(
            self.relation([[0, 0], [2, 0], [2, 2], [0, 2]], [[1, 1], [3, 1], [3, 3], [1, 3]]),
        )

    def test_containment_does_not_create_a_relation(self):
        self.assertIsNone(
            self.relation([[0, 0], [4, 0], [4, 4], [0, 4]], [[1, 1], [2, 1], [2, 2], [1, 2]]),
        )

    def test_disjoint(self):
        self.assertIsNone(
            self.relation([[0, 0], [1, 0], [1, 1], [0, 1]], [[2, 0], [3, 0], [3, 1], [2, 1]])
        )

    def test_graph_adds_both_directions(self):
        graph = build_graph(
            {
                "regions": [
                    {"id": "A", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]},
                    {"id": "B", "polygon": [[1, 0], [2, 0], [2, 1], [1, 1]]},
                ]
            }
        )
        self.assertNotIn("undirected_edges", graph)
        self.assertEqual(len(graph["directed_edges"]), 2)
        self.assertEqual(graph["connected_components"], [["A", "B"]])
        self.assertEqual(graph["directed_edges"][0]["relation"], "safe_portal")
        self.assertEqual(graph["directed_edges"][0]["portal_width"], 1.0)
        self.assertEqual(graph["directed_edges"][0]["safe_portal_width"], 1.0)

    def test_portal_too_narrow_for_robot_is_not_an_edge(self):
        graph = build_graph(
            {
                "regions": [
                    {"id": "A", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]},
                    {"id": "B", "polygon": [[1, 0], [2, 0], [2, 1], [1, 1]]},
                ]
            },
            required_clearance=0.5,
        )
        self.assertEqual(graph["directed_edges"], [])
        self.assertEqual(graph["connected_components"], [["A"], ["B"]])

    def test_acd_preserves_area_and_returns_convex_regions(self):
        boundary = [[0, 0], [4, 0], [4, 1], [2, 1], [2, 3], [0, 3]]
        regions = approximate_convex_decomposition(boundary)
        self.assertGreater(len(regions), 1)
        self.assertTrue(all(is_convex(region, 1e-9) for region in regions))
        self.assertAlmostEqual(sum(polygon_area(region) for region in regions), 8.0)

    def test_map_pipeline_runs_acd_then_builds_connected_graph(self):
        graph, regions_data, boundary = build_pipeline(
            {
                "map": {
                    "boundary": [[0, 0], [4, 0], [4, 1], [2, 1], [2, 3], [0, 3]],
                    "robot_radius": 0.1,
                    "safety_margin": 0.1,
                    "start": [0.5, 0.5],
                    "goal": [0.5, 2.5],
                }
            }
        )
        self.assertIsNotNone(boundary)
        self.assertEqual(len(graph["vertices"]), len(regions_data["regions"]))
        self.assertEqual(len(graph["connected_components"]), 1)
        self.assertEqual(graph["pipeline"], "map -> ACD -> convex regions -> graph")
        self.assertEqual(graph["planning"]["required_clearance"], 0.2)

    def test_start_too_close_to_wall_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "start clearance"):
            build_pipeline(
                {
                    "map": {
                        "boundary": [[0, 0], [4, 0], [4, 4], [0, 4]],
                        "robot_radius": 0.25,
                        "safety_margin": 0.1,
                        "start": [0.2, 1],
                        "goal": [3, 3],
                    }
                }
            )

    def test_acd_supports_polygon_obstacles(self):
        boundary = [[0, 0], [16, 0], [16, 10], [0, 10]]
        obstacles = [
            [[2, 2], [5, 1.5], [4, 4]],
            [[7, 1], [9, 1.5], [10, 3.5], [8.5, 4.5], [6.5, 3]],
            [[12, 5], [15, 5], [15, 8], [13.5, 8], [13.5, 6.5], [12, 6.5]],
        ]
        regions = approximate_convex_decomposition(boundary, obstacles)
        obstacle_polygons = [[tuple(point) for point in obstacle] for obstacle in obstacles]
        expected_area = polygon_area([tuple(point) for point in boundary]) - sum(
            polygon_area(obstacle) for obstacle in obstacle_polygons
        )
        self.assertTrue(all(is_convex(region, 1e-9) for region in regions))
        self.assertAlmostEqual(sum(polygon_area(region) for region in regions), expected_area)
        for region in regions:
            center = (
                sum(point[0] for point in region) / len(region),
                sum(point[1] for point in region) / len(region),
            )
            self.assertFalse(any(point_in_polygon(center, obstacle, 1e-9) for obstacle in obstacle_polygons))

        graph, regions_data, map_geometry = build_pipeline(
            {"map": {"boundary": boundary, "obstacles": obstacles}}
        )
        self.assertEqual(len(graph["vertices"]), len(regions_data["regions"]))
        self.assertEqual(len(graph["connected_components"]), 1)
        self.assertEqual(len(map_geometry["obstacles"]), 3)


if __name__ == "__main__":
    unittest.main()
