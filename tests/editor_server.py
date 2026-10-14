"""Isolated real backend for the Electron edit/export test; never opens production data."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
import studio
studio.DATA = root / 'backend' / 'studio-data' / 'verification' / 'editor-server'
import main
import uvicorn

if __name__ == '__main__':
    uvicorn.run(main.app, host='127.0.0.1', port=18761, log_level='warning')
