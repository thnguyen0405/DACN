"""Query preparation and scoring contract tests; no Ollama server required."""
from copy import deepcopy
import itertools
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

from prepare_scoring_data import (load_config, prepare, prepare_file, query_paths,
    path_cost, sigmoid, weighted_graph, yen_paths)
from score_maps import score_map, score_prepared, validate_answer, explanation_review_flags

ROOT = Path(__file__).resolve().parents[1]


def graph_for(pairs, starts=('S',), goals=('G',), extra=()):
    ids = sorted({v for pair in pairs for v in pair} | set(starts) | set(goals) | set(extra))
    vertices = []
    for i, v in enumerate(ids):
        vertices.append({'id': v, 'centroid': [i * 2., 0.],
                         'polygon': [[i*2, 0], [i*2+1, 0], [i*2+1, 1], [i*2, 1]],
                         'descriptors': {'aspect_ratio': 100., 'mean_clearance': 5.}})
    by_id = {v['id']: v for v in vertices}
    edges = []
    for a, b in pairs:
        midpoint = (by_id[a]['centroid'][0] + by_id[b]['centroid'][0]) / 2
        for source, target in ((a, b), (b, a)):
            edges.append({'source': source, 'target': target,
                          'safe_portal': [[midpoint, 0.5], [midpoint, 1.5]],
                          'safe_portal_width': 1., 'portal_width': 1.4})
    return {'vertices': vertices, 'directed_edges': edges,
            'planning': {'start_regions': list(starts), 'goal_regions': list(goals),
                         'robot_radius': 0.2, 'required_clearance': 0.3}}


class SequenceTests(unittest.TestCase):
    def test_weight_uses_safe_portal_midpoint(self):
        graph = graph_for([('S', 'G')])
        vertices, adjacency, _ = weighted_graph(graph)
        # Centroids differ by 2, midpoint is 1 above their axis.
        self.assertAlmostEqual(adjacency['S']['G'], 2 * math.sqrt(2))
        result = prepare(graph, load_config())
        self.assertEqual(result['query']['returned_k'], 1)
        self.assertAlmostEqual(result['sequences'][0]['total_weight'], 2*math.sqrt(2))

    def test_yen_matches_exhaustive_simple_paths(self):
        # Independent exhaustive oracle on small graphs, including equal costs.
        for seed in range(15):
            rng = random.Random(seed)
            adjacency = {str(i): {} for i in range(6)}
            for a, b in itertools.permutations(adjacency, 2):
                if rng.random() < .35:
                    adjacency[a][b] = rng.randint(1, 4)
            paths = []
            def walk(path):
                if path[-1] == '5':
                    paths.append(tuple(path))
                    return
                for b in adjacency[path[-1]]:
                    if b not in path:
                        walk(path + [b])
            walk(['0'])
            expected = sorted(paths, key=lambda p: (path_cost(p, adjacency), p))[:5]
            self.assertEqual(yen_paths(adjacency, '0', '5', 5), expected)

    def test_multiple_endpoints_and_shared_region(self):
        adjacency = {'A': {'B': 1.}, 'B': {'A': 1., 'C': 1.}, 'C': {}}
        paths = query_paths(adjacency, ['A', 'B'], ['B', 'C'], 3)
        self.assertEqual(paths, [('B',), ('A', 'B'), ('B', 'C')])
        same = prepare(graph_for([], starts=('S',), goals=('S',)), load_config())
        self.assertEqual(same['sequences'][0]['regions'], ['S'])
        self.assertEqual(same['sequences'][0]['total_weight'], 0)
        self.assertFalse(same['regions'][0]['memberships']['alternative_route']['active'])

    def test_endpoint_coordinates_include_all_boundary_matches(self):
        graph = graph_for([('A', 'B')], starts=('A',), goals=('B',))
        graph['vertices'][0]['polygon'] = [[0,0],[1,0],[1,1],[0,1]]
        graph['vertices'][1]['polygon'] = [[1,0],[2,0],[2,1],[1,1]]
        graph['planning'].update(start=[1,.5], goal=[1.5,.5])
        result = prepare(graph, load_config())
        self.assertEqual(result['query']['start_regions'], ['A', 'B'])
        self.assertEqual(result['sequences'][0]['regions'], ['B'])

    def test_disconnected_and_missing_endpoints(self):
        graph = graph_for([('S', 'A'), ('G', 'B')])
        result = prepare(graph, load_config())
        self.assertEqual(result['query']['status'], 'disconnected')
        self.assertEqual(result['sequences'], [])
        self.assertIsNone(result['connections'][0]['structural_features']['sequence_fraction'])
        graph['planning'].update(start=[1000,1000])
        self.assertEqual(prepare(graph, load_config())['query']['status'], 'missing_endpoint_regions')

    def test_sequences_only_use_retained_directed_edges(self):
        graph = graph_for([('S', 'A'), ('A', 'G')])
        graph['directed_edges'] = [e for e in graph['directed_edges']
                                   if (e['source'], e['target']) != ('A', 'G')]
        result = prepare(graph, load_config())
        self.assertEqual(result['sequences'], [])
        self.assertIsNone(result['regions'][0]['memberships']['pocket']['value'])


