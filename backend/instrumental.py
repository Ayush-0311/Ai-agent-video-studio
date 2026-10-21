"""Original local instrumental beds; no downloads, keys or third-party recordings."""
import math
import wave


def create(path, seconds, mood='cinematic'):
    import numpy as np
    rate=24000
    beat=60/(84 if mood=='uplifting' else 68)
    bar=beat*4
    chords = [(57,60,64),(53,57,60),(48,52,55),(55,59,62)]
    if mood=='calm':
        chords=[(48,52,55),(53,57,60),(57,60,64),(55,59,62)]
    with wave.open(str(path),'wb') as out:
        out.setnchannels(2);out.setsampwidth(2);out.setframerate(rate)
        for offset in range(math.ceil(seconds)):
            t=np.arange(min(rate,round((seconds-offset)*rate)),dtype=np.float64)/rate+offset
            channels=[]
            for side in (-1,1):
                signal=np.zeros_like(t)
                for index,chord in enumerate(chords):
                    active=((t//bar).astype(int)%4)==index
                    phase=t%bar
                    env=np.minimum(phase/.35,1)*np.minimum((bar-phase)/.6,1)
                    for note in chord:
                        hz=440*2**((note-69)/12)*(1+side*.0008)
                        signal+=active*env*(np.sin(2*np.pi*hz*t)+.18*np.sin(4*np.pi*hz*t))*.035
                        pluck=t%beat
                        signal+=active*np.exp(-pluck*5)*np.sin(2*np.pi*hz*2*t)*.018
                if mood!='calm':
                    pulse=t%beat
                    signal+=np.exp(-pulse*18)*np.sin(2*np.pi*55*t)*.035
                fade=np.minimum(t/2,1)*np.minimum((seconds-t)/3,1)
                channels.append(signal*np.maximum(0,fade))
            stereo=np.stack(channels,axis=1)
            out.writeframes((np.clip(stereo,-.8,.8)*32767).astype('<i2').tobytes())
