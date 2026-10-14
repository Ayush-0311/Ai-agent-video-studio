"""Small, bounded public reference lookup. Not a fact-checking guarantee."""
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests


def is_explanation(prompt):
    return bool(re.search(r'\b(explain|exaplain|exaplin|explainn|tell me about|what is|what are|how does|how do|samjhao|kya hai)\b|क्या है|समझाओ', prompt, re.I))


def lookup(prompt):
    query = re.sub(r'^\s*(?:please\s+)?(?:(?:explain|exaplain|exaplin|explainn)(?:\s+(?:to\s+)?me)?|what (?:is|are)|tell me about|samjhao)\s+', '', prompt, flags=re.I)
    query = re.sub(r'\bmachine lear(?:i)?ng\b', 'machine learning', query, flags=re.I)
    query = query.strip(' .?!')[:180]
    language = 'hi' if re.search(r'[\u0900-\u097f]', query) else 'en'
    host = language + '.wikipedia.org'
    result = {'status': 'unavailable', 'query': query, 'provider': 'Wikipedia introductory references',
              'checked_at': datetime.now(timezone.utc).isoformat(), 'sources': [],
              'note': 'No online references retrieved; narration must avoid uncertain or current claims.'}
    try:
        response = requests.get('https://' + host + '/w/api.php', params={
            'action': 'query', 'generator': 'search', 'gsrsearch': query, 'gsrlimit': 2,
            'prop': 'extracts|info', 'inprop': 'url', 'exintro': 1, 'explaintext': 1,
            'exchars': 1600, 'format': 'json'}, headers={'User-Agent': 'SmartEditStudentProject/1.0'}, timeout=(5, 12))
        response.raise_for_status()
        pages = response.json().get('query', {}).get('pages', {}).values()
        for page in sorted(pages, key=lambda p: p.get('index', 0)):
            url, excerpt = page.get('fullurl', ''), page.get('extract', '').strip()
            parsed = urlsplit(url)
            if parsed.scheme == 'https' and parsed.hostname == host and excerpt:
                result['sources'].append({'title': str(page.get('title', ''))[:200], 'url': url, 'excerpt': excerpt[:1600]})
        if result['sources']:
            result.update(status='retrieved', note='Introductory references only. Review relevance and factual claims before publishing.')
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        pass  # Offline references must not prevent an otherwise usable explainer.
    return result
