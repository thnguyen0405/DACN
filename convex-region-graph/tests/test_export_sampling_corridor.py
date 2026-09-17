import unittest

from export_sampling_corridor import CorridorExportError, build_sampling_corridor


class SamplingCorridorExportTests(unittest.TestCase):
    def setUp(self):
        self.graph = {
            "vertices": [
                {
                    "id": "C0",
                    "centroid": [0.5, 0.5],
                    "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
                },
                {
                    "id": "C1",
                    "centroid": [1.5, 0.5],
                    "polygon": [[1, 0], [2, 0], [2, 1], [1, 1]],
                },
                {
                    "id": "C2",
                    "centroid": [2.5, 0.5],
                    "polygon": [[2, 0], [3, 0], [3, 1], [2, 1]],
                },
            ]
        }

    def test_only_sequence_regions_are_exported_in_route_order(self):
        corridor = build_sampling_corridor(
            self.graph, {"sequence": ["C2", "C0"]}
        )

        self.assertEqual(corridor["sequence"], ["C2", "C0"])
        self.assertEqual(
            [region["id"] for region in corridor["regions"]], ["C2", "C0"]
        )
        self.assertEqual(
            corridor["regions"][0]["polygon"],
            [[2.0, 0.0], [3.0, 0.0], [3.0, 1.0], [2.0, 1.0]],
        )

    def test_unknown_route_region_is_rejected(self):
        with self.assertRaisesRegex(CorridorExportError, "unknown graph region"):
            build_sampling_corridor(self.graph, {"sequence": ["C0", "C99"]})

    def test_empty_route_is_rejected(self):
        with self.assertRaisesRegex(CorridorExportError, "non-empty"):
            build_sampling_corridor(self.graph, {"sequence": []})

    def test_missing_route_sequence_is_rejected(self):
        with self.assertRaisesRegex(CorridorExportError, "non-empty"):
            build_sampling_corridor(self.graph, {})

    def test_duplicate_route_region_is_rejected(self):
        with self.assertRaisesRegex(CorridorExportError, "duplicate"):
            build_sampling_corridor(self.graph, {"sequence": ["C0", "C1", "C0"]})

    def test_duplicate_graph_region_is_rejected(self):
        duplicate = {"vertices": self.graph["vertices"] + [self.graph["vertices"][0]]}
        with self.assertRaisesRegex(CorridorExportError, "Duplicate graph region"):
            build_sampling_corridor(duplicate, {"sequence": ["C0"]})


if __name__ == "__main__":
    unittest.main()
