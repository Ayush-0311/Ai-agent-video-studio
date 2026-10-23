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
        self.assertEqual(get.call_args.kwargs['params']['exchars'], 1200)
        self.assertEqual(get.call_args.kwargs['params']['exlimit'], 3)
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

    def test_empty_focused_search_falls_back_once_and_skips_ambiguous_pages(self):
        empty=Mock(); empty.json.return_value={}
        found=Mock(); found.json.return_value={'query':{'pages':{
            '1':{'index':1,'title':'Solar','fullurl':'https://en.wikipedia.org/wiki/Solar',
                 'extract':'Several meanings','pageprops':{'disambiguation':''}},
            '2':{'index':2,'title':'Solar power','fullurl':'https://en.wikipedia.org/wiki/Solar_power',
                 'extract':'Light converted to electricity'}}}}
        with patch.object(research.requests,'get',side_effect=[empty,found]) as get:
            result=research.lookup('Solar power household appliance example',fallback_query='Solar power')
        self.assertEqual(get.call_count,2)
        self.assertEqual(result['status'],'retrieved')
        self.assertEqual(result['query'],'Solar power')
        self.assertEqual(len(result['sources']),1)
        self.assertEqual(get.call_args.kwargs['params']['ppprop'],'disambiguation')
        self.assertEqual(len(result['attempted_queries']),2)

    def test_provider_and_connection_failures_do_not_repeat_search(self):
        response=Mock(); response.json.return_value={'error':{'code':'ratelimited'}}
        for reply in (response,requests.Timeout()):
            with patch.object(research.requests,'get',side_effect=[reply]) as get:
                result=research.lookup('Solar electricity',fallback_query='Solar power')
            self.assertEqual(result['status'],'unavailable')
            self.assertEqual(result['sources'],[])
            self.assertEqual(get.call_count,1)
            self.assertIn('failure_reason',result)

    def test_duplicate_or_blank_queries_do_not_send_extra_requests(self):
        response=Mock(); response.json.return_value={}
        with patch.object(research.requests,'get',return_value=response) as get:
            research.lookup('Explain solar power',fallback_query='solar power')
            self.assertEqual(get.call_count,1)
        with patch.object(research.requests,'get') as get:
            research.lookup(' ')
        get.assert_not_called()

    def test_relevance_filter_drops_broad_hits_and_cleans_search_noise(self):
        response=Mock(); response.json.return_value={'query':{'pages':{
            '1':{'index':1,'title':'Deforestation','fullurl':'https://en.wikipedia.org/wiki/Deforestation',
                 'extract':'Tree cover loss is often caused by agriculture.'},
            '2':{'index':2,'title':'Mangrove forest','fullurl':'https://en.wikipedia.org/wiki/Mangrove_forest',
                 'extract':'Mangrove roots stabilize shorelines and help reduce erosion.'}}}}
        with patch.object(research.requests,'get',return_value=response) as get:
            result=research.lookup('tree roots riverbank erosion mechanism science wikipedia')
        self.assertEqual(get.call_args.kwargs['params']['gsrsearch'],'tree roots riverbank erosion')
        self.assertEqual([source['title'] for source in result['sources']],['Mangrove forest'])
