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
    query = re.sub(r'\b(?:mechanism|science|wikipedia|introductory|overview)\b', ' ', query, flags=re.I)
    return query.strip(' .?!')[:180]


def _relevance_score(query, title, excerpt):
    """Reject search hits that only match a broad word but miss the topic."""
    text = (title + ' ' + excerpt).casefold()
    tokens = [token for token in re.findall(r'[a-z0-9]+', query.casefold())
              if len(token) > 2 and token not in {
                  'the', 'and', 'for', 'with', 'from', 'into', 'how', 'does', 'help',
                  'reduce', 'make', 'use', 'example', 'explain', 'about', 'simple',
                  'beginner', 'beginners', 'only', 'all', 'not', 'prevent', 'can'}]
    groups = {
        'root': ('root',),
        'bank': ('riverbank', 'river bank', 'streambank', 'stream bank', 'bank', 'river', 'stream', 'riparian', 'shoreline'),
        'erosion': ('erosion', 'erod', 'sediment', 'soil loss'),
        'vegetation': ('tree', 'forest', 'plant', 'vegetation', 'mangrove'),
    }
    if any(token in {'root', 'roots'} for token in tokens) and any(
            token in {'riverbank', 'riverbanks', 'streambank', 'streambanks', 'erosion', 'erosions'}
            for token in tokens):
        matched = sum(any(alias in text for alias in aliases) for aliases in groups.values())
        return matched
    matched_terms = sum(token.rstrip('s') in text for token in tokens)
    return matched_terms


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
                'exchars': 1200, 'exlimit': 3, 'format': 'json'}, headers={'User-Agent': 'SmartEditStudentProject/1.0'}, timeout=(3, 5))
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
                title = str(page.get('title', ''))[:200]
                if (parsed.scheme == 'https' and parsed.hostname == host and excerpt
                        and _relevance_score(candidate, title, excerpt) >= min(2, len(re.findall(r'[a-z0-9]{3,}', candidate.casefold())))):
                    result['sources'].append({'title': title, 'url': url, 'excerpt': excerpt[:1600]})
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
