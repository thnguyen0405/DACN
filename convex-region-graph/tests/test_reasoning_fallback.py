import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error

from llm_weight_provider import LLMProviderError, ReasoningRequiredError
from research.llm_study import StudyProvider


class ReasoningFallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        root = Path(__file__).resolve().parents[1]
        self.graph = json.loads((root / 'research/data/hole/graph.json').read_text())

    def provider(self, effort='none'):
        with mock.patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-key'}):
            return StudyProvider(self.graph, self.folder, self.folder / 'absent.env',
                                 reasoning_effort=effort)

    def rejected(self, code=400, message='Reasoning is mandatory for this endpoint and cannot be disabled.'):
        body = {'error': {'message': message, 'code': code, 'metadata': {'provider_name': None}}}
        return urllib.error.HTTPError('https://openrouter.ai/api/v1/chat/completions',
                                      code, 'rejected', {}, io.BytesIO(json.dumps(body).encode()))

    def test_exact_reported_error_retries_once_and_records_effective_setting(self):
        provider = self.provider()
        provider.max_tokens = 32768
        content = {'region_scores': [{'id': v['id'], 'score': .5, 'reason': 'Test fixture'}
                                     for v in self.graph['vertices']]}
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.headers = {'Content-Type': 'application/json'}
        response.read.return_value = json.dumps({
            'model': 'fixture:free', 'usage': {'cost': 0},
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}],
        }).encode()
        with mock.patch('urllib.request.urlopen', side_effect=[self.rejected(), response]) as transport:
            scores, metadata = provider.score()
        bodies = [json.loads(call.args[0].data) for call in transport.call_args_list]
        self.assertEqual([b['reasoning']['effort'] for b in bodies], ['none', 'low'])
        for body in bodies:
            self.assertEqual(body['model'], 'openrouter/free')
            self.assertEqual(body['max_tokens'], 32768)
        self.assertEqual(bodies[0]['messages'], bodies[1]['messages'])
        self.assertEqual(len(scores), len(self.graph['vertices']))
        self.assertEqual(metadata['requested_reasoning_effort'], 'none')
        self.assertEqual(metadata['reasoning_effort'], 'low')
        self.assertEqual(len(metadata['reasoning_fallbacks']), 1)

    def test_second_rejection_stops_and_is_not_mislabelled_unavailable(self):
        provider = self.provider()
        with mock.patch('urllib.request.urlopen', side_effect=[self.rejected(), self.rejected()]) as transport:
            with self.assertRaises(ReasoningRequiredError) as error:
                provider.score()
        self.assertEqual(transport.call_count, 2)
        self.assertNotIn('unavailable', str(error.exception))
        self.assertFalse((self.folder / 'call-00.json').exists())

    def test_rate_limit_and_explicit_low_do_not_trigger_compatibility_retry(self):
        for effort, rejection in [('none', self.rejected(429, 'Rate limit')),
                                  ('low', self.rejected())]:
            with self.subTest(effort=effort):
                provider = self.provider(effort)
                with mock.patch('urllib.request.urlopen', side_effect=rejection) as transport:
                    with self.assertRaises(LLMProviderError):
                        provider.score()
                self.assertEqual(transport.call_count, 1)


if __name__ == '__main__':
    unittest.main()