class StructuralLabelTests(unittest.TestCase):
    def test_simple_route_membership_excludes_cycle_side_excursions(self):
        from prepare_scoring_data import simple_route_members
        # A cycle attached at a single articulation cannot occur on a simple
        # S-G route: entering it requires revisiting its attachment node.
        adjacency = {'S': {'A'}, 'A': {'S','G','X','Y'}, 'G': {'A'},
                     'X': {'A','Y'}, 'Y': {'A','X'}}
        nodes, edges = simple_route_members(adjacency, ['S'], ['G'])
        self.assertEqual(nodes, {'S','A','G'})
        self.assertEqual(edges, {('A','S'),('A','G')})

    def test_fraction_one_does_not_mean_mandatory(self):
        graph = graph_for([('S','A'),('A','B'),('B','G'),('A','C'),('C','G'),
                           ('A','D'),('D','G'),('S','Z'),('Z','G')])
        # Make the S-Z-G bypass costly while preserving valid geometry.
        for e in graph['directed_edges']:
            if 'Z' in (e['source'], e['target']):
                e['safe_portal'] = [[50.,50.], [50.,51.]]
        result = prepare(graph, load_config())
        edge = next(e for e in result['connections'] if {e['source'],e['target']} == {'S','A'})
        self.assertEqual(edge['structural_features']['sequence_fraction'], 1.)
        self.assertFalse(edge['structural_features']['mandatory_on_all_start_goal_paths'])
        self.assertTrue(edge['memberships']['critical']['active'])

    def test_mandatory_pockets_and_true_alternative_routes(self):
        graph = graph_for([('S','A'),('A','G'),('S','B'),('B','G'),('B','P'),('P','Q')])
        result = prepare(graph, load_config())
        regions = {r['id']: r for r in result['regions']}
        self.assertTrue(regions['P']['memberships']['pocket']['active'])
        self.assertTrue(regions['Q']['memberships']['dead_end']['active'])
        self.assertFalse(regions['P']['memberships']['alternative_route']['active'])
        self.assertFalse(regions['Q']['memberships']['alternative_route']['active'])
        self.assertTrue(any(e['memberships']['alternative_route']['active'] for e in result['connections']))
        single = prepare(graph_for([('S','G')]), load_config())
        self.assertTrue(single['connections'][0]['structural_features']['mandatory_on_all_start_goal_paths'])

    def test_missing_inscribed_geometry_is_not_substituted(self):
        result = prepare(graph_for([('S','A'),('A','G')]), load_config())
        middle = next(r for r in result['regions'] if r['id']=='A')
        self.assertIsNone(middle['memberships']['open']['value'])
        self.assertIsNone(middle['memberships']['corridor']['value'])
        self.assertIsNone(result['connections'][0]['memberships']['narrow']['value'])
        self.assertIn('not equivalent', middle['memberships']['corridor']['reason'])

    def test_explicit_features_and_config_control_memberships(self):
        graph = graph_for([('S','A'),('A','G')])
        for r in graph['vertices']:
            r['descriptors'].update(maximum_inscribed_ball_radius=1., maximum_inscribed_ellipsoid_axis_ratio=3.)
        for e in graph['directed_edges']:
            e['intersection_inscribed_ball_radius'] = .4
        config = load_config()
        result = prepare(graph, config)
        middle = next(r for r in result['regions'] if r['id']=='A')
        self.assertAlmostEqual(middle['memberships']['open']['value'], .5)
        self.assertAlmostEqual(middle['memberships']['corridor']['value'], .5)
        self.assertAlmostEqual(result['connections'][0]['memberships']['narrow']['value'], .5)
        config['label_rules']['open']['threshold'] = 6
        self.assertFalse(prepare(graph, config)['regions'][0]['memberships']['open']['active'])
        self.assertEqual(sigmoid(10000,0,1),1.)

    def test_flappy_sequences_valid_and_source_unchanged(self):
        path = ROOT/'research/data/flappy/graph.json'
        before = path.read_bytes()
        graph = json.loads(before)
        frozen = deepcopy(graph)
        result = prepare(graph, load_config(), 'flappy')
        _, adjacency, _ = weighted_graph(graph)
        self.assertEqual(result['query']['returned_k'], 3)
        for sequence in result['sequences']:
            p = sequence['regions']
            self.assertEqual(len(p),len(set(p)))
            self.assertIn(p[0],result['query']['start_regions'])
            self.assertIn(p[-1],result['query']['goal_regions'])
            self.assertAlmostEqual(sequence['total_weight'],path_cost(p,adjacency))
            self.assertEqual(len(sequence['connections']),len(p)-1)
        self.assertEqual(graph,frozen)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(len(result['regions']),35)
        self.assertEqual(len(result['connections']),43)

    def test_invalid_k_and_output_overwrite(self):
        with self.assertRaises(ValueError):
            load_config(k=0)
        with self.assertRaises(ValueError):
            prepare_file(ROOT/'research/data/flappy/graph.json',output=ROOT/'research/data/flappy/graph.json')
        with self.assertRaises(ValueError):
            score_map('flappy',output=ROOT/'outputs/flappy/scores.json',prepare_only=True)


