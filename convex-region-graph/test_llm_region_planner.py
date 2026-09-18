import unittest

from llm_region_planner import PlanningError, plan_regions, prepare_safe_portal_graph


def vertex(region_id, polygon):
    return {"id": region_id, "centroid": [sum(p[0] for p in polygon) / len(polygon), sum(p[1] for p in polygon) / len(polygon)], "polygon": polygon}


def edge(source, target, relation="safe_portal"):
    return {"source": source, "target": target, "relation": relation, "safe_portal_width": 1.0}


def graph():
    return {
        "directed": True,
        "planning": {"start": [0.25, 0.5], "goal": [1.75, 0.5]},
        "vertices": [
            vertex("A", [[0, 0], [1, 0], [1, 1], [0, 1]]),
            vertex("B", [[1, 0], [2, 0], [2, 1], [1, 1]]),
        ],
        "directed_edges": [edge("A", "B"), edge("B", "A")],
    }


class LLMRegionPlannerTests(unittest.TestCase):
    def test_uses_map_start_goal_and_builds_nonzero_prior(self):
        plan = plan_regions(
            graph(),
            {"region_scores": [{"id": "A", "score": 0.8}, {"id": "B", "score": 1.0}], "edge_costs": []},
        )
        self.assertEqual(plan["start_region"], "A")
        self.assertEqual(plan["goal_region"], "B")
        self.assertEqual(plan["route"]["sequence"], ["A", "B"])
        self.assertAlmostEqual(sum(item["probability"] for item in plan["sampling_prior"]), 1.0)
        self.assertTrue(all(item["probability"] > 0.0 for item in plan["sampling_prior"]))
        self.assertEqual(plan["model_completion"]["derived_edge_costs"], [{"source": "A", "target": "B"}, {"source": "B", "target": "A"}])

    def test_invented_edge_is_rejected(self):
        with self.assertRaisesRegex(PlanningError, "nonexistent safe portal"):
            plan_regions(
                graph(),
                {"region_scores": [], "edge_costs": [{"source": "A", "target": "C", "cost": 0.2}]},
            )

    def test_graph_rejects_non_safe_portal_edge(self):
        invalid = graph()
        invalid["directed_edges"][0]["relation"] = "point_contact"
        with self.assertRaisesRegex(PlanningError, "not a safe_portal"):
            prepare_safe_portal_graph(invalid)

    def test_explicit_region_overrides_map_lookup(self):
        plan = plan_regions(
            graph(),
            {"region_scores": [], "edge_costs": [{"source": "B", "target": "A", "cost": 0.1}]},
            start_region="B",
            goal_region="A",
        )
        self.assertEqual(plan["route"]["sequence"], ["B", "A"])


if __name__ == "__main__":
    unittest.main()
