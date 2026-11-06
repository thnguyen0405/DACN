import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from acd2d_reference import ROOT, import_partition
from build_graph import build_pipeline


class ACD2DReferenceTests(unittest.TestCase):
    def document(self, name="flappy"):
        return json.loads((ROOT / "research/data" / name / "map.json").read_text())

    def test_reference_region_counts_and_ids_are_preserved_without_redecomposition(self):
        with mock.patch("build_graph.approximate_convex_decomposition", side_effect=AssertionError("unexpected redecomposition")):
            for name, count in (("hole", 9), ("narrow", 18), ("flappy", 35), ("room", 83)):
                with self.subTest(map=name):
                    graph, _, _ = build_pipeline(self.document(name))
                    self.assertEqual(len(graph["vertices"]), count)
                    self.assertEqual({v["id"] for v in graph["vertices"]}, {f"C{i}" for i in range(count)})
                    provenance = graph["decomposition"]
                    self.assertEqual(provenance["execution"], "recorded_partition_import")
                    self.assertEqual(len(provenance["source_sha256"]), 64)
                    repair = provenance["rounding_repair"]
                    self.assertLess(repair["maximum_vertex_displacement"], repair["allowed_vertex_displacement"])
                    self.assertLess(repair["coverage_error_area"], 1e-8)

    def test_changed_geometry_is_rejected_instead_of_reusing_an_old_partition(self):
        document = self.document()
        document["map"]["boundary"][1][0] += 0.1
        with self.assertRaisesRegex(ValueError, "Map geometry changed"):
            import_partition(document)

    def test_planning_endpoints_can_change_without_changing_the_partition(self):
        document = self.document()
        original = copy.deepcopy(document["map"])
        document["map"]["start"], document["map"]["goal"] = original["goal"], original["start"]
        graph, _, _ = build_pipeline(document)
        self.assertEqual(len(graph["vertices"]), 35)
        self.assertEqual(graph["planning"]["start"], original["goal"])

    def test_corrupted_reference_is_rejected_by_checksum(self):
        document = self.document()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            document["acd2d_reference"]["path"] = "reference.json"
            (root / "reference.json").write_text('{"regions": []}')
            with mock.patch("acd2d_reference.ROOT", root):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    import_partition(document)
