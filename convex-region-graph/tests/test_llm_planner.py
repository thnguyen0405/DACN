import io
import json
import os
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from graph_utils import GraphValidationError, prepare_planning_graph
from llm_planner import main, plan_route
from llm_weight_provider import (
    DEFAULT_OPENROUTER_BASE_URL,
    DEFAULT_OPENROUTER_MODEL,
    DuplicateEdgeWeightWarning,
    LLMProviderError,
    LLMWeightProvider,
    OpenRouterWeightProvider,
    validate_edge_weights,
)
from weighted_search import dijkstra_region_path


def vertex(region_id):
    return {"id": region_id, "centroid": [0.0, 0.0], "polygon": []}


def edge(source, target, relation="shared_edge"):
    return {"source": source, "target": target, "relation": relation}


class FakeWeightProvider(LLMWeightProvider):
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def get_edge_weights(self, graph, start_region, goal_region):
        self.calls += 1
        return self.response


class FakeHTTPResponse:
    def __init__(
        self,
        payload=None,
        *,
        raw_body=None,
        status=200,
        content_type="application/json",
    ):
        self.raw_body = (
            raw_body if raw_body is not None else json.dumps(payload).encode("utf-8")
        )
        self.status = status
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.raw_body

    def getcode(self):
        return self.status


class GraphRuleTests(unittest.TestCase):
    def test_undirected_edges_are_not_used(self):
        graph = {
            "vertices": [vertex("A"), vertex("B")],
            "directed_edges": [],
            "undirected_edges": [edge("A", "B")],
        }
        prepared = prepare_planning_graph(graph)
        route = dijkstra_region_path(prepared, {}, "A", "B")
        self.assertFalse(route["valid"])
        self.assertEqual(route["sequence"], [])

    def test_directed_edge_orientation_is_preserved(self):
        graph = {
            "vertices": [vertex("A"), vertex("B")],
            "directed_edges": [edge("A", "B")],
        }
        prepared = prepare_planning_graph(graph)
        weights = {("A", "B"): 0.2}
        self.assertFalse(dijkstra_region_path(prepared, weights, "B", "A")["valid"])

    def test_unknown_graph_endpoint_is_rejected(self):
        graph = {"vertices": [vertex("A")], "directed_edges": [edge("A", "B")]}
        with self.assertRaises(GraphValidationError):
            prepare_planning_graph(graph)


class LLMValidationTests(unittest.TestCase):
    def setUp(self):
        self.graph = prepare_planning_graph(
            {
                "vertices": [vertex("A"), vertex("B"), vertex("C")],
                "directed_edges": [edge("A", "B"), edge("B", "C")],
            }
        )

    def response(self, source="A", target="B", weight=0.2):
        return {"edge_weights": [{"source": source, "target": target, "weight": weight}]}

    def test_unknown_region_is_rejected(self):
        with self.assertRaisesRegex(LLMProviderError, "unknown region"):
            validate_edge_weights(self.response("A", "X"), self.graph)

    def test_unknown_edge_is_rejected(self):
        with self.assertRaisesRegex(LLMProviderError, "nonexistent"):
            validate_edge_weights(self.response("A", "C"), self.graph)

    def test_negative_weight_is_rejected(self):
        with self.assertRaisesRegex(LLMProviderError, "greater than 0"):
            validate_edge_weights(self.response(weight=-0.01), self.graph)

    def test_zero_weight_is_rejected(self):
        with self.assertRaisesRegex(
            LLMProviderError,
            "Weight must be greater than 0 and less than or equal to 1",
        ):
            validate_edge_weights(self.response(weight=0.0), self.graph)

    def test_positive_weights_through_one_are_accepted(self):
        response = {
            "edge_weights": [
                {"source": "A", "target": "B", "weight": 0.0001},
                {"source": "B", "target": "C", "weight": 1.0},
            ]
        }
        weights, missing = validate_edge_weights(response, self.graph)
        self.assertEqual(weights, {("A", "B"): 0.0001, ("B", "C"): 1.0})
        self.assertEqual(missing, [])

    def test_weight_above_one_is_rejected(self):
        with self.assertRaisesRegex(LLMProviderError, "less than or equal to 1"):
            validate_edge_weights(self.response(weight=1.01), self.graph)

    def test_invalid_json_is_rejected(self):
        with self.assertRaisesRegex(LLMProviderError, "invalid JSON"):
            validate_edge_weights("not JSON", self.graph)

    def test_missing_weight_gets_neutral_default(self):
        weights, missing = validate_edge_weights(self.response(), self.graph)
        self.assertEqual(weights[("B", "C")], 0.5)
        self.assertEqual(missing, [("B", "C")])

    def test_no_usable_weights_is_rejected(self):
        with self.assertRaisesRegex(LLMProviderError, "no usable"):
            validate_edge_weights({"edge_weights": []}, self.graph)

    def test_provider_metadata_is_ignored_during_validation(self):
        response = self.response()
        response["provider_metadata"] = {
            "provider": "openrouter",
            "requested_model": "openrouter/free",
            "resolved_model": "example/free-model",
            "temperature": 0.0,
        }
        weights, missing = validate_edge_weights(response, self.graph)
        self.assertEqual(weights[("A", "B")], 0.2)
        self.assertEqual(missing, [("B", "C")])

    def test_identical_duplicate_is_accepted_with_warning(self):
        response = {
            "edge_weights": [
                {"source": "A", "target": "B", "weight": 0.18},
                {"source": "A", "target": "B", "weight": 0.18},
            ]
        }
        with self.assertWarns(DuplicateEdgeWeightWarning):
            weights, missing = validate_edge_weights(response, self.graph)
        self.assertEqual(weights[("A", "B")], 0.18)
        self.assertEqual(missing, [("B", "C")])

    def test_conflicting_duplicate_is_rejected(self):
        response = {
            "edge_weights": [
                {"source": "A", "target": "B", "weight": 0.18},
                {"source": "A", "target": "B", "weight": 0.60},
            ]
        }
        with self.assertRaisesRegex(LLMProviderError, "Conflicting duplicate weights"):
            validate_edge_weights(response, self.graph)


