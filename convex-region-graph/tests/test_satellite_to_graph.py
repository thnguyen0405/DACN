import copy
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
import zipfile

import numpy as np
from PIL import Image
from shapely.geometry import Point, Polygon

from graph_utils import prepare_planning_graph
from export_sampling_prior import build_sampling_prior
from satellite_to_graph import (annotation_template, build_documents,
                                mask_to_polygons, read_image, save_documents,
                                suggest_region, zip_documents)


class SatelliteTests(unittest.TestCase):
    def setUp(self):
        self.identity = dict(name="synthetic.png", width=100, height=100, sha256="test-hash")
        self.annotation = annotation_template(self.identity)
        self.annotation["calibration"].update(points_px=[[0, 0], [100, 0]], distance_m=10,
                                               source="Synthetic 10 m square test fixture", basis="measured")
        self.annotation["planning_px"] = dict(start=[10, 10], goal=[90, 90])
        self.annotation["review"]["geometry_confirmed"] = True

    def build(self, annotation=None, **kwargs):
        return build_documents(annotation or self.annotation, self.identity, **kwargs)

    def test_square_ground_truth_and_pixel_y_flip(self):
        docs = self.build()
        graph = docs["graph.json"]
        self.assertEqual(len(graph["vertices"]), 1)
        vertex = graph["vertices"][0]
        self.assertAlmostEqual(vertex["area"], 100)
        self.assertEqual(vertex["centroid"], [5, 5])
        self.assertAlmostEqual(vertex["descriptors"]["perimeter"], 40)
        self.assertAlmostEqual(vertex["descriptors"]["diameter"], math.sqrt(200))
        self.assertAlmostEqual(vertex["descriptors"]["aspect_ratio"], 1)
        self.assertAlmostEqual(vertex["descriptors"]["compactness"], 4 / math.pi)
        self.assertAlmostEqual(vertex["descriptors"]["centroid_clearance"], 5)
        self.assertAlmostEqual(vertex["descriptors"]["mean_clearance"], 10 / 6, delta=.08)
        self.assertEqual(graph["planning"]["start"], [1, 9])
        self.assertEqual(graph["planning"]["goal"], [9, 1])
        self.assertTrue(docs["audit.json"]["start_goal_graph_connected"])
        self.assertIn("<svg", docs["graph.svg"])

    def test_scale_changes_lengths_and_area_not_shape(self):
        first = self.build()["graph.json"]["vertices"][0]
        self.annotation["calibration"]["distance_m"] = 20
        second = self.build()["graph.json"]["vertices"][0]
        self.assertAlmostEqual(second["area"], 4 * first["area"])
        self.assertAlmostEqual(second["descriptors"]["diameter"], 2 * first["descriptors"]["diameter"])
        self.assertAlmostEqual(second["descriptors"]["compactness"], first["descriptors"]["compactness"])

    def test_hole_coverage_convexity_and_existing_llm_export(self):
        self.annotation["geometry_px"]["obstacles"] = [[[40, 40], [60, 40], [60, 60], [40, 60]]]
        docs = self.build()
        graph, audit = docs["graph.json"], docs["audit.json"]
        self.assertAlmostEqual(audit["free_area_m2"], 96)
        self.assertLess(audit["coverage_error_m2"], 1e-8)
        self.assertLess(audit["overlap_area_m2"], 1e-8)
        for v in graph["vertices"]:
            p = Polygon(v["polygon"])
            self.assertAlmostEqual(p.area, p.convex_hull.area)
            self.assertLess(p.intersection(Polygon([[4, 4], [6, 4], [6, 6], [4, 6]])).area, 1e-8)
        planning = prepare_planning_graph(graph)
        self.assertEqual(len(planning["vertices"]), len(graph["vertices"]))
        prior = {"start_region": graph["planning"]["start_region"],
                 "goal_region": graph["planning"]["goal_region"],
                 "region_scores": [{"id": v["id"], "score": 0.5, "reason": "Test fixture"}
                                   for v in graph["vertices"]]}
        # The downstream prior schema is checked using the same validator as the demo.
        exported, missing = build_sampling_prior(graph, prior)
        self.assertFalse(missing)
        self.assertEqual(len(exported["regions"]), len(graph["vertices"]))

    def test_walkable_union_concave_and_boundary_obstacle(self):
        self.annotation["geometry_px"]["walkable"] = [
            [[0, 0], [100, 0], [100, 30], [0, 30]],
            [[70, 0], [100, 0], [100, 100], [70, 100]],
        ]
        self.annotation["geometry_px"]["obstacles"] = [[[40, 0], [60, 0], [60, 10], [40, 10]]]
        self.annotation["planning_px"]["start"] = [10, 15]
        docs = self.build()
        self.assertAlmostEqual(docs["audit.json"]["free_area_m2"], 49)
        self.assertLess(docs["audit.json"]["coverage_error_m2"], 1e-8)

    def test_disconnected_geometry_rejected_without_dropping_components(self):
        self.annotation["geometry_px"]["walkable"] = [
            [[0, 0], [30, 0], [30, 30], [0, 30]],
            [[70, 70], [100, 70], [100, 100], [70, 100]],
        ]
        with self.assertRaisesRegex(ValueError, "liên thông"):
            self.build()

    def test_invalid_and_outside_polygons(self):
        for ring in ([[0, 0], [100, 100], [0, 100], [100, 0]],
                     [[0, 0], [101, 0], [101, 50]],
                     [[0, 0], [50, float("nan")], [100, 100]]):
            with self.subTest(ring=ring):
                annotation = copy.deepcopy(self.annotation)
                annotation["geometry_px"]["boundary"] = ring
                with self.assertRaises(ValueError):
                    self.build(annotation)

    def test_endpoint_on_wall_or_inside_obstacle_or_too_close(self):
        self.annotation["geometry_px"]["obstacles"] = [[[40, 40], [60, 40], [60, 60], [40, 60]]]
        for point in ([50, 50], [0, 20], [1, 20]):
            with self.subTest(point=point):
                self.annotation["planning_px"]["start"] = point
                with self.assertRaisesRegex(ValueError, "start"):
                    self.build()

    def test_calibration_review_identity_guards(self):
        cases = []
        for field, value in (("distance_m", None), ("distance_m", float("inf")),
                             ("source", ""), ("points_px", [[1, 1], [1, 1]]),
                             ("basis", "assumed"), ("relative_uncertainty", -0.1)):
            annotation = copy.deepcopy(self.annotation)
            annotation["calibration"][field] = value
            cases.append(annotation)
        annotation = copy.deepcopy(self.annotation)
        annotation["review"]["geometry_confirmed"] = False
        cases.append(annotation)
        annotation = copy.deepcopy(self.annotation)
        annotation["image"]["sha256"] = "different-image"
        cases.append(annotation)
        for annotation in cases:
            with self.subTest(annotation=annotation):
                with self.assertRaises(ValueError):
                    self.build(annotation)

    def test_estimated_calibration_is_never_promoted_to_verified(self):
        self.annotation["calibration"]["basis"] = "map_measurement"
        docs = self.build(allow_estimated=True)
        provenance = docs["graph.json"]["provenance"]
        self.assertEqual(provenance["calibration"]["status"], "estimated")
        self.assertEqual(provenance["physical_accuracy"], "not_independently_verified")

    def test_uncalibrated_pixel_mode_never_labels_measurements_as_metres(self):
        self.annotation["coordinate_units"] = "px"
        self.annotation["calibration"]["distance_m"] = None
        self.annotation["calibration"]["points_px"] = []
        self.annotation["robot"]["radius_px"] = 2
        docs = self.build()
        graph, audit = docs["graph.json"], docs["audit.json"]
        self.assertEqual(graph["vertices"][0]["area"], 10000)
        self.assertEqual(graph["planning"]["start"], [10, 90])
        self.assertEqual(graph["planning"]["robot_radius"], 2)
        self.assertEqual(graph["descriptor_metadata"]["length_unit"], "px")
        self.assertEqual(graph["descriptor_metadata"]["area_unit"], "px^2")
        self.assertNotIn("units m^2", graph["descriptor_metadata"]["traversability"])
        self.assertIsNone(graph["provenance"]["calibration"]["metres_per_pixel"])
        self.assertNotIn("free_area_m2", audit)
        self.assertEqual(docs["map.json"]["map"]["coordinate_units"], "px")
        with self.assertRaisesRegex(ValueError, "metre coordinates"):
            build_sampling_prior(graph, {})

    def test_mask_preserves_holes_components_and_original_coordinates(self):
        mask = np.zeros((10, 10), dtype=bool)
        mask[1:9, 1:9] = True
        mask[4:6, 4:6] = False
        result = mask_to_polygons(mask, 100, 100, 0)
        self.assertEqual(result["audit"]["components"], 1)
        self.assertEqual(len(result["obstacles"]), 1)
        self.assertAlmostEqual(Polygon(result["walkable"][0], result["obstacles"]).area, 6000)
        mask[:, 4:6] = False
        result = mask_to_polygons(mask, 100, 100, 0)
        self.assertEqual(result["audit"]["components"], 2)

    def test_colour_proposal_does_not_leak_to_disconnected_same_colour(self):
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb[10:40, 10:40] = 180
        rgb[60:90, 60:90] = 180
        proposal = suggest_region(Image.fromarray(rgb), [20, 20], tolerance=5, simplify_px=0)
        self.assertEqual(proposal["audit"]["mask_area_px2"], 900)
        self.assertTrue(proposal["audit"]["review_required"])
        self.assertFalse(Polygon(proposal["walkable"][0]).contains(Point(70, 70)))

    def test_nested_mask_island_cannot_be_silently_lost(self):
        mask = np.ones((20, 20), dtype=bool)
        mask[3:17, 3:17] = False
        mask[8:12, 8:12] = True
        with self.assertRaisesRegex(ValueError, "đảo"):
            mask_to_polygons(mask, 100, 100, 0)

    def test_full_resolution_image_hash_and_zip_non_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.png"
            Image.new("RGB", (100, 100), "gray").save(path)
            image, identity = read_image(path)
            self.assertEqual(image.size, (100, 100))
            self.assertEqual(len(identity["sha256"]), 64)
            docs = self.build()
            output = Path(folder) / "run"
            save_documents(docs, output)
            self.assertEqual(json.loads((output / "graph.json").read_text())["vertices"][0]["area"], 100)
            with self.assertRaises(ValueError):
                save_documents(docs, output)
            with zipfile.ZipFile(io.BytesIO(zip_documents(docs))) as archive:
                self.assertEqual(set(archive.namelist()), set(docs))


if __name__ == "__main__":
    unittest.main()
