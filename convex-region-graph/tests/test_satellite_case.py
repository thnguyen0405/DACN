import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.request
import warnings

from PIL import Image
from shapely.geometry import Polygon

from satellite_case import build_case, main, score_case
from satellite_to_graph import annotation_template, read_image, save_documents
from research.geometry import World


class SatelliteCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image_path = self.root / "image.png"
        Image.new("RGB", (200, 100), "#889988").save(self.image_path)
        self.image, self.identity = read_image(self.image_path)
        self.annotation = annotation_template(self.identity)
        self.annotation["geometry_px"]["boundary"] = [[20, 10], [180, 10], [180, 90], [20, 90]]
        self.annotation["geometry_px"]["obstacles"] = [[[90, 35], [110, 35], [110, 65], [90, 65]]]
        self.annotation["planning_px"] = {"start": [30, 50], "goal": [170, 50]}
        self.annotation["review"]["geometry_confirmed"] = True

    def build(self):
        return build_case(self.image, self.identity, self.annotation, grid_step=.5)

    def test_simulation_normalization_preserves_gates_and_area(self):
        original = copy.deepcopy(self.annotation)
        docs = self.build()
        self.assertEqual(self.annotation, original)
        m = docs["map.json"]["map"]
        self.assertEqual(Polygon(m["boundary"]).bounds, (0, 0, 20, 10))
        self.assertEqual(m["start"], [1.25, 5])
        self.assertEqual(m["goal"], [18.75, 5])
        self.assertAlmostEqual(docs["import_audit.json"]["free_area"], (160*80-20*30)*.125**2)
        self.assertEqual(docs["map.json"]["provenance"]["calibration"]["status"], "simulation_normalized")
        self.assertIsNone(docs["map.json"]["provenance"]["calibration"]["metres_per_pixel"])
        self.assertTrue(World(docs["map.json"]).path_valid(docs["reference.json"]["path"]))
        self.assertIn("simulation m", docs["graph.svg"])
        self.assertEqual({n for n in docs if n.endswith((".svg", ".png"))},
                         {"graph.svg", "satellite_overlay.png"})
        with Image.open(io.BytesIO(docs["satellite_overlay.png"])) as overlay:
            self.assertEqual(overlay.size, self.image.size)

    def test_cli_discovers_sidecar_exports_binary_and_refuses_stale_case(self):
        (self.root / "annotations.json").write_text(json.dumps(self.annotation))
        output = self.root / "case"
        args = ["build", "--image", str(self.image_path), "--output", str(output), "--grid-step", ".5"]
        self.assertEqual(main(args), 0)
        expected = {"map.json", "regions.json", "graph.json", "reference.json", "import_audit.json",
                    "annotations.json", "pipeline_status.json", "graph.svg", "satellite_overlay.png"}
        self.assertEqual({p.name for p in output.iterdir()}, expected)
        self.assertEqual(main(args), 2)
        self.assertFalse((output / "llm_prior.json").exists())

    def test_prior_compatible_with_both_research_and_cpp(self):
        docs = self.build()
        output = self.root / "case"
        save_documents(docs, output)
        def provider(graph):
            return {"region_scores": [{"id": v["id"], "score": .7, "reason": "fixture"}
                                      for v in graph["vertices"]]}, {"source": "unit_test_fixture"}
        prior = score_case(output, self.root / "unused.env", provider=provider)
        self.assertEqual(set(prior["scores"]), {v["id"] for v in docs["graph.json"]["vertices"]})
        sampling = json.loads((output / "sampling_prior.json").read_text())
        self.assertEqual(len(sampling["regions"]), len(prior["scores"]))
        self.assertEqual(sampling["start_region"], docs["graph.json"]["planning"]["start_region"])
        self.assertEqual(json.loads((output / "pipeline_status.json").read_text())["llm"], "complete")
        with self.assertRaisesRegex(ValueError, "đã có prior"):
            score_case(output, self.root / "unused.env", provider=provider)

    def test_llm_failure_and_missing_regions_do_not_publish_fake_prior(self):
        for mode in ("failure", "missing"):
            with self.subTest(mode=mode):
                output = self.root / mode
                save_documents(self.build(), output)
                def provider(graph):
                    if mode == "failure":
                        raise ValueError("provider unavailable")
                    return {"region_scores": [{"id": graph["vertices"][0]["id"], "score": .7}]}, {}
                with warnings.catch_warnings(), self.assertRaises(ValueError):
                    warnings.simplefilter("ignore")
                    score_case(output, self.root / "unused.env", provider=provider)
                self.assertFalse((output / "llm_prior.json").exists())
                self.assertFalse((output / "sampling_prior.json").exists())
                self.assertEqual(json.loads((output / "pipeline_status.json").read_text())["llm"], "failed")

    def test_calibrated_mode_does_not_invent_scale_and_grid_is_bounded(self):
        with self.assertRaises(ValueError):
            build_case(self.image, self.identity, self.annotation, scale_mode="calibrated")
        with self.assertRaisesRegex(ValueError, "lưới"):
            build_case(self.image, self.identity, self.annotation, grid_step=.00001)

    def test_reasoning_setting_reaches_transport_without_changing_research_default(self):
        from research.llm_study import StudyProvider
        from llm_weight_provider import OpenRouterWeightProvider
        graph = self.build()["graph.json"]
        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}), \
             mock.patch.object(OpenRouterWeightProvider, "_request_http_json", return_value={}) as transport:
            for kwargs, expected in (({}, "low"), ({"reasoning_effort": "none"}, "none")):
                provider = StudyProvider(graph, self.root / expected, self.root / "unused.env", **kwargs)
                request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                                                 data=b'{"model":"openrouter/free"}')
                provider._request_http_json(request)
                sent = json.loads(transport.call_args.args[0].data)
                self.assertEqual(sent["reasoning"], {"effort": expected, "exclude": True})


if __name__ == "__main__":
    unittest.main()
