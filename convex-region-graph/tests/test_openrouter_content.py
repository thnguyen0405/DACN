"""Regression tests for HTTP 200 responses without usable final JSON."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from llm_region_prior import OpenRouterRegionPriorProvider, build_region_prior
from llm_weight_provider import LLMProviderError
from tests.test_llm_planner import FakeHTTPResponse, edge, vertex


class OpenRouterContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.debug = Path(self.temp.name) / 'response.txt'
        self.provider = OpenRouterRegionPriorProvider(
            Path(__file__).parents[1] / 'prompts/region_prior_prompt.txt',
            api_key='regression-secret', model='openrouter/free', debug_response_path=self.debug)
        self.expected = {'region_scores': [{'id': 'A', 'score': 0.8}, {'id': 'B', 'score': 0.9}]}

    def completion(self, content, finish='stop', **fields):
        return {'model': 'example/free', 'choices': [
            {'finish_reason': finish, 'message': {'content': content, **fields}}]}

    def assert_failure(self, payload, message, calls=1):
        with patch('llm_weight_provider.urllib.request.urlopen', return_value=FakeHTTPResponse(payload)) as http:
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(LLMProviderError, message) as caught:
                self.provider._get_model_json('JSON')
        self.assertEqual(http.call_count, calls)
        return str(caught.exception)

    def test_null_then_valid_recovers_through_region_pipeline(self):
        replies = [self.completion(None), self.completion(json.dumps(self.expected))]
        graph = {'vertices': [vertex('A'), vertex('B')], 'directed_edges': [edge('A', 'B')]}
        with patch('llm_weight_provider.urllib.request.urlopen', side_effect=[FakeHTTPResponse(x) for x in replies]) as http:
            with redirect_stdout(io.StringIO()):
                prior, _, scores, missing = build_region_prior(graph, 'A', 'B', provider=self.provider)
        self.assertEqual(scores, {'A': 0.8, 'B': 0.9})
        self.assertEqual(missing, [])
        self.assertEqual(prior['provider_metadata']['resolved_model'], 'example/free')
        self.assertEqual(http.call_count, 2)
        for call in http.call_args_list:
            body = json.loads(call.args[0].data)
            self.assertEqual(body['model'], 'openrouter/free')
            self.assertNotIn('models', body)

    def test_empty_variants_retry_once_and_never_use_reasoning(self):
        for content in [None, '', '   ', []]:
            with self.subTest(content=content):
                self.assert_failure(self.completion(content, reasoning=json.dumps(self.expected)), 'empty final content', 2)
                self.assertTrue(self.debug.exists())

    def test_text_blocks_are_joined(self):
        text = json.dumps(self.expected)
        payload = self.completion([{'type': 'text', 'text': text[:20]}, {'type': 'text', 'text': text[20:]}])
        with patch('llm_weight_provider.urllib.request.urlopen', return_value=FakeHTTPResponse(payload)) as http:
            self.assertEqual(self.provider._get_model_json('JSON'), (self.expected, 'example/free'))
        self.assertEqual(http.call_count, 1)

    def test_token_limit_rejects_even_parseable_partial_scores(self):
        for content in [None, json.dumps(self.expected)]:
            payload = self.completion(content, finish='length', reasoning='hidden reasoning')
            payload['usage'] = {'completion_tokens': 500, 'completion_tokens_details': {'reasoning_tokens': 500}}
            error = self.assert_failure(payload, 'OPENROUTER_MAX_TOKENS')
            self.assertIn('reasoning_tokens', error)
            self.assertNotIn('hidden reasoning', error)

    def test_refusal_filter_tools_and_generation_failure_are_not_retried(self):
        for payload, error in [
            (self.completion(None, refusal='Cannot answer'), 'refused'),
            (self.completion(None, finish='content_filter'), 'filtered'),
            (self.completion(None, finish='tool_calls', tool_calls=[{}]), 'tool calls'),
            (self.completion(None, finish='error'), 'generation failed')]:
            with self.subTest(error=error):
                self.assert_failure(payload, error)

    def test_http_200_embedded_transient_error_recovers(self):
        for location in ['top', 'choice']:
            payload = {'error': {'code': 503, 'message': 'Provider unavailable'}}
            if location == 'choice':
                payload = {'choices': [{'error': payload['error']}]}
            replies = [payload, self.completion(json.dumps(self.expected))]
            with patch('llm_weight_provider.urllib.request.urlopen', side_effect=[FakeHTTPResponse(x) for x in replies]) as http:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(self.provider._get_model_json('JSON')[0], self.expected)
            self.assertEqual(http.call_count, 2)

    def test_embedded_auth_and_rate_limit_do_not_retry_and_redact(self):
        for code, message in [(401, 'authentication failed'), (429, 'rate limit')]:
            error = self.assert_failure({'error': {'code': code, 'message': 'regression-secret'}}, message)
            self.assertNotIn('regression-secret', error)
            self.assertNotIn('regression-secret', self.debug.read_text())

    def test_malformed_envelopes_and_content_fail_cleanly(self):
        cases = [{}, {'choices': []}, {'choices': [None]}, {'choices': [{'message': []}]}]
        cases += [self.completion(x) for x in [42, {}, [{'type': 'reasoning', 'text': '{}'}], '[]', '{bad']]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assert_failure(payload, 'OpenRouter|LLM')

    def test_transport_and_content_share_two_attempt_budget(self):
        with patch('llm_weight_provider.urllib.request.urlopen', side_effect=[
            FakeHTTPResponse(raw_body=b'{bad'), FakeHTTPResponse(self.completion(None))]) as http:
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(LLMProviderError, 'empty final content'):
                self.provider._get_model_json('JSON')
        self.assertEqual(http.call_count, 2)

    def test_diagnostic_redacts_context_and_saved_payload(self):
        payload = self.completion(None)
        payload['model'] = 'regression-secret'
        error = self.assert_failure(payload, 'empty final content', 2)
        self.assertNotIn('regression-secret', error)
        self.assertNotIn('regression-secret', self.debug.read_text())
        self.assertIn('[REDACTED]', self.debug.read_text())

    def test_optional_max_tokens_is_forwarded(self):
        with patch.dict('os.environ', {'OPENROUTER_MAX_TOKENS': '8192'}):
            provider = OpenRouterRegionPriorProvider(self.provider.prompt_path, api_key='test')
        with patch('llm_weight_provider.urllib.request.urlopen', return_value=FakeHTTPResponse(self.completion(json.dumps(self.expected)))) as http:
            provider._get_model_json('JSON')
        self.assertEqual(json.loads(http.call_args.args[0].data)['max_tokens'], 8192)

    def test_invalid_max_tokens_fail_before_request(self):
        for value in [0, -1, True, 1.5, 'abc', '1.5']:
            with self.subTest(value=value), self.assertRaisesRegex(LLMProviderError, 'positive integer'):
                OpenRouterRegionPriorProvider(self.provider.prompt_path, api_key='test', max_tokens=value)


if __name__ == '__main__':
    unittest.main()
