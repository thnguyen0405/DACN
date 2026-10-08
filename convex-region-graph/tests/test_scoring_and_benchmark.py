import importlib.util
import math
from pathlib import Path
import unittest

from export_sampling_corridor import CorridorExportError, build_sampling_corridor
from llm_region_planner import plan_regions
from llm_weight_provider import graph_prompt_data
from scoring import deterministic_scoring


def demo_graph():
    vertices = []
    for index in range(3):
        vertices.append({
            "id": f"C{index}", "centroid": [index + 0.5, 0.5], "area": 1.0,
            "polygon": [[index, 0], [index + 1, 0], [index + 1, 1], [index, 1]],
            "descriptors": {"diameter": math.sqrt(2), "aspect_ratio": 1.0,
                "compactness": 1.27, "mean_clearance": 0.5, "centroid_clearance": 0.5,
                "degree": 2, "safe_degree": 2, "conductance": 0.25, "safe_conductance": 0.2},
        })
    edges = []
    for source, target in (("C0", "C1"), ("C1", "C0"), ("C1", "C2"), ("C2", "C1")):
        x = 1.0 if {source, target} == {"C0", "C1"} else 2.0
        edges.append({"source": source, "target": target, "relation": "safe_portal",
            "portal": [[x, 0], [x, 1]], "safe_portal": [[x, .2], [x, .8]],
            "portal_width": 1.0, "safe_portal_width": .6,
            "traversability": .5, "safe_traversability": .3})
    return {"directed": True, "planning": {"start": [.5, .5], "goal": [2.5, .5],
        "robot_radius": .2, "safety_margin": .1, "required_clearance": .3},
        "vertices": vertices, "directed_edges": edges}


class ScoringTests(unittest.TestCase):
    def test_deterministic_scores_are_explicitly_non_llm_and_finite(self):
        result = deterministic_scoring(demo_graph(), "C0", "C2")
        self.assertEqual(result["scoring_mode"], "deterministic_heuristic")
        self.assertEqual(len(result["region_scores"]), 3)
        self.assertEqual(len(result["edge_costs"]), 4)
        self.assertTrue(all(0 <= item["score"] <= 1 for item in result["region_scores"]))
        self.assertTrue(all(0 < item["cost"] <= 1 for item in result["edge_costs"]))
        self.assertTrue(all("not LLM" in item["reason"] for item in result["edge_costs"]))

    def test_missing_llm_edges_use_geometry_aware_costs(self):
        plan = plan_regions(demo_graph(), {"region_scores": [{"id": "C0", "score": .5}], "edge_costs": []})
        costs = {(item["source"], item["target"]): item["cost"] for item in plan["edge_costs"]}
        self.assertTrue(any(cost != .5 for cost in costs.values()))
        self.assertEqual(plan["route"]["sequence"], ["C0", "C1", "C2"])

    def test_prompt_schema_contains_real_geometry_and_robot_model(self):
        payload = graph_prompt_data(demo_graph(), "C0", "C2")
        self.assertEqual(payload["start"]["coordinates"], [.5, .5])
        self.assertEqual(payload["robot"]["required_clearance"], .3)
        self.assertIn("safe_portal", payload["directed_edges"][0])
        self.assertIn("diameter", payload["regions"][0])


class SequenceExportTests(unittest.TestCase):
    def test_sequence_scores_order_portals_and_exploration_are_preserved(self):
        graph = demo_graph()
        route = {"start_region": "C0", "goal_region": "C2", "sequence": ["C0", "C1", "C2"]}
        prior = {"region_scores": [{"id": "C0", "score": .2}, {"id": "C1", "score": .8}, {"id": "C2", "score": 1.0}]}
        strategy = build_sampling_corridor(graph, route, prior, .8, .25)
        self.assertEqual(strategy["sequence"], ["C0", "C1", "C2"])
        self.assertEqual([r["score"] for r in strategy["regions"]], [.2, .8, 1.0])
        self.assertEqual(len(strategy["portals"]), 2)
        self.assertEqual(strategy["global_exploration_probability"], .2)

    def test_nonexistent_sequence_edge_is_rejected(self):
        with self.assertRaisesRegex(CorridorExportError, "nonexistent directed edge"):
            build_sampling_corridor(demo_graph(), {"sequence": ["C0", "C2"]})


class BenchmarkCalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parents[2] / "sampling-based-path-finding-main" / "scripts" / "benchmark.py"
        spec = importlib.util.spec_from_file_location("benchmark_module", path)
        cls.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.module)

    def test_ansi_color_does_not_corrupt_last_metric(self):
        line = "\x1b[0m[INFO] [RESULT] planner=rrt guidance=none success=1 planning_time_ms=12 time_to_first_solution_ms=2 path_length=5 straight_line_distance=4 path_length_ratio=1.25 iterations=30 nodes_added=20\x1b[0m\n"
        self.assertEqual(self.module.parse_result(line)["nodes_added"], 20)
        self.assertIsNone(self.module.parse_result(line.replace("nodes_added=20", "nodes_added=broken")))

    def test_parse_and_summary(self):
        text = "[RESULT] planner=rrt guidance=none success=1 planning_time_ms=12.5 time_to_first_solution_ms=8 path_length=5 straight_line_distance=4 path_length_ratio=1.25 iterations=10 nodes_added=8"
        row = self.module.parse_result(text)
        row["seed"] = 42
        self.assertEqual(row["path_length_ratio"], 1.25)
        summary = self.module.summarize([row])
        self.assertEqual(summary[0]["success_rate"], 1.0)
        self.assertEqual(summary[0]["iterations_mean"], 10.0)

    def test_failed_run_has_no_path_length(self):
        text = "[RESULT] planner=rrt guidance=none success=0 planning_time_ms=100 time_to_first_solution_ms=-1 path_length=-1 straight_line_distance=4 path_length_ratio=-1 iterations=10 nodes_added=8"
        row = self.module.parse_result(text)
        self.assertIsNone(row["path_length"])
        self.assertIsNone(row["path_length_ratio"])


if __name__ == "__main__":
    unittest.main()
