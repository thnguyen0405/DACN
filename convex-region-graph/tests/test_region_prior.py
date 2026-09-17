import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from export_sampling_prior import build_sampling_prior
from graph_utils import prepare_planning_graph
from llm_region_prior import (
    MISSING_REGION_SCORE,
    MissingRegionScoreWarning,
    OpenRouterRegionPriorProvider,
    build_region_prior,
    validate_region_scores,
)
from llm_weight_provider import LLMProviderError


def vertex(region_id, x=0.0):
    return {
        "id": region_id,
        "centroid": [x + 0.5, 0.5],
        "polygon": [[x, 0.0], [x + 1.0, 0.0], [x + 1.0, 1.0], [x, 1.0]],
    }


class RegionPriorValidationTests(unittest.TestCase):
    def setUp(self):
        self.raw_graph = {
            "vertices": [vertex("A", 0.0), vertex("B", 1.0), vertex("C", 2.0)],
            "directed_edges": [
                {"source": "A", "target": "B", "relation": "shared_edge"},
                {"source": "B", "target": "C", "relation": "shared_edge"},
            ],
        }
        self.graph = prepare_planning_graph(self.raw_graph)

    def test_valid_scores(self):
        scores, missing = validate_region_scores(
            {"region_scores": [
                {"id": "A", "score": 0.2},
                {"id": "B", "score": 1.0},
                {"id": "C", "score": 0.4},
            ]},
            self.graph,
        )
        self.assertEqual(scores, {"A": 0.2, "B": 1.0, "C": 0.4})
        self.assertEqual(missing, [])

    def test_duplicate_region_is_rejected(self):
        with self.assertRaisesRegex(LLMProviderError, "Duplicate"):
            validate_region_scores(
                {"region_scores": [
                    {"id": "A", "score": 0.2},
                    {"id": "A", "score": 0.2},
                ]},
                self.graph,
            )

    def test_unknown_region_is_rejected(self):
        with self.assertRaisesRegex(LLMProviderError, "unknown region"):
            validate_region_scores(
                {"region_scores": [{"id": "X", "score": 0.2}]}, self.graph
            )

    def test_invalid_scores_are_rejected(self):
        for score in (0.0, -0.1, 1.1, True, "0.5", math.inf, math.nan):
            with self.subTest(score=score):
                with self.assertRaises(LLMProviderError):
                    validate_region_scores(
                        {"region_scores": [{"id": "A", "score": score}]}, self.graph
                    )

    def test_completely_empty_response_is_rejected(self):
        with self.assertRaisesRegex(LLMProviderError, "no usable"):
            validate_region_scores({"region_scores": []}, self.graph)

    def test_missing_scores_receive_documented_fallback(self):
        with self.assertWarns(MissingRegionScoreWarning):
            scores, missing = validate_region_scores(
                {"region_scores": [{"id": "B", "score": 0.8}]}, self.graph
            )
        self.assertEqual(missing, ["A", "C"])
        self.assertEqual(scores["A"], MISSING_REGION_SCORE)
        self.assertEqual(scores["C"], MISSING_REGION_SCORE)

    def test_normalized_prior_preserves_metadata_and_reasons(self):
        response = {
            "provider_metadata": {"provider": "test"},
            "region_scores": [
                {"id": "A", "score": 0.4, "reason": "start"},
                {"id": "B", "score": 0.8, "reason": "connector"},
                {"id": "C", "score": 0.9, "reason": "goal"},
            ],
        }
        prior, _, _, missing = build_region_prior(
            self.raw_graph, "A", "C", response=response
        )
        self.assertEqual(missing, [])
        self.assertEqual(prior["provider_metadata"], {"provider": "test"})
        self.assertEqual(prior["start_region"], "A")
        self.assertEqual(prior["goal_region"], "C")
        self.assertEqual(prior["region_scores"][1]["reason"], "connector")


class SamplingPriorExporterTests(unittest.TestCase):
    def setUp(self):
        self.graph = {
            "vertices": [vertex("A", 0.0), vertex("B", 1.0)],
            "directed_edges": [
                {"source": "A", "target": "B", "relation": "shared_edge"}
            ],
        }

    def test_export_contains_every_polygon_and_score(self):
        sampling_prior, missing = build_sampling_prior(
            self.graph,
            {
                "start_region": "A",
                "goal_region": "B",
                "region_scores": [
                    {"id": "A", "score": 0.25},
                    {"id": "B", "score": 0.75},
                ],
            },
        )
        self.assertEqual(missing, [])
        self.assertEqual([r["id"] for r in sampling_prior["regions"]], ["A", "B"])
        self.assertEqual([r["score"] for r in sampling_prior["regions"]], [0.25, 0.75])
        self.assertEqual(sampling_prior["regions"][0]["polygon"], self.graph["vertices"][0]["polygon"])

    def test_export_rejects_unknown_endpoint(self):
        with self.assertRaisesRegex(ValueError, "Unknown goal"):
            build_sampling_prior(
                self.graph,
                {
                    "start_region": "A",
                    "goal_region": "X",
                    "region_scores": [{"id": "A", "score": 1.0}],
                },
            )


class OpenRouterRegionPriorProviderTests(unittest.TestCase):
    @patch.object(OpenRouterRegionPriorProvider, "_get_model_json")
    def test_provider_uses_region_prompt_and_metadata(self, mock_request):
        mock_request.return_value = (
            {"region_scores": [{"id": "A", "score": 1.0}]},
            "resolved/model",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt = Path(temp_dir) / "prompt.txt"
            prompt.write_text("score regions", encoding="utf-8")
            provider = OpenRouterRegionPriorProvider(prompt, api_key="secret")
            graph = {
                "vertices": [vertex("A")],
                "directed_edges": [],
            }
            response = provider.get_region_scores(graph, "A", "A")

        sent_prompt = mock_request.call_args.args[0]
        self.assertIn("score regions", sent_prompt)
        self.assertIn('"start_region": "A"', sent_prompt)
        self.assertEqual(response["provider_metadata"]["resolved_model"], "resolved/model")
        self.assertEqual(response["region_scores"][0]["id"], "A")


if __name__ == "__main__":
    unittest.main()
