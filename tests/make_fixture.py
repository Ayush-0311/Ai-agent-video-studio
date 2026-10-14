"""Portable real-media fixture for editor tests; no external download needed."""
import subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from runtime_tools import _find_ffmpeg
if __name__=='__main__':
    target=Path(sys.argv[1]);target.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([_find_ffmpeg(),'-y','-v','error','-f','lavfi','-i','testsrc2=size=1280x720:rate=30',
        '-f','lavfi','-i','sine=frequency=330:sample_rate=48000','-t','10','-c:v','libx264','-preset','ultrafast',
        '-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(target)],check=True)
