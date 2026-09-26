import unittest
from build_graph import build_pipeline
from export_scoring_dataset import make_record

class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.graph,_,_=build_pipeline({'map':{'boundary':[[0,0],[2,0],[2,2],[0,2]],
            'obstacles':[], 'start':[.5,.5], 'goal':[1.5,1.5]}})
    def test_unlabeled_has_no_fabricated_target(self):
        record=make_record(self.graph,'rubric')
        self.assertEqual([m['role'] for m in record['messages']],['system','user'])
    def test_labeled_requires_explicit_scores_and_provenance(self):
        labels={'region_scores':[{'id':'C0','score':.8,'reason':'reviewed'}],'edge_costs':[]}
        with self.assertRaises(ValueError): make_record(self.graph,'rubric',labels)
        self.assertEqual(make_record(self.graph,'rubric',labels,'human-reviewed')['messages'][-1]['role'],'assistant')
        with self.assertRaises(ValueError):
            make_record(self.graph,'rubric',{'region_scores':[],'edge_costs':[]},'human-reviewed')

class ResponsesParsingTests(unittest.TestCase):
    def test_rest_output_after_reasoning(self):
        from llm_region_planner import response_text
        self.assertEqual(response_text({'status':'completed','output':[
            {'type':'reasoning'}, {'type':'message','content':[{'type':'output_text','text':'{"ok":true}'}]}]}),'{"ok":true}')
    def test_refusal_and_incomplete(self):
        from llm_region_planner import response_text
        for payload in ({'status':'incomplete','output_text':'{}'},
                        {'output':[{'type':'message','content':[{'type':'refusal'}]}]}):
            with self.assertRaises(ValueError): response_text(payload)
