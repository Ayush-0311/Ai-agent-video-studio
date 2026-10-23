"""Real Requests response objects for streaming HTTP boundary fixtures."""
import io
import json
import requests


def response(data=None, content=b'', mime='application/json', status=200, headers=None):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode() if data is not None else content
    result._content_consumed = True
    result.raw = io.BytesIO(result._content)
    result.headers.update({'content-type': mime, 'Content-Length': str(len(result._content))})
    result.headers.update(headers or {})
    return result
