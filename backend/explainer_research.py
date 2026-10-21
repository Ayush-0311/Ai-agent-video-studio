"""Small, bounded public reference lookup. Not a fact-checking guarantee."""
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests


def is_explanation(prompt):
    return bool(re.search(r'\b(explain|exaplain|exaplin|explainn|tell me about|what is|what are|how does|how do|samjhao|kya hai)\b|क्या है|समझाओ', prompt, re.I))


def clean_query(prompt):
    query = re.sub(r'^\s*(?:please\s+)?(?:(?:explain|exaplain|exaplin|explainn)(?:\s+(?:to\s+)?me)?|what (?:is|are)|tell me about|samjhao)\s+', '', prompt, flags=re.I)
    query = re.sub(r'\bmachine lear(?:i)?ng\b', 'machine learning', query, flags=re.I)
    return query.strip(' .?!')[:180]


def lookup(prompt, fallback_query=None):
    query = clean_query(prompt)
    result = {'status': 'unavailable', 'query': query, 'provider': 'Wikipedia introductory references',
              'checked_at': datetime.now(timezone.utc).isoformat(), 'sources': [], 'attempted_queries':[],
              'note': 'No online references retrieved; narration must avoid uncertain or current claims.'}
    queries = list(dict.fromkeys(q for q in (query, clean_query(fallback_query or '')) if q))
    for candidate in queries[:2]:
        result['attempted_queries'].append(candidate)
        host = ('hi' if re.search(r'[\u0900-\u097f]', candidate) else 'en') + '.wikipedia.org'
        try:
            response = requests.get('https://' + host + '/w/api.php', params={
                'action': 'query', 'generator': 'search', 'gsrsearch': candidate, 'gsrlimit': 3,
                'prop': 'extracts|info|pageprops', 'ppprop':'disambiguation',
                'inprop': 'url', 'exintro': 1, 'explaintext': 1,
                'exchars': 1600, 'format': 'json'}, headers={'User-Agent': 'SmartEditStudentProject/1.0'}, timeout=(3, 5))
            response.raise_for_status()
            payload = response.json()
            if payload.get('error'):
                result['failure_reason'] = 'provider_error'
                break
            pages = payload.get('query', {}).get('pages', {}).values()
            for page in sorted(pages, key=lambda p: p.get('index', 0)):
                if 'disambiguation' in page.get('pageprops', {}):
                    continue
                url, excerpt = page.get('fullurl', ''), page.get('extract', '').strip()
                parsed = urlsplit(url)
                if parsed.scheme == 'https' and parsed.hostname == host and excerpt:
                    result['sources'].append({'title': str(page.get('title', ''))[:200], 'url': url, 'excerpt': excerpt[:1600]})
                if len(result['sources']) == 2:
                    break
            if result['sources']:
                result.update(status='retrieved', query=candidate,
                              note='Introductory references only. Review relevance and factual claims before publishing.')
                result.pop('failure_reason', None)
                break
            result['failure_reason'] = 'no_results'
        except requests.RequestException:
            result['failure_reason'] = 'connection_or_http_error'
            break  # A broader query cannot repair an offline or rate-limited service.
        except (ValueError, TypeError, AttributeError):
            result['failure_reason'] = 'invalid_response'
            break
    return result
