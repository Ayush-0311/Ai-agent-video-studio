import unittest
from unittest.mock import Mock, patch
import requests
import explainer_research as research


class ResearchTests(unittest.TestCase):
    def test_public_reference_lookup_uses_clean_query_and_sorts_results(self):
        response = Mock()
        response.json.return_value = {'query':{'pages':{
            '2':{'index':2,'title':'Bad link','fullurl':'https://example.test','extract':'Do not use'},
            '1':{'index':1,'title':'Artificial intelligence','fullurl':'https://en.wikipedia.org/wiki/Artificial_intelligence','extract':'Definition ' * 300}}}}
        with patch.object(research.requests,'get',return_value=response) as get:
            result = research.lookup('explain me artificial intelligence')
        self.assertEqual(get.call_args.kwargs['params']['gsrsearch'], 'artificial intelligence')
        self.assertEqual(result['status'], 'retrieved')
        self.assertEqual(len(result['sources']), 1)
        self.assertLessEqual(len(result['sources'][0]['excerpt']), 1600)

    def test_network_failure_and_empty_results_are_explicit(self):
        with patch.object(research.requests,'get',side_effect=requests.Timeout):
            result = research.lookup('What is AI?')
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['sources'], [])
        response = Mock(); response.json.return_value = {}
        with patch.object(research.requests,'get',return_value=response):
            self.assertEqual(research.lookup('Unknown topic')['status'], 'unavailable')

    def test_explanation_intent(self):
        self.assertTrue(research.is_explanation('Explain machine learning'))
        self.assertTrue(research.is_explanation('exaplin me machine learing'))
        self.assertTrue(research.is_explanation('AI kya hai'))
        self.assertFalse(research.is_explanation('A puppy plays in a garden'))
