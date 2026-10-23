"""Stream immutable generated clips with bounded retries and HTTP range resume."""
import re
import time
from pathlib import Path
import requests


def download(url, destination, headers, checkpoint=lambda: None, limit=256*1024*1024):
    destination = Path(destination)
    # Each call owns a fresh partial; retries resume only this immutable job URL.
    destination.write_bytes(b'')
    etag = None
    for attempt in range(3):
        checkpoint()
        offset = destination.stat().st_size
        request_headers = dict(headers, **{'Accept-Encoding': 'identity'})
        if offset:
            request_headers['Range'] = f'bytes={offset}-'
            if etag:
                request_headers['If-Range'] = etag
        try:
            with requests.get(url, headers=request_headers, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                if not response.headers.get('content-type', '').startswith('video/'):
                    raise ValueError('Generated clip service returned non-video content.')
                if response.status_code == 206:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                    if not match or int(match[1]) != offset or int(match[2])+1 != int(match[3]):
                        raise ValueError('Invalid resumed clip range; retry the download.')
                    if etag and response.headers.get('ETag') != etag:
                        raise ValueError('Generated clip changed during download.')
                    total = int(match[3])
                    mode = 'ab'
                elif response.status_code == 200:
                    offset = 0  # Older bridges may ignore Range: restart safely.
                    total = int(response.headers.get('Content-Length', '0'))
                    mode = 'wb'
                else:
                    raise ValueError('Unexpected generated clip response.')
                if total > limit:
                    raise ValueError('Generated clip exceeds the download size limit.')
                etag = response.headers.get('ETag')
                with destination.open(mode) as output:
                    for block in response.iter_content(chunk_size=1024*1024):
                        checkpoint()
                        if block:
                            offset += len(block)
                            if offset > limit:
                                raise ValueError('Generated clip exceeds the download size limit.')
                            output.write(block)
                if not offset or (total and offset != total):
                    raise requests.ConnectionError('Generated clip transfer ended early.')
                return
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError, requests.HTTPError) as exc:
            if isinstance(exc, requests.HTTPError) and (exc.response is None or
                    exc.response.status_code not in (408, 429, 500, 502, 503, 504)):
                raise
            if attempt == 2:
                raise RuntimeError('Clip download interrupted after three attempts. Check the Colab connection.') from None
            checkpoint()
            time.sleep(1+attempt)