class ScoringContractTests(unittest.TestCase):
    def test_explanation_flags_do_not_relabel_or_change_scores(self):
        data = prepare(graph_for([('S','G')]), load_config())
        edge = deepcopy(data['connections'][0])
        original = deepcopy(edge)
        answer = {'status':'scored','score':7,'reason':'This connection is a junction.'}
        flags = explanation_review_flags(answer, edge, connection=True)
        self.assertTrue(any('junction' in flag for flag in flags))
        self.assertEqual(edge, original)
        self.assertEqual(answer['score'],7)
        answer['reason']='No narrow label is available.'
        self.assertEqual(explanation_review_flags(answer,edge,connection=True),[])

    def test_validation_rejects_invalid_responses(self):
        for answer in [{'status':'scored','score':True,'reason':'x'},
                       {'status':'scored','score':11,'reason':'x'},
                       {'status':'infeasible','score':None,'reason':'x'},
                       {'status':'insufficient_data','score':0,'reason':'x'},
                       {'status':'scored','score':7,'reason':'x','labels':['open']}]:
            with self.assertRaises(ValueError):
                validate_answer(answer)
        with self.assertRaises(ValueError):
            validate_answer({'status':'scored','score':7,'reason':'x'*321})

    def test_context_identity_checkpoint_and_resume(self):
        data = prepare(graph_for([('S','G')]),load_config())
        calls = []
        def fake(task, payload, **kwargs):
            calls.append((task,payload))
            return {'status':'scored','score':6,'reason':'Structural evidence only; missing width labels.'}
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'scores.json'
            result=score_prepared(data,output=output,request_fn=fake)
            self.assertEqual(len(calls),3)
            self.assertEqual(result['status'],'complete')
            self.assertIn('sequences',calls[0][1]['context'])
            self.assertIn('memberships',calls[0][1]['item'])
            score_prepared(data,output=output,resume=True,request_fn=fake)
            self.assertEqual(len(calls),3)
            with self.assertRaises(ValueError):
                score_prepared(data,model='different',output=output,resume=True,request_fn=fake)

    def test_disconnected_query_does_not_call_model(self):
        data=prepare(graph_for([('S','A'),('G','B')]),load_config())
        def fail(*args,**kwargs):
            raise AssertionError('Model must not be called')
        with tempfile.TemporaryDirectory() as directory:
            result=score_prepared(data,output=Path(directory)/'scores.json',request_fn=fail)
        self.assertTrue(all(r['score'] is None for r in result['regions']+result['edges']))

    def test_failed_run_resumes_from_last_saved_item(self):
        data=prepare(graph_for([('S','G')]), load_config())
        calls=[]
        def interrupted(task, payload, **kwargs):
            calls.append(task)
            if len(calls)==2:
                raise ConnectionError('Simulated interrupted request')
            return {'status':'scored','score':5,'reason':'A retained query connection.'}
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'scores.json'
            with self.assertRaises(ConnectionError):
                score_prepared(data,output=output,request_fn=interrupted)
            checkpoint=json.loads(output.read_text())
            self.assertEqual(len(checkpoint['regions']),1)
            def success(*args,**kwargs):
                return {'status':'scored','score':5,'reason':'A retained query connection.'}
            result=score_prepared(data,output=output,resume=True,request_fn=success)
            self.assertEqual(len(result['regions']),2)
            self.assertEqual(len(result['edges']),1)
            self.assertEqual(result['status'],'complete')


if __name__ == '__main__':
    unittest.main()