class OpenRouterProviderTests(unittest.TestCase):
    def setUp(self):
        self.prompt_path = Path(__file__).parents[1] / "prompts" / "edge_weight_prompt.txt"
        self.graph = prepare_planning_graph(
            {
                "vertices": [vertex("A"), vertex("B")],
                "directed_edges": [edge("A", "B")],
            }
        )

    def provider(self, **overrides):
        options = {
            "prompt_path": self.prompt_path,
            "api_key": "test-key",
            "model": DEFAULT_OPENROUTER_MODEL,
            "base_url": DEFAULT_OPENROUTER_BASE_URL,
            "temperature": 0.0,
        }
        options.update(overrides)
        return OpenRouterWeightProvider(**options)

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_valid_openrouter_json_response(self, mock_urlopen):
        expected = {
            "edge_weights": [
                {"source": "A", "target": "B", "weight": 0.2, "reason": "Direct edge."}
            ]
        }
        mock_urlopen.return_value = FakeHTTPResponse(
            {
                "model": "example/resolved-free-model",
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps(expected)}}
                ],
            }
        )

        result = self.provider().get_edge_weights(self.graph, "A", "B")

        self.assertEqual(result["edge_weights"], expected["edge_weights"])
        self.assertEqual(
            result["provider_metadata"],
            {
                "provider": "openrouter",
                "requested_model": DEFAULT_OPENROUTER_MODEL,
                "resolved_model": "example/resolved-free-model",
                "temperature": 0.0,
            },
        )
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url, "https://openrouter.ai/api/v1/chat/completions"
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(request.get_header("Accept"), "application/json")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], DEFAULT_OPENROUTER_MODEL)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIs(body["stream"], False)
        self.assertEqual(body["temperature"], 0.0)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertIn('"start_region": "A"', body["messages"][0]["content"])
        self.assertNotIn("models", body)

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_temperature_from_environment_is_sent(self, mock_urlopen):
        expected = {
            "edge_weights": [{"source": "A", "target": "B", "weight": 0.2}]
        }
        mock_urlopen.return_value = FakeHTTPResponse(
            {
                "model": "example/resolved-free-model",
                "choices": [{"message": {"content": json.dumps(expected)}}],
            }
        )
        with patch.dict(os.environ, {"OPENROUTER_TEMPERATURE": "0.2"}):
            provider = OpenRouterWeightProvider(
                self.prompt_path,
                api_key="test-key",
                model=DEFAULT_OPENROUTER_MODEL,
                base_url=DEFAULT_OPENROUTER_BASE_URL,
            )
            result = provider.get_edge_weights(self.graph, "A", "B")

        request = mock_urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["temperature"], 0.2)
        self.assertEqual(result["provider_metadata"]["temperature"], 0.2)

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_temperature_defaults_to_zero(self, mock_urlopen):
        expected = {
            "edge_weights": [{"source": "A", "target": "B", "weight": 0.2}]
        }
        mock_urlopen.return_value = FakeHTTPResponse(
            {"choices": [{"message": {"content": json.dumps(expected)}}]}
        )
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenRouterWeightProvider(
                self.prompt_path,
                api_key="test-key",
                model=DEFAULT_OPENROUTER_MODEL,
                base_url=DEFAULT_OPENROUTER_BASE_URL,
            )
            provider.get_edge_weights(self.graph, "A", "B")

        request = mock_urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["temperature"], 0.0)

    def test_missing_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(LLMProviderError, "OPENROUTER_API_KEY is not set"):
                OpenRouterWeightProvider(self.prompt_path)

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_invalid_model_json_response(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(
            {"choices": [{"message": {"content": "not JSON"}}]}
        )
        with self.assertRaisesRegex(LLMProviderError, "LLM model content returned invalid JSON"):
            self.provider().get_edge_weights(self.graph, "A", "B")

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_malformed_http_body_is_saved_and_retry_fails(self, mock_urlopen):
        malformed = b'{"choices":[{"message":{"content":"truncated"}}'
        mock_urlopen.return_value = FakeHTTPResponse(raw_body=malformed)
        with tempfile.TemporaryDirectory() as temp_dir:
            debug_path = Path(temp_dir) / "openrouter_invalid_response.txt"
            output = io.StringIO()
            with redirect_stdout(output):
                with self.assertRaises(LLMProviderError) as caught:
                    self.provider(debug_response_path=debug_path).get_edge_weights(
                        self.graph, "A", "B"
                    )

            message = str(caught.exception)
            self.assertIn("OpenRouter returned invalid HTTP JSON", message)
            self.assertIn("HTTP status: 200", message)
            self.assertIn("Content-Type: application/json", message)
            self.assertIn(f"Response bytes: {len(malformed)}", message)
            self.assertIn("JSON parsing error:", message)
            self.assertIn(str(debug_path), message)
            self.assertEqual(debug_path.read_bytes(), malformed)
            self.assertEqual(mock_urlopen.call_count, 2)
            self.assertIn(
                "Retrying OpenRouter request once because the response was malformed...",
                output.getvalue(),
            )

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_unexpected_sse_is_reported_without_retry(self, mock_urlopen):
        sse_body = b'data: {"choices":[]}\n\ndata: [DONE]\n'
        mock_urlopen.return_value = FakeHTTPResponse(
            raw_body=sse_body, content_type="text/event-stream; charset=utf-8"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            debug_path = Path(temp_dir) / "openrouter_invalid_response.txt"
            with self.assertRaisesRegex(
                LLMProviderError, "unexpected streaming/SSE response"
            ):
                self.provider(debug_response_path=debug_path).get_edge_weights(
                    self.graph, "A", "B"
                )
            self.assertEqual(debug_path.read_bytes(), sse_body)
            self.assertEqual(mock_urlopen.call_count, 1)

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_one_retry_succeeds_after_malformed_response(self, mock_urlopen):
        expected = {
            "edge_weights": [
                {"source": "A", "target": "B", "weight": 0.2}
            ]
        }
        mock_urlopen.side_effect = [
            FakeHTTPResponse(raw_body=b'{"truncated":'),
            FakeHTTPResponse(
                {"choices": [{"message": {"content": json.dumps(expected)}}]}
            ),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with redirect_stdout(output):
                result = self.provider(
                    debug_response_path=Path(temp_dir) / "invalid.txt"
                ).get_edge_weights(self.graph, "A", "B")
        self.assertEqual(result["edge_weights"], expected["edge_weights"])
        self.assertIsNone(result["provider_metadata"]["resolved_model"])
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertIn("response was malformed", output.getvalue())

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_api_key_is_redacted_from_errors_and_debug_file(self, mock_urlopen):
        secret = "test-secret-key"
        mock_urlopen.return_value = FakeHTTPResponse(
            raw_body=f"not-json {secret}".encode("utf-8"),
            content_type="text/plain",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            debug_path = Path(temp_dir) / "invalid.txt"
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(LLMProviderError) as caught:
                    self.provider(
                        api_key=secret, debug_response_path=debug_path
                    ).get_edge_weights(self.graph, "A", "B")
            self.assertNotIn(secret, str(caught.exception))
            self.assertNotIn(secret, debug_path.read_text(encoding="utf-8"))
            self.assertIn("[REDACTED]", debug_path.read_text(encoding="utf-8"))

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_invalid_key_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":{"message":"Invalid API key"}}'),
        )
        with self.assertRaisesRegex(LLMProviderError, "Check OPENROUTER_API_KEY"):
            self.provider().get_edge_weights(self.graph, "A", "B")

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_http_rate_limit_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error":{"message":"Rate limit exceeded"}}'),
        )
        with self.assertRaisesRegex(LLMProviderError, "rate limit reached"):
            self.provider().get_edge_weights(self.graph, "A", "B")
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_unsupported_response_format_is_clear(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions",
            400,
            "Bad Request",
            {},
            io.BytesIO(
                b'{"error":{"message":"response_format is not supported"}}'
            ),
        )
        with self.assertRaisesRegex(LLMProviderError, "does not support response_format"):
            self.provider().get_edge_weights(self.graph, "A", "B")
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_model_unavailable_suggests_free_router(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b'{"error":{"message":"No endpoints available"}}'),
        )
        with redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(LLMProviderError, "No paid fallback"):
                self.provider().get_edge_weights(self.graph, "A", "B")
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("llm_weight_provider.urllib.request.urlopen")
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("offline")
        with redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(LLMProviderError, "OpenRouter network error"):
                self.provider().get_edge_weights(self.graph, "A", "B")


class CLIResponseMetadataTests(unittest.TestCase):
    def test_resolved_model_is_printed_and_saved(self):
        graph = {
            "vertices": [vertex("A"), vertex("B")],
            "directed_edges": [edge("A", "B")],
        }
        response = {
            "provider_metadata": {
                "provider": "openrouter",
                "requested_model": "openrouter/free",
                "resolved_model": "example/resolved-free-model",
                "temperature": 0.0,
            },
            "edge_weights": [{"source": "A", "target": "B", "weight": 0.2}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            graph_path = temp_path / "graph.json"
            weights_path = temp_path / "weights.json"
            graph_path.write_text(json.dumps(graph), encoding="utf-8")
            output = io.StringIO()
            with patch(
                "llm_planner.OpenRouterWeightProvider",
                return_value=FakeWeightProvider(response),
            ):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            str(graph_path),
                            "--start",
                            "A",
                            "--goal",
                            "B",
                            "--env-file",
                            str(temp_path / "missing.env"),
                            "--weights-output",
                            str(weights_path),
                            "--route-output",
                            str(temp_path / "route.json"),
                            "--svg-output",
                            str(temp_path / "route.svg"),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            self.assertIn("Requested model: openrouter/free", output.getvalue())
            self.assertIn(
                "Resolved model: example/resolved-free-model", output.getvalue()
            )
            saved = json.loads(weights_path.read_text(encoding="utf-8"))
            self.assertEqual(saved, response)


class DijkstraTests(unittest.TestCase):
    def setUp(self):
        self.graph = prepare_planning_graph(
            {
                "vertices": [vertex("A"), vertex("B"), vertex("C"), vertex("D")],
                "directed_edges": [
                    edge("A", "B"),
                    edge("B", "D"),
                    edge("A", "C"),
                    edge("C", "D"),
                ],
            }
        )
        self.weights = {
            ("A", "B"): 0.2,
            ("B", "D"): 0.2,
            ("A", "C"): 0.1,
            ("C", "D"): 0.8,
        }

    def test_minimum_cost_valid_path_is_selected(self):
        route = dijkstra_region_path(self.graph, self.weights, "A", "D")
        self.assertTrue(route["valid"])
        self.assertEqual(route["sequence"], ["A", "B", "D"])
        self.assertEqual(route["total_cost"], 0.4)
        real_edges = {(e["source"], e["target"]) for e in self.graph["directed_edges"]}
        self.assertTrue(
            all(pair in real_edges for pair in zip(route["sequence"], route["sequence"][1:]))
        )

    def test_no_path_returns_invalid_empty_sequence(self):
        route = dijkstra_region_path(self.graph, self.weights, "D", "A")
        self.assertFalse(route["valid"])
        self.assertEqual(route["sequence"], [])
        self.assertIn("No directed path", route["reason"])

    def test_pipeline_uses_mock_provider_without_network(self):
        response = {
            "edge_weights": [
                {"source": source, "target": target, "weight": weight}
                for (source, target), weight in self.weights.items()
            ]
        }
        provider = FakeWeightProvider(response)
        route, _, _, missing = plan_route(
            self.graph, "A", "D", provider=provider
        )
        self.assertEqual(provider.calls, 1)
        self.assertEqual(route["sequence"], ["A", "B", "D"])
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
