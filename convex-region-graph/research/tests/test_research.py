import json
import math
from pathlib import Path
import tempfile
import unittest
from shapely.geometry import Polygon
from research.geometry import World,GridReference,path_region_sequence,overlap_metrics
from research.adaptive import AdaptivePrior
from research.import_dataset import read_poly
from research.rrt_experiment import run_rrt
from research.scoring_audit import sequence_audit
from tests.test_scoring_and_benchmark import demo_graph
from scoring import _required_bottlenecks


def world():
 return World({'boundary':[[0,0],[3,0],[3,1],[0,1]],'obstacles':[],
               'robot_radius':.1,'safety_margin':0,'start':[.5,.5],'goal':[2.5,.5]})


class GeometryTests(unittest.TestCase):
 def test_point_and_whole_segment_clearance(self):
  w=World({'boundary':[[0,0],[4,0],[4,4],[0,4]],'obstacles':[[[1.99,1],[2.01,1],[2.01,3],[1.99,3]]], 'robot_radius':.1})
  self.assertTrue(w.valid([1,2]));self.assertTrue(w.valid([3,2]))
  self.assertFalse(w.segment_valid([1,2],[3,2]))
  self.assertFalse(w.valid([.05,2]))
  self.assertTrue(w.segment_valid([1,.5],[3,.5]))
 def test_grid_returns_safe_path_and_corridor_restricts_edges(self):
  w=world();grid=GridReference(w,.1)
  reference=grid.shortest(w.data['start'],w.data['goal'])
  self.assertTrue(w.path_valid(reference['path']))
  self.assertIsNone(grid.shortest(w.data['start'],w.data['goal'],Polygon([[0,0],[1,0],[1,1],[0,1]])))
 def test_region_sequence_catches_intermediate_regions(self):
  self.assertEqual(path_region_sequence([[.5,.5],[2.5,.5]],demo_graph()),['C0','C1','C2'])
 def test_shared_boundary_does_not_duplicate_regions(self):
  g=demo_graph()
  self.assertEqual(len(path_region_sequence([[1,.2],[1,.8]],g)),1)
 def test_overlap_identical_and_failure(self):
  path=[[.5,.5],[2.5,.5]]
  r=overlap_metrics(path,path,demo_graph())
  for key in ['region_jaccard_pct','sequence_lcs_pct','path_coverage_pct']:self.assertAlmostEqual(r[key],100)
  self.assertIsNone(overlap_metrics([],path,demo_graph())['path_coverage_pct'])
 def test_sequence_validity_is_separate_from_continuous_optimality(self):
  g=demo_graph();g['planning'].update(start_region='C0',goal_region='C2');w=world();grid=GridReference(w,.1)
  ref=grid.shortest(w.data['start'],w.data['goal'])
  r=sequence_audit(g,['C0','C1','C2'],w,grid,ref)
  self.assertTrue(r['topology_valid']);self.assertTrue(r['retains_grid_optimum'])
  self.assertEqual(r['continuous_optimality'],'not_proven')
  self.assertFalse(sequence_audit(g,['C0','C2'],w,grid,ref)['topology_valid'])
 def test_poly_respects_vertex_order_and_comments(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'x.poly';p.write_text('# comment\n1\n4 out\n0 0\n0 1\n1 1\n1 0\n4 3 2 1\n')
   outer,holes=read_poly(p);self.assertEqual(outer[0],[1,0]);self.assertEqual(holes,[])
 def test_disconnected_graph_has_no_required_bottlenecks(self):
  g=demo_graph();g['directed_edges']=[]
  self.assertEqual(_required_bottlenecks(g,'C0','C2'),set())
  self.assertEqual(_required_bottlenecks(demo_graph(),'C0','C2'),{'C1'})


class AdaptiveTests(unittest.TestCase):
 def test_decay_only_on_accepted_nodes_and_respects_floor(self):
  p=AdaptivePrior({'A':.8,'B':.2},decay=.5,every=2,floor=.1)
  p.observe(1);self.assertEqual(p.scores['A'],.8)
  p.observe(2,'A');p.observe(3,'A');self.assertEqual(p.scores['A'],.4)
  for i in range(4,30):p.observe(i,'A')
  self.assertEqual(p.scores['A'],.1);self.assertEqual(p.scores['B'],.2)
 def test_region_entry_respects_cooldown_and_call_cap(self):
  p=AdaptivePrior({'A':.8,'B':.2},refresh='new_region',cooldown=3,max_calls=1)
  self.assertFalse(p.observe(1,'A'));self.assertFalse(p.observe(2,'A'));self.assertTrue(p.observe(3))
  self.assertFalse(p.observe(5,'B'));self.assertFalse(p.observe(10));self.assertEqual(p.calls,1)
 def test_interval_fires_without_accepted_node(self):
  p=AdaptivePrior({'A':1},refresh='interval',interval=5,cooldown=0,max_calls=2)
  self.assertFalse(p.observe(4));self.assertTrue(p.observe(5));self.assertTrue(p.observe(10));self.assertFalse(p.observe(15))
 def test_update_preserves_visit_decay(self):
  p=AdaptivePrior({'A':1},decay=.5,every=1);p.observe(1,'A');p.update({'A':.8});self.assertEqual(p.scores['A'],.4)
  with self.assertRaises(ValueError):p.update({'B':.5})
 def test_invalid_configs_rejected(self):
  for kwargs in [{'decay':1},{'every':0},{'interval':0},{'max_calls':-1}]:
   with self.assertRaises(ValueError):AdaptivePrior({'A':1},**kwargs)
 def test_seeded_rrt_paths_safe_and_repeatable(self):
  w=world();g=demo_graph();scores={v['id']:.5 for v in g['vertices']}
  a=run_rrt(w,g,scores,iterations=80,seed=42,decay=.15)
  b=run_rrt(w,g,scores,iterations=80,seed=42,decay=.15)
  self.assertTrue(a['success']);self.assertTrue(w.path_valid(a['path']));self.assertEqual(a['path'],b['path'])
 def test_start_region_does_not_trigger_new_region_refresh(self):
  g={'vertices':[{'id':'A','polygon':[[0,0],[3,0],[3,1],[0,1]]}]}
  def unexpected(_):raise AssertionError('Start region is already visited')
  r=run_rrt(world(),g,{'A':1},iterations=120,refresh='new_region',refresh_callback=unexpected)
  self.assertEqual(r['refresh_results'],[])
  self.assertFalse(any(e['type']=='refresh_due' for e in r['adaptive_events']))
 def test_refresh_failure_keeps_valid_existing_prior(self):
  def fail(_):raise RuntimeError('fixture failure')
  a=run_rrt(world(),demo_graph(),{'C0':.5,'C1':.5,'C2':.5},iterations=120,refresh='interval',interval=100,refresh_callback=fail)
  self.assertEqual(len(a['refresh_results']),1);self.assertFalse(a['refresh_results'][0]['success'])
  self.assertTrue(a['success'])


if __name__=='__main__':unittest.main()
