"""Bounded bridge metadata lookup for cache identity across tunnel reconnects."""
import threading
import time
import requests

_lock = threading.Lock()
_entries = {}


def remember(cfg, data):
    models = data.get('cache_models', {}) if isinstance(data, dict) else {}
    if not isinstance(models, dict):
        models = {}
    with _lock:
        # Only retain current/recent connections; tokens never enter asset keys.
        if len(_entries) >= 8:
            _entries.clear()
        _entries[(cfg.image_url, cfg.bridge_token)] = (time.monotonic(), models)


def identity(cfg, kind):
    key = (cfg.image_url, cfg.bridge_token)
    with _lock:
        entry = _entries.get(key)
    if entry is None or time.monotonic()-entry[0] > 60:
        try:
            response = requests.get(cfg.image_url.rstrip('/')+'/health',
                headers={'Authorization': 'Bearer '+cfg.bridge_token}, timeout=10)
            response.raise_for_status()
            remember(cfg, response.json())
        except (requests.RequestException, ValueError):
            # Unknown/older bridges remain isolated by address. Never assume two
            # unknown engines have the same weights, voice or generation config.
            remember(cfg, {})
        with _lock:
            entry = _entries.get(key)
    model = entry[1].get(kind) if entry else None
    return ['bridge-model-v1', model] if model else ['legacy-bridge', cfg.image_url]
