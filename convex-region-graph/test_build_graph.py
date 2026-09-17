import unittest

from build_graph import build_graph, intersection_relation, normalize_polygon


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

    def test_point_contact(self):
        self.assertEqual(
            self.relation([[0, 0], [1, 0], [1, 1], [0, 1]], [[1, 1], [2, 1], [1, 2]]),
            "point_contact",
        )

    def test_overlap(self):
        self.assertEqual(
            self.relation([[0, 0], [2, 0], [2, 2], [0, 2]], [[1, 1], [3, 1], [3, 3], [1, 3]]),
            "overlap",
        )

    def test_containment_is_overlap(self):
        self.assertEqual(
            self.relation([[0, 0], [4, 0], [4, 4], [0, 4]], [[1, 1], [2, 1], [2, 2], [1, 2]]),
            "overlap",
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
        self.assertEqual(len(graph["undirected_edges"]), 1)
        self.assertEqual(len(graph["directed_edges"]), 2)
        self.assertEqual(graph["connected_components"], [["A", "B"]])


if __name__ == "__main__":
    unittest.main()
