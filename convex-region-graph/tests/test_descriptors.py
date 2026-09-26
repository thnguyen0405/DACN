import math
import unittest
from build_graph import build_pipeline
from region_descriptors import polygon_moments
from llm_region_planner import compact_llm_input, prepare_safe_portal_graph

class DescriptorTests(unittest.TestCase):
    def test_square_exact_moments_translation_and_winding(self):
        square=[[0,0],[2,0],[2,2],[0,2]]
        for poly in (square, square[::-1], [[x+10000,y-10000] for x,y in square]):
            d=polygon_moments(poly)
            self.assertAlmostEqual(d['area'],4)
            self.assertAlmostEqual(d['diameter'],math.sqrt(8))
            self.assertAlmostEqual(d['aspect_ratio'],1)
            self.assertAlmostEqual(d['compactness'],4/math.pi)
            self.assertAlmostEqual(d['covariance_eigenvalues'][0],1/3)

    def test_rectangle_ratio_is_eigenvalue_ratio_not_side_ratio(self):
        d=polygon_moments([[0,0],[4,0],[4,1],[0,1]])
        self.assertAlmostEqual(d['aspect_ratio'],16)

    def test_square_mean_clearance_and_prompt_survive_validation(self):
        graph,_,_=build_pipeline({'map':{'boundary':[[0,0],[2,0],[2,2],[0,2]],'obstacles':[]}})
        # Exact area mean of distance to boundary of a side-2 square = 1/3.
        d=graph['vertices'][0]['descriptors']
        self.assertAlmostEqual(d['mean_clearance'],1/3,delta=.015)
        self.assertAlmostEqual(d['centroid_clearance'],1)
        self.assertEqual(d['conductance'],0)
        payload=compact_llm_input(prepare_safe_portal_graph(graph),'C0','C0')
        self.assertEqual(payload['regions'][0]['descriptors'],d)
        self.assertIn('mean_clearance_method',payload['descriptor_metadata'])

    def test_missing_map_means_unknown_clearance(self):
        graph,_,_=build_pipeline({'regions':[
            {'id':'a','polygon':[[0,0],[1,0],[1,1],[0,1]]},
            {'id':'b','polygon':[[1,0],[2,0],[2,1],[1,1]]}]})
        self.assertAlmostEqual(graph['vertices'][0]['descriptors']['conductance'],.25)
        self.assertEqual(graph['vertices'][0]['descriptors']['degree'],1)
        self.assertIsNone(graph['vertices'][0]['descriptors']['mean_clearance'])
        self.assertIsNone(graph['directed_edges'][0]['traversability'])

    def test_narrow_portal_preserves_intrinsic_but_not_safe_connectivity(self):
        from build_graph import build_graph
        from region_descriptors import enrich_graph
        graph=build_graph({'regions':[
            {'id':'a','polygon':[[0,0],[1,0],[1,1],[0,1]]},
            {'id':'b','polygon':[[1,0],[2,0],[2,1],[1,1]]}]},required_clearance=.5)
        enrich_graph(graph)
        d=graph['vertices'][0]['descriptors']
        self.assertEqual(d['degree'],1)
        self.assertEqual(d['safe_degree'],0)
        self.assertAlmostEqual(d['conductance'],.25)
        self.assertEqual(d['safe_conductance'],0)
